"""Fiscalía Nacional de Chile adapter (Spanish).

Source #12 in `design/sources.md`. Discovery during build (2026-04-25):
the URL marked approximate in the source inventory (`/Fiscalia/sala_prensa`)
is a 404. Fiscalía moved its press section to `/actualidad/noticias/...`.

The adapter targets the *nacionales* news page. The page lists every
type of case Fiscalía publishes — homicide, drugs, organized crime,
public-sector corruption, etc. The adapter applies a Spanish-language
keyword filter (`cohecho`, `corrupción`, `soborno`, `lavado`, `fraude`,
`Ley 20.393`) over title + body so that only anti-corruption-relevant
items make it into the scout.

Anti-corruption signal in Fiscalía's national news stream is sparse —
most pages return zero matches. That is itself useful information for
the scout review: it tells Tom + Ellen whether Chile coverage from this
source is viable, or whether a different surface is needed.

Each card on the page renders inside `<div class="views-row">` as a
`<div class="card-new ...">` with a `<p class="fecha">DD/MM/YYYY | Nacional</p>`,
an `<h4 class="title">` containing an `<a href="/actualidad/noticias/...">` whose
text is the headline, and a `<div class="field--name-body">` body summary.
"""

from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from lawtracker.sources._filters import ANTI_CORRUPTION_ES
from lawtracker.sources.base import EventRecord, SourceAdapter

KEYWORDS = ANTI_CORRUPTION_ES


class FiscaliaChileAdapter(SourceAdapter):
    source_id = "fiscalia_chile"
    kind = "event_list"
    url = "https://www.fiscaliadechile.cl/actualidad/noticias/nacionales"

    def parse(self, html: str, client: Any) -> list[EventRecord]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[EventRecord] = []
        for card in soup.select("div.card-new"):
            title_link = card.select_one("h4.title a")
            if not isinstance(title_link, Tag):
                continue
            href = title_link.get("href")
            if not isinstance(href, str):
                continue
            absolute_url = urljoin(self.url, href)

            title_text = title_link.get_text(separator=" ", strip=True)
            body_el = card.select_one(".field--name-body")
            body_text = (
                body_el.get_text(separator=" ", strip=True)
                if isinstance(body_el, Tag)
                else None
            )

            haystack = " ".join(filter(None, [title_text, body_text]))
            if not KEYWORDS.search(haystack):
                continue

            fecha_el = card.select_one("p.fecha")
            event_date, region_tag = _parse_fecha(fecha_el)

            metadata: dict[str, str] = {}
            if region_tag:
                metadata["region"] = region_tag

            records.append(
                EventRecord(
                    dedup_key=absolute_url,
                    source_id=self.source_id,
                    event_date=event_date,
                    title=title_text,
                    primary_actor=None,
                    summary=body_text,
                    url=absolute_url,
                    country="CL",
                    metadata=metadata,
                )
            )
        return records


def _parse_fecha(tag: Tag | None) -> tuple[date | None, str | None]:
    if not isinstance(tag, Tag):
        return None, None
    raw = tag.get_text(separator="|", strip=True)
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    event_date: date | None = None
    region_tag: str | None = None
    if parts:
        try:
            event_date = datetime.strptime(parts[0], "%d/%m/%Y").date()
        except ValueError:
            event_date = None
    if len(parts) > 1:
        region_tag = parts[1]
    return event_date, region_tag
