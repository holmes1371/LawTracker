"""Generic RSS 2.0 / Atom feed adapter.

Subclass with a 4-line declaration to add any RSS-feed source:

    class MyBlogAdapter(RssFeedAdapter):
        source_id = "my_blog"
        kind = "event_list"
        url = "https://example.com/feed/"
        country = None  # or "US", "AU", etc. — the outlet's home jurisdiction

Optional `keyword_filter` (compiled regex) — restricts emitted records
to entries whose title or description matches. Useful when an outlet
covers a broader topic surface than what the scout cares about.

This is the reuse mechanism Tom asked about (2026-04-25) — once new
RSS-feed sources need to be added (law-firm blogs, aggregators, etc.),
each one is a 4-line subclass instead of a full adapter.
"""

import re
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from lawtracker.sources.base import EventRecord, SourceAdapter

DC_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


class RssFeedAdapter(SourceAdapter):
    country: ClassVar[str | None] = None
    keyword_filter: ClassVar[re.Pattern[str] | None] = None

    def parse(self, html: str, client: Any) -> list[EventRecord]:
        root = ET.fromstring(html)

        items = root.findall(".//item")
        if not items:
            items = root.findall(f".//{ATOM_NS}entry")
        if not items:
            return []

        records: list[EventRecord] = []
        for item in items:
            title = _first_text(item, ("title", f"{ATOM_NS}title"))
            link = _extract_link(item)
            if title is None or not link:
                continue

            description = _first_text(
                item, ("description", f"{ATOM_NS}summary", f"{ATOM_NS}content")
            )
            haystack = " ".join(filter(None, [title, description]))
            if self.keyword_filter is not None and not self.keyword_filter.search(haystack):
                continue

            pub_date = _first_text(
                item, ("pubDate", f"{ATOM_NS}published", f"{ATOM_NS}updated")
            )
            event_date = _parse_pub_date(pub_date)

            creator = _first_text(item, (DC_CREATOR, f"{ATOM_NS}author/{ATOM_NS}name"))

            categories = [
                el.text.strip()
                for el in item.findall("category")
                if el.text and el.text.strip()
            ]

            metadata: dict[str, str] = {}
            if creator:
                metadata["author"] = creator
            if categories:
                metadata["categories"] = ", ".join(categories)

            records.append(
                EventRecord(
                    dedup_key=link,
                    source_id=self.source_id,
                    event_date=event_date,
                    title=title.strip(),
                    primary_actor=creator,
                    summary=_strip_html(description) if description else None,
                    url=link,
                    country=self.country,
                    metadata=metadata,
                )
            )
        return records


def _first_text(item: ET.Element, paths: tuple[str, ...]) -> str | None:
    for path in paths:
        el = item.find(path)
        if el is not None and el.text:
            return el.text
    return None


def _extract_link(item: ET.Element) -> str | None:
    rss_link = item.find("link")
    if rss_link is not None and rss_link.text:
        return rss_link.text.strip()
    atom_link = item.find(f"{ATOM_NS}link")
    if atom_link is not None:
        href = atom_link.get("href")
        if href:
            return href.strip()
    return None


def _parse_pub_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (ValueError, TypeError):
        return None


def _strip_html(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
