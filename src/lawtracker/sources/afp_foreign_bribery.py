"""AFP foreign-bribery adapter.

Source #10 in `design/sources.md`. Discovery during build (2026-04-25):
the AFP general media-releases page (`/news-media/media-releases`) is
*not* a viable source — across 30 pages of recent releases there are
zero foreign-bribery hits. Foreign bribery is a small fraction of AFP's
overall enforcement work, and the topic landing at
`/crimes/fraud-and-corruption` only shows ~4 recent items, mostly
domestic NDIS / fraud content.

The viable surface is AFP's site search:
`https://www.afp.gov.au/search?keys=foreign+bribery`. It returns mixed
results — some are static crime-type landing pages, others are media
releases. The adapter filters to `/news-centre/` URLs to keep only
actual news items.

Each search result renders inside `<div class="views-row">` with a
`search-result__date` (carries an ISO datetime), a
`search-result__category` (e.g. "Fraud and corruption"), a
`search-result__title` containing an `<a href="/news-centre/...">`,
and a `search-result__description` with a highlighted excerpt.
"""

from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from lawtracker.sources.base import EventRecord, SourceAdapter


class AfpForeignBriberyAdapter(SourceAdapter):
    source_id = "afp_foreign_bribery"
    kind = "event_list"
    url = "https://www.afp.gov.au/search?keys=foreign+bribery"

    def parse(self, html: str, client: Any) -> list[EventRecord]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[EventRecord] = []
        for row in soup.select("div.views-row"):
            title_link = row.select_one(".search-result__title a")
            if not isinstance(title_link, Tag):
                continue
            href = title_link.get("href")
            if not isinstance(href, str) or "/news-centre/" not in href:
                continue

            title = title_link.get_text(strip=True)
            absolute_url = urljoin(self.url, href)

            event_date = _parse_datetime_attr(row.select_one("time.datetime"))
            category = _text_of(row.select_one(".search-result__category a"))
            excerpt = _text_of(row.select_one(".search-result__description"))

            metadata: dict[str, str] = {}
            if category:
                metadata["category"] = category

            records.append(
                EventRecord(
                    dedup_key=absolute_url,
                    source_id=self.source_id,
                    event_date=event_date,
                    title=title,
                    primary_actor=None,
                    summary=excerpt,
                    url=absolute_url,
                    country="AU",
                    metadata=metadata,
                )
            )
        return records


def _parse_datetime_attr(tag: Tag | None) -> date | None:
    if not isinstance(tag, Tag):
        return None
    raw = tag.get("datetime")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def _text_of(tag: Tag | None) -> str | None:
    if not isinstance(tag, Tag):
        return None
    text = tag.get_text(separator=" ", strip=True)
    return text or None
