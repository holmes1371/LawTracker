"""Miller & Chevalier — FCPA / International Anti-Corruption practice search.

The firm doesn't expose RSS, but its Drupal-driven `/search` endpoint accepts
filter parameters that pin results to the FCPA practice area
(`related_practice=8965`). The adapter fetches three content types in one
poll — publications, news, and events — by overriding the `urls` property.

Signal value:
- **Publications** — the FCPA Winter / Spring / Summer / Autumn Reviews
  Tom flagged in `possibleSources.txt` are here, plus client alerts and
  enforcement-update memos. Highest-signal of the three.
- **News** — items mentioning the firm in press, awards, lateral moves.
- **Events** — speaking engagements at industry conferences. Lower signal
  for enforcement trends but useful for "what topics are practitioners
  discussing right now."

Each search result renders as `<div class="search_result">` with:
  - `.search_result__header--date time[datetime]` — ISO datetime
  - `.search_result__header--title a` — title and href to detail page
  - optional `.field--name-field-event-type` — sub-type label
    (e.g. "Speaking Engagement", "Article", "News Mention")

Content type is detected from the result URL slug (`/publication/`,
`/news/`, `/event/`) so the parser doesn't need to know which of the
three URLs it's parsing.
"""

from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from lawtracker.sources.base import EventRecord, SourceAdapter

_BASE = "https://www.millerchevalier.com"
_SEARCH_BASE = (
    _BASE
    + "/search?search_term=&related_practice=8965&related_professional=any"
    "&related_subject=any&related_region=any&date_from=&date_to=&view_more=1"
)
_CONTENT_TYPES: tuple[str, ...] = ("publication", "news", "event")


class MillerChevalierFcpaAdapter(SourceAdapter):
    source_id = "miller_chevalier_fcpa"
    kind = "event_list"
    url = f"{_SEARCH_BASE}&content_types%5B0%5D=publication"
    country = "US"
    use_curl_cffi = True

    @property
    def urls(self) -> tuple[str, ...]:
        return tuple(f"{_SEARCH_BASE}&content_types%5B0%5D={ct}" for ct in _CONTENT_TYPES)

    def parse(self, html: str, client: Any) -> list[EventRecord]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[EventRecord] = []
        for card in soup.select("div.search_result"):
            title_link = card.select_one(".search_result__header--title a")
            if not isinstance(title_link, Tag):
                continue
            href = title_link.get("href")
            if not isinstance(href, str):
                continue
            absolute_url = urljoin(_BASE, href)

            title = title_link.get_text(strip=True)
            event_date = _parse_time_attr(card.select_one("time.datetime"))
            content_type = _content_type_from_href(href)

            sub_type_el = card.select_one(".field--name-field-event-type")
            sub_type = sub_type_el.get_text(strip=True) if isinstance(sub_type_el, Tag) else None

            metadata: dict[str, str] = {"content_type": content_type}
            if sub_type:
                metadata["sub_type"] = sub_type

            records.append(
                EventRecord(
                    dedup_key=absolute_url,
                    source_id=self.source_id,
                    event_date=event_date,
                    title=title,
                    primary_actor=None,
                    summary=None,
                    url=absolute_url,
                    country=self.country,
                    metadata=metadata,
                )
            )
        return records


def _parse_time_attr(tag: Tag | None) -> date | None:
    if not isinstance(tag, Tag):
        return None
    raw = tag.get("datetime")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _content_type_from_href(href: str) -> str:
    for prefix in ("/publication/", "/news/", "/event/"):
        if href.startswith(prefix):
            return prefix.strip("/")
    return "unknown"
