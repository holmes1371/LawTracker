"""DOJ FCPA enforcement actions adapter.

Source #5 in `design/sources.md`. The adapter targets DOJ's per-year
chronological case lists at
`/criminal/criminal-fraud/case/related-enforcement-actions/{year}`. The
class iterates `years` (default: 2025 + 2026) so the scout has 12-24
months of trend depth in a single poll.

The landing page at `/criminal-fraud/related-enforcement-actions` is a
navigation hub (alphabetical + chronological year index), not a case
list, so the adapter does not target it.

Each case on the year page renders as two adjacent paragraphs:

  <p>... <a href="/criminal/fraud/fcpa/cases/...">United States v. ...</a></p>
  <p class="Indent1">Case No: ...<br>District: ...<br>Filed: Month D, YYYY</p>

The parser pairs them by walking back from each `p.Indent1` to the
immediately-preceding `<p>` carrying the case-caption link.

Link-following enrichment (item 17, option (b) per Tom 2026-04-25):
for each list-page entry, the adapter best-effort fetches the linked
case-detail page, locates the press-release URL within it, fetches the
press release, and extracts: topic, component, industry, resolution_type,
amount_usd, press_release_url. Enrichment failures are silent — the
basic record is still emitted.
"""

import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, ClassVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from lawtracker.sources.base import EventRecord, SourceAdapter

YEAR_URL_TEMPLATE = (
    "https://www.justice.gov/criminal/criminal-fraud/case/related-enforcement-actions/{year}"
)
CURRENT_YEAR_URL = YEAR_URL_TEMPLATE.format(year=2026)

INDUSTRY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("medical device", "medical devices"),
    ("pharmaceutical", "pharmaceuticals"),
    ("healthcare", "healthcare"),
    ("oil and gas", "oil and gas"),
    ("oil & gas", "oil and gas"),
    ("petroleum", "oil and gas"),
    ("mining", "mining"),
    ("aerospace", "aerospace"),
    ("defense contractor", "defense"),
    ("defense industry", "defense"),
    ("financial services", "financial services"),
    ("investment bank", "financial services"),
    ("commercial bank", "financial services"),
    ("hedge fund", "financial services"),
    ("private equity", "financial services"),
    ("technology company", "technology"),
    ("software company", "technology"),
    ("telecommunications", "telecom"),
    ("telecom", "telecom"),
    ("energy company", "energy"),
    ("utility", "energy"),
    ("construction", "construction"),
    ("engineering and construction", "construction"),
    ("manufacturer", "manufacturing"),
    ("consumer goods", "consumer goods"),
    ("retail", "retail"),
    ("hospitality", "hospitality"),
    ("logistics", "logistics"),
    ("shipping", "shipping"),
    ("automotive", "automotive"),
    ("entertainment", "entertainment"),
    ("media company", "media"),
)

RESOLUTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdeclined to prosecute\b", re.IGNORECASE), "declination"),
    (re.compile(r"\bdeclination\b", re.IGNORECASE), "declination"),
    (re.compile(r"\bdeferred prosecution agreement\b", re.IGNORECASE), "DPA"),
    (re.compile(r"\bnon-?prosecution agreement\b", re.IGNORECASE), "NPA"),
    (re.compile(r"\bplea(?:ded|ed)?\s+guilty\b", re.IGNORECASE), "guilty plea"),
    (re.compile(r"\bguilty plea\b", re.IGNORECASE), "guilty plea"),
    (re.compile(r"\b(?:returned an? )?indictment\b", re.IGNORECASE), "indictment"),
    (re.compile(r"\bsentenc(?:ed|ing)\b", re.IGNORECASE), "sentencing"),
    (re.compile(r"\bcomplaint\s+(?:was\s+)?filed\b", re.IGNORECASE), "complaint"),
)

_AMOUNT_RE = re.compile(
    r"\$\s?([\d,]+(?:\.\d+)?)\s*(million|billion|thousand)?",
    re.IGNORECASE,
)

_CAPTION_PREFIX = re.compile(r"^(United States|U\.S\.|USA)\s+v\.\s+", re.IGNORECASE)
_PRESS_RELEASE_PATH = re.compile(r"/opa/pr/")


class DojFcpaActionsAdapter(SourceAdapter):
    source_id = "doj_fcpa_actions"
    kind = "event_list"
    url = CURRENT_YEAR_URL

    years: ClassVar[tuple[int, ...]] = (2025, 2026)

    @property
    def urls(self) -> tuple[str, ...]:
        return tuple(YEAR_URL_TEMPLATE.format(year=y) for y in self.years)

    def parse(self, html: str, client: Any) -> list[EventRecord]:
        soup = BeautifulSoup(html, "html.parser")
        body = soup.select_one("div.field_body")
        if body is None:
            return []

        records: list[EventRecord] = []
        for indent in body.select("p.Indent1"):
            record = self._build_record(indent, client)
            if record is not None:
                records.append(record)
        return records

    def _build_record(self, indent: Tag, client: Any) -> EventRecord | None:
        caption_p = indent.find_previous_sibling("p")
        if not isinstance(caption_p, Tag):
            return None
        link = caption_p.find("a")
        if not isinstance(link, Tag):
            return None
        href = link.get("href")
        if not isinstance(href, str):
            return None

        absolute_url = urljoin(self.url, href)
        title = link.get_text(strip=True)
        metadata_text = indent.get_text(separator="\n", strip=True)
        case_no = _extract_field(metadata_text, "Case No:")
        district = _extract_field(metadata_text, "District:")
        event_date = _parse_filed_date(_extract_field(metadata_text, "Filed:"))

        metadata: dict[str, Any] = {}
        if case_no:
            metadata["case_number"] = case_no
        if district:
            metadata["district"] = district

        enrichment = _fetch_enrichment(client, absolute_url)
        metadata.update(enrichment)

        return EventRecord(
            dedup_key=absolute_url,
            source_id=self.source_id,
            event_date=event_date,
            title=title,
            primary_actor=_strip_caption_prefix(title),
            summary=enrichment.get("press_release_title"),
            url=absolute_url,
            country="US",
            metadata=metadata,
        )


def _fetch_enrichment(client: Any, case_url: str) -> dict[str, Any]:
    """Best-effort: case-detail page → press-release URL → press release.

    Any failure returns whatever has been collected so far. Enrichment is
    incidental to the basic record, so silent fail-soft is correct.
    """
    try:
        case_resp = client.get(case_url)
        if case_resp.status_code != 200:
            return {}
        case_soup = BeautifulSoup(case_resp.text, "html.parser")
        pr_link = case_soup.find("a", href=_PRESS_RELEASE_PATH)
        if not isinstance(pr_link, Tag):
            return {}
        pr_href = pr_link.get("href")
        if not isinstance(pr_href, str):
            return {}
        pr_url = urljoin(case_url, pr_href)

        pr_resp = client.get(pr_url)
        if pr_resp.status_code != 200:
            return {"press_release_url": pr_url}
        return _parse_press_release(pr_resp.text, pr_url)
    except Exception:
        return {}


def _parse_press_release(html: str, pr_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    metadata: dict[str, Any] = {"press_release_url": pr_url}

    pr_title_el = soup.select_one("span.field-formatter--string")
    pr_title = pr_title_el.get_text(strip=True) if isinstance(pr_title_el, Tag) else None
    if pr_title:
        metadata["press_release_title"] = pr_title

    topic = _join_field_items(soup.select_one("div.node-topics"))
    if topic:
        metadata["topic"] = topic

    component = _join_field_items(soup.select_one("div.node-component"))
    if component:
        metadata["component"] = component

    body_el = soup.select_one("div.field_body")
    body_text = body_el.get_text(separator=" ", strip=True) if isinstance(body_el, Tag) else ""

    industry = _detect_first(body_text, INDUSTRY_KEYWORDS)
    if industry:
        metadata["industry"] = industry

    resolution = _detect_resolution(body_text)
    if resolution:
        metadata["resolution_type"] = resolution

    amount = _extract_first_amount_usd(body_text)
    if amount is not None:
        metadata["amount_usd"] = amount

    return metadata


def _join_field_items(container: Tag | None) -> str | None:
    if not isinstance(container, Tag):
        return None
    items = [
        item.get_text(strip=True)
        for item in container.select(".field__item")
        if isinstance(item, Tag) and item.get_text(strip=True)
    ]
    return ", ".join(items) if items else None


def _detect_first(text: str, options: Iterable[tuple[str, str]]) -> str | None:
    lowered = text.lower()
    for needle, label in options:
        if needle in lowered:
            return label
    return None


def _detect_resolution(text: str) -> str | None:
    for pattern, label in RESOLUTION_PATTERNS:
        if pattern.search(text):
            return label
    return None


def _extract_first_amount_usd(text: str) -> int | None:
    match = _AMOUNT_RE.search(text)
    if match is None:
        return None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = (match.group(2) or "").lower()
    multiplier = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}.get(
        suffix, 1
    )
    return int(amount * multiplier)


def _extract_field(text: str, label: str) -> str | None:
    for line in text.split("\n"):
        if line.startswith(label):
            return line[len(label) :].strip() or None
    return None


def _parse_filed_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%B %d, %Y").date()
    except ValueError:
        return None


def _strip_caption_prefix(title: str) -> str | None:
    stripped = _CAPTION_PREFIX.sub("", title).strip()
    return stripped or None
