"""SEC FCPA enforcement actions adapter — LLM-extracted from narrative page.

Source #6 in `design/sources.md`. The SEC's FCPA cases page is a single
long narrative document — year headers (`<h2>`/`<h3>` "2024", "2023", …)
followed by free-text paragraphs with bolded company names and embedded
date strings like `(12/19/2024)`. Regex-based extraction would be brittle;
this adapter sends the recent slice to Claude (or a stub during design
iteration) and parses structured `EventRecord`s out of the JSON response.

Scope per Ellen 2026-04-25: only the most recent 1-2 years are relevant
for trend identification. The adapter slices the page to the current
year + previous year before sending it to the LLM, dropping older history.

Cloudflare-fingerprint-blocked when fetched with httpx, so
`use_curl_cffi = True`.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from bs4 import BeautifulSoup

from lawtracker import llm
from lawtracker.sources.base import EventRecord, PollResult, SourceAdapter

_SEC_URL = "https://www.sec.gov/enforce/sec-enforcement-actions-fcpa-cases"

_RECENT_N_YEARS_DEFAULT: int = 2

SEC_SYSTEM = (
    "You are a structured-data extraction assistant. The user will give you "
    "an HTML or plain-text excerpt from the SEC's FCPA enforcement-actions "
    "page. Each entry on that page is a paragraph naming a defendant in bold "
    "and describing a civil enforcement action — typically with a date in "
    "parentheses like (12/19/2024) and links to the SEC order or litigation "
    "release. Extract one record per entry. Return ONLY a JSON array — no "
    "prose before or after."
)

SEC_USER_TEMPLATE = """\
Extract every SEC FCPA enforcement action mentioned in the excerpt below into a JSON array. \
For each entry produce an object with these keys:

- `title`: the case caption or short headline. If the entry begins with a bolded company name, \
use "SEC v. {{Company}}" (or "SEC v. {{Individual}}" for individual defendants).
- `event_date`: ISO date (YYYY-MM-DD) parsed from the parenthetical date in the entry. Use \
null only if no date is present.
- `primary_actor`: the defendant company or individual name as plain text.
- `summary`: a one-sentence description of the action and resolution.
- `detail_url`: absolute URL of the linked SEC order / litigation release if one is given; \
null otherwise.
- `metadata`: an object with optional keys: `action_type` (e.g. "administrative_proceeding", \
"civil_action", "settled_administrative"), `disgorgement_usd` (integer), `civil_penalty_usd` \
(integer), `country` (where the alleged conduct occurred), `industry`.

Output requirements:
- Return ONLY valid JSON. Start with `[`. End with `]`. No markdown fences, no prose.
- If no entries are found, return `[]`.

Excerpt:

```
{excerpt}
```
"""

_STUB_SEC_RECORDS: list[dict[str, Any]] = [
    {
        "title": "[STUB] SEC v. Example Aerospace Corp.",
        "event_date": "2025-12-19",
        "primary_actor": "Example Aerospace Corp.",
        "summary": (
            "[STUB] Settled administrative proceeding; agreed to ~$30M in disgorgement "
            "and prejudgment interest for FCPA anti-bribery and books-and-records "
            "violations involving payments to officials in two foreign jurisdictions."
        ),
        "detail_url": "https://www.sec.gov/litigation/admin/2025/example-aerospace.pdf",
        "metadata": {
            "action_type": "administrative_proceeding",
            "disgorgement_usd": 30000000,
            "country": "PH",
            "industry": "aerospace",
        },
    },
    {
        "title": "[STUB] SEC v. Jane Doe (former director, Example Energy Ltd.)",
        "event_date": "2025-11-20",
        "primary_actor": "Jane Doe",
        "summary": (
            "[STUB] Civil complaint charging a former director with authorizing bribes "
            "in connection with a multi-billion-dollar energy contract scheme."
        ),
        "detail_url": "https://www.sec.gov/litigation/complaints/2025/example-doe.pdf",
        "metadata": {
            "action_type": "civil_action",
            "country": "IN",
            "industry": "energy",
        },
    },
]

_STUB_RESPONSE = json.dumps(_STUB_SEC_RECORDS, indent=2)


class SecFcpaCasesAdapter(SourceAdapter):
    source_id = "sec_fcpa_cases"
    kind = "event_list"
    url = _SEC_URL
    country = "US"
    use_curl_cffi = True

    recent_n_years: int = _RECENT_N_YEARS_DEFAULT

    def parse(self, html: str, client: Any) -> list[EventRecord]:
        excerpt = _slice_to_recent_years(html, self.recent_n_years)
        if not excerpt:
            return []

        prompt = SEC_USER_TEMPLATE.format(excerpt=excerpt)
        response = llm.complete(
            system=SEC_SYSTEM,
            user=prompt,
            stub=_STUB_RESPONSE,
            max_tokens=4096,
        )
        return _records_from_llm_response(response)

    def _fetch_one(self, client: Any, url: str) -> PollResult:
        # SEC may return a 301/302 redirect to its current canonical path.
        # The base implementation follows redirects (httpx) / impersonates a
        # browser (curl_cffi), so the standard flow is fine. Override only
        # exists here as a hook if SEC ever needs special handling.
        return super()._fetch_one(client, url)


def _slice_to_recent_years(html: str, n_years: int) -> str:
    """Reduce the SEC narrative to the most recent N years that appear.

    The page is laid out as `<h2>2024</h2><p>...entries...</p><h2>2023</h2>...`
    The text version looks like isolated year lines (`^2024$`) with case
    paragraphs in between. This finds the highest year present in the page
    and slices from there through the year that's `n_years - 1` older,
    dropping anything older.

    Auto-adapts to whatever years SEC has published — no need to update
    a hardcoded year tuple at calendar rollover. When SEC hasn't yet
    published current year, the slice still grabs the most recent two
    available.

    Returns plain text; the LLM doesn't need surrounding HTML chrome.
    """
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup.find("main") or soup.body
    if article is None:
        return ""
    text = article.get_text(separator="\n", strip=True)

    year_lines = re.findall(r"(?m)^\s*(20\d{2})\s*$", text)
    if not year_lines:
        return ""

    available_years = sorted({int(y) for y in year_lines}, reverse=True)
    if not available_years:
        return ""

    target_years = available_years[:n_years]
    latest = target_years[0]
    earliest = target_years[-1]

    pattern_start = re.compile(rf"(?m)^\s*{latest}\s*$")
    start_match = pattern_start.search(text)
    if start_match is None:
        return ""

    pattern_end = re.compile(rf"(?m)^\s*{earliest - 1}\s*$")
    end_match = pattern_end.search(text, start_match.end())
    end_idx = end_match.start() if end_match else len(text)

    excerpt = text[start_match.start() : end_idx].strip()
    return excerpt[:30000]


def _records_from_llm_response(response: str) -> list[EventRecord]:
    """Parse the LLM's JSON response into EventRecords. Fail-soft."""
    if not response or not response.strip():
        return []
    try:
        payload = json.loads(_strip_code_fence(response))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    records: list[EventRecord] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        record = _record_from_raw(raw)
        if record is not None:
            records.append(record)
    return records


def _strip_code_fence(text: str) -> str:
    """Models sometimes wrap JSON in ```json …```; strip the fence."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _record_from_raw(raw: dict[str, Any]) -> EventRecord | None:
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    detail_url = raw.get("detail_url") or raw.get("url") or ""
    if not isinstance(detail_url, str):
        detail_url = ""

    event_date_str = raw.get("event_date")
    event_date = _parse_iso_date(event_date_str) if isinstance(event_date_str, str) else None

    metadata_raw = raw.get("metadata") or {}
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
    action_type = metadata.get("action_type") if isinstance(metadata, dict) else None
    if isinstance(action_type, str):
        metadata = {**metadata, "action_type": action_type}

    primary_actor = raw.get("primary_actor")
    summary = raw.get("summary")

    dedup_key = detail_url if detail_url else _fallback_dedup_key(title, event_date)

    return EventRecord(
        dedup_key=dedup_key,
        source_id="sec_fcpa_cases",
        event_date=event_date,
        title=title.strip(),
        primary_actor=primary_actor if isinstance(primary_actor, str) else None,
        summary=summary if isinstance(summary, str) else None,
        url=detail_url if detail_url else _SEC_URL,
        country="US",
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _fallback_dedup_key(title: str, event_date: date | None) -> str:
    if event_date:
        return f"sec:{event_date.isoformat()}:{title}"
    return f"sec:{title}"
