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

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from lawtracker import llm
from lawtracker.llm_cache import JsonCache
from lawtracker.sources import EventRecord

DEFAULT_CACHE_PATH = Path("data/scout/.cache/summaries.json")

SUMMARY_SYSTEM = (
    "You read FCPA / anti-corruption articles and either summarize them "
    "or flag them as event-noise so they can be dropped from the table.\n\n"
    "For each article:\n\n"
    "1. If the article is PRIMARILY an advertisement, recording, or recap "
    "of a non-substantive event — podcast episode, webinar, CLE webcast, "
    "conference promo, networking gathering, panel discussion, fireside "
    "chat, awards announcement, etc. — respond with:\n"
    '   {"drop": true, "reason": "<short phrase>"}\n\n'
    "2. Otherwise, write a 1-2 sentence summary capturing: who is "
    "involved, what happened, why it matters for FCPA practitioners. Be "
    "specific about names, industries, agencies, and dollar amounts when "
    "present. No hedging, no filler. Respond with:\n"
    '   {"drop": false, "summary": "<your summary>"}\n\n'
    "Return ONLY the JSON object — no markdown fences, no prose before "
    "or after."
)

SUMMARY_USER_TEMPLATE = """\
Summarize this article or flag it as event-noise.

Title: {title}
Source: {source_id}{country_suffix}
Date: {event_date}

Article body:

{body}

Respond with a single JSON object: either {{"drop": true, "reason": "..."}} \
or {{"drop": false, "summary": "..."}}.
"""


@dataclass(frozen=True)
class _LlmDecision:
    drop: bool
    summary: str | None
    reason: str | None


def enrich_summaries(
    events: list[EventRecord],
    cache: JsonCache | None = None,
    fetch_article_text: Any = None,
    on_event: Any = None,
) -> list[EventRecord]:
    """Populate `event.summary` from the cache or by calling the LLM.

    The LLM also classifies each article as event-noise (podcast, webinar,
    conference ad, etc.) — flagged events are dropped from the returned
    list. Both decisions (keep + summary, or drop + reason) are cached so
    repeat runs don't re-evaluate the same articles.

    Original (pre-LLM) summary, if any, is preserved in
    `metadata["summary_source"]` for reference.

    `on_event(event, status, detail="")` callback fires once per event
    with status ∈ {`cached`, `cached-drop`, `llm-keep`, `llm-drop`,
    `failed`, `off`}. Used by the scout for live progress output in
    anthropic mode.
    """
    if cache is None:
        cache = JsonCache(DEFAULT_CACHE_PATH)

    fetch = fetch_article_text or _fetch_article_text
    mode = _current_mode()

    def _notify(event: EventRecord, status: str, detail: str = "") -> None:
        if on_event is not None:
            on_event(event, status, detail)

    enriched: list[EventRecord] = []
    for event in events:
        if mode == "off":
            _notify(event, "off")
            enriched.append(event)
            continue

        cache_key = summary_cache_key(event)
        cached_raw = cache.get(cache_key)
        decision = _decision_from_cache(cached_raw)
        from_cache = decision is not None

        if decision is None:
            decision = _generate_decision(event, fetch)
            if decision is not None:
                cache.put(cache_key, _decision_to_cache(decision, event.url, mode))

        if decision is None:
            _notify(event, "failed", "fetch or LLM error; keeping prior summary")
            enriched.append(event)
            continue

        if decision.drop:
            label = "cached-drop" if from_cache else "llm-drop"
            _notify(event, label, decision.reason or "")
            continue

        if decision.summary:
            label = "cached" if from_cache else "llm-keep"
            _notify(event, label)
            enriched.append(_apply_summary(event, decision.summary))
        else:
            _notify(event, "failed", "no summary in decision")
            enriched.append(event)
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


def _generate_decision(event: EventRecord, fetch: Any) -> _LlmDecision | None:
    mode = _current_mode()
    if mode == "stub":
        # Stub mode: no LLM call, no fetch. Always returns drop=False so
        # the pipeline runs end-to-end during design iteration.
        return _LlmDecision(drop=False, summary=_stub_summary(event), reason=None)

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
        stub=_stub_decision_json(event),
        max_tokens=400,
    )
    return _parse_decision(raw)


def _stub_decision_json(event: EventRecord) -> str:
    """JSON-shaped stub matching the real-mode response format."""
    return json.dumps({"drop": False, "summary": _stub_summary(event)})


def _parse_decision(raw: str) -> _LlmDecision | None:
    """Parse a JSON `{"drop": ..., "summary"|"reason": ...}` response.

    Tolerates a markdown code fence around the JSON (some models add one
    despite instructions). On parse failure, treats the raw text as a
    summary (fail-soft — don't lose the LLM's work to formatting issues).
    """
    text = _strip_code_fence(raw).strip()
    if not text:
        return None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _LlmDecision(drop=False, summary=text, reason=None)

    if not isinstance(data, dict):
        return _LlmDecision(drop=False, summary=text, reason=None)

    if data.get("drop") is True:
        reason = data.get("reason")
        return _LlmDecision(
            drop=True,
            summary=None,
            reason=str(reason) if isinstance(reason, str) else None,
        )

    summary = data.get("summary")
    if isinstance(summary, str) and summary.strip():
        return _LlmDecision(drop=False, summary=summary.strip(), reason=None)

    # Malformed: drop=false but no usable summary.
    return _LlmDecision(drop=False, summary=text, reason=None)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _decision_from_cache(entry: Any) -> _LlmDecision | None:
    """Read a cache entry into a decision. Backward-compatible with the
    pre-drop-aware schema (entries with `summary` but no `drop` field)."""
    if not isinstance(entry, dict):
        return None
    if entry.get("drop") is True:
        return _LlmDecision(
            drop=True,
            summary=None,
            reason=str(entry.get("reason") or "") or None,
        )
    summary = entry.get("summary")
    if isinstance(summary, str) and summary.strip():
        return _LlmDecision(drop=False, summary=summary, reason=None)
    return None


def _decision_to_cache(
    decision: _LlmDecision, url: str, mode: str
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "url": url,
    }
    if decision.drop:
        return {**base, "drop": True, "reason": decision.reason}
    return {**base, "drop": False, "summary": decision.summary}


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
