"""DOJ FCPA enforcement actions adapter.

Source #5 in `design/sources.md`. The URL targets the **current-year**
chronological list page; DOJ's per-year URL pattern is stable but the year
in the path needs to roll over each January. The adapter URL is a class
attribute and an explicit constant below — update both at year rollover.

The landing page at `/criminal-fraud/related-enforcement-actions` is a
navigation hub (alphabetical + chronological year index), not a case list,
so it is not the adapter's target.

Each case on the year page renders as two adjacent paragraphs:

  <p>... <a href="/criminal/fraud/fcpa/cases/...">United States v. ...</a></p>
  <p class="Indent1">Case No: ...<br>District: ...<br>Filed: Month D, YYYY</p>

The parser pairs them by walking back from each Indent1 paragraph to its
immediately-preceding paragraph carrying the case-caption link.
"""

import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from lawtracker.sources.base import EventRecord, SourceAdapter

CURRENT_YEAR_URL = (
    "https://www.justice.gov/criminal/criminal-fraud/case/related-enforcement-actions/2026"
)


class DojFcpaActionsAdapter(SourceAdapter):
    source_id = "doj_fcpa_actions"
    kind = "event_list"
    url = CURRENT_YEAR_URL

    def parse(self, html: str) -> list[EventRecord]:
        soup = BeautifulSoup(html, "html.parser")
        body = soup.select_one("div.field_body")
        if body is None:
            return []

        records: list[EventRecord] = []
        for indent in body.select("p.Indent1"):
            caption_p = _previous_element(indent, "p")
            if caption_p is None:
                continue
            link = caption_p.find("a")
            if not isinstance(link, Tag):
                continue
            href = link.get("href")
            if not isinstance(href, str):
                continue

            absolute_url = urljoin(self.url, href)
            title = link.get_text(strip=True)
            metadata_text = indent.get_text(separator="\n", strip=True)
            case_no = _extract_field(metadata_text, "Case No:")
            district = _extract_field(metadata_text, "District:")
            event_date = _parse_filed_date(_extract_field(metadata_text, "Filed:"))

            metadata: dict[str, str] = {}
            if case_no:
                metadata["case_number"] = case_no
            if district:
                metadata["district"] = district

            records.append(
                EventRecord(
                    dedup_key=absolute_url,
                    source_id=self.source_id,
                    event_date=event_date,
                    title=title,
                    primary_actor=_strip_caption_prefix(title),
                    summary=None,
                    url=absolute_url,
                    country="US",
                    metadata=metadata,
                )
            )
        return records


def _previous_element(node: Tag, name: str) -> Tag | None:
    sibling = node.find_previous_sibling(name)
    return sibling if isinstance(sibling, Tag) else None


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


_CAPTION_PREFIX = re.compile(r"^(United States|U\.S\.|USA)\s+v\.\s+", re.IGNORECASE)


def _strip_caption_prefix(title: str) -> str | None:
    stripped = _CAPTION_PREFIX.sub("", title).strip()
    return stripped or None
