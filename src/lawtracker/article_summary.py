"""Per-event article summarization with disk-backed cache.

Ellen 2026-04-25: "The LLM will need to go into each of the articles
and provide a summary - we should have a caching system so it doesn't
have to reevaluate the same article multiple times and it knows to skip
over articles that have already been analyzed."

For each event, this:

1. Looks up `summary_cache_key(event)` in the cache (mode-stamped).
2. Cache hit → reuse the cached summary verbatim.
3. Cache miss → generate a summary:
   - **stub mode** (default): synthesize a deterministic placeholder
     from event metadata. No HTTP fetch, no API spend. Visible at a
     glance because it's prefixed `[STUB summary]`.
   - **anthropic mode**: fetch the article via curl_cffi (handles both
     plain-vanilla sites and Cloudflare-protected ones), strip chrome,
     send title + body to Claude, return the response.
   - **off mode**: leave existing summary unchanged.
4. Write the cache entry, mutate the event with the new summary.

Cache keys include the mode so stubs and anthropic summaries don't mix:
`stub|<dedup_key>` vs `anthropic|<dedup_key>`. Switching modes
re-summarizes only what's missing in that mode's cache.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from lawtracker import llm
from lawtracker.llm_cache import JsonCache
from lawtracker.sources import EventRecord

DEFAULT_CACHE_PATH = Path("data/scout/.cache/summaries.json")

SUMMARY_SYSTEM = (
    "You summarize FCPA / anti-corruption articles for senior compliance "
    "lawyers and corporate risk-and-audit committee members. Read the "
    "article and write 1-2 sentences capturing: who is involved, what "
    "happened, why it matters for FCPA practitioners. Be specific with "
    "names, industries, agencies, and dollar amounts when present. "
    "No hedging. No filler. No preamble — return only the summary."
)

SUMMARY_USER_TEMPLATE = """\
Summarize the article below in 1-2 sentences for FCPA practitioners.

Title: {title}
Source: {source_id}{country_suffix}
Date: {event_date}

Article body:

{body}
"""


def enrich_summaries(
    events: list[EventRecord],
    cache: JsonCache | None = None,
    fetch_article_text: Any = None,
) -> list[EventRecord]:
    """Populate `event.summary` from the cache or by calling the LLM.

    Returns a new list with possibly-mutated `EventRecord`s. Cache is
    written through inside this function. Original (pre-LLM) summary,
    if any, is preserved in `metadata["summary_source"]` for reference.
    """
    if cache is None:
        cache = JsonCache(DEFAULT_CACHE_PATH)

    fetch = fetch_article_text or _fetch_article_text
    mode = _current_mode()

    enriched: list[EventRecord] = []
    for event in events:
        if mode == "off":
            enriched.append(event)
            continue

        cache_key = summary_cache_key(event)
        cached_entry = cache.get(cache_key)
        cached_summary: str | None = None
        if isinstance(cached_entry, dict):
            value = cached_entry.get("summary")
            if isinstance(value, str) and value.strip():
                cached_summary = value

        if cached_summary is not None:
            enriched.append(_apply_summary(event, cached_summary))
            continue

        new_summary = _generate_summary(event, fetch)
        if new_summary is None:
            enriched.append(event)
            continue

        cache.put(
            cache_key,
            {
                "summary": new_summary,
                "mode": mode,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "url": event.url,
            },
        )
        enriched.append(_apply_summary(event, new_summary))
    return enriched


def summary_cache_key(event: EventRecord) -> str:
    return f"{_current_mode()}|{event.dedup_key}"


def _current_mode() -> str:
    return os.environ.get("LAWTRACKER_LLM_MODE", "stub").lower()


def _apply_summary(event: EventRecord, summary: str) -> EventRecord:
    new_metadata = dict(event.metadata)
    if event.summary and event.summary != summary and "summary_source" not in new_metadata:
        new_metadata["summary_source"] = event.summary
    return event.model_copy(update={"summary": summary, "metadata": new_metadata})


def _generate_summary(event: EventRecord, fetch: Any) -> str | None:
    mode = _current_mode()
    if mode == "stub":
        return _stub_summary(event)

    body = fetch(event.url)
    if not body:
        return None

    user_prompt = SUMMARY_USER_TEMPLATE.format(
        title=event.title,
        source_id=event.source_id,
        country_suffix=f" ({event.country})" if event.country else "",
        event_date=event.event_date.isoformat() if event.event_date else "unknown",
        body=body[:8000],
    )
    raw = llm.complete(
        system=SUMMARY_SYSTEM,
        user=user_prompt,
        stub=_stub_summary(event),
        max_tokens=300,
    )
    text = raw.strip()
    return text or None


def _stub_summary(event: EventRecord) -> str:
    parts = ["[STUB summary]"]
    if event.country:
        parts.append(f"({event.country})")
    parts.append(f"Article from `{event.source_id}`.")
    if event.event_date:
        parts.append(f"Dated {event.event_date.isoformat()}.")
    parts.append(
        f"Title: {event.title[:120]}{'…' if len(event.title) > 120 else ''}"
    )
    parts.append(
        "Real Claude would read the article body and produce 1-2 sentences here."
    )
    return " ".join(parts)


def _fetch_article_text(url: str) -> str | None:
    """Fetch an article URL and return readable body text. Fail-soft.

    Uses curl_cffi (Chrome-impersonating TLS) so the same call handles
    both plain sites and Cloudflare-protected ones with one path.
    """
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        return None

    try:
        with curl_requests.Session(impersonate="chrome120", timeout=20) as session:
            response = session.get(url)
            if response.status_code != 200:
                return None
            return _extract_body_text(response.text)
    except Exception:
        return None


def _extract_body_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    body = soup.find("article") or soup.find("main") or soup.body or soup
    return body.get_text(separator=" ", strip=True)
