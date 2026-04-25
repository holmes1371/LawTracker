# LawTracker — Source adapter framework (item 3)

Status: in flight 2026-04-25. Plan approved by Tom in conversation that day. First design note under `design/` for an implementation item.

## Scope

**In:**

- `src/lawtracker/sources/__init__.py`, `base.py` — `SourceAdapter` ABC, `PollResult`, `PollStatus`, `EventRecord`.
- `src/lawtracker/sources/doj_fcpa_actions.py` — first concrete adapter (source #5 in `design/sources.md`).
- `tests/fixtures/doj_fcpa_actions.html` — committed snapshot of the live page for offline parser tests.
- `tests/test_sources_base.py`, `tests/test_doj_fcpa_actions.py`.
- This design note.

**Out (defers to a later item):**

- SQLAlchemy models, Alembic migrations, any DB writes — item 4.
- The `document`-kind half of the framework (DOJ Resource Guide, ECCP, etc.) — `PollResult.snapshot` slot will be added by item 4 when the first document adapter lands; not predeclared now.
- Poll loop / scheduler — item 5.
- Live network fetches in the default test suite. One opt-in smoke test gated by `@pytest.mark.live` for ad-hoc verification.
- Cross-source dedup (e.g. DOJ press releases overlapping with FCPA actions) — separate concern post-storage.
- Link-following enrichment for DOJ FCPA actions (fetching each case-detail page for penalty / defendant / etc.). v1 is **list-page-only**; if Ellen needs richer rows, file a follow-up item.

## Decisions

### 1. Adapter signals fetch outcome, not change detection

`SourceAdapter.poll()` returns `PollResult(status, events, error)`:

- `status: Literal["ok", "transient_failure", "permanent_failure"]`
- `events: list[EventRecord]` (empty unless `status == "ok"`)
- `error: str | None`

Reasoning: "no change" is the storage layer's call (item 4 set-reconciles dedup keys against persisted state). The adapter's only job is to return what it observed.

- `ok` — fetch + parse succeeded. `events` is the full set as observed (may legitimately be empty).
- `transient_failure` — network error, 5xx, timeout. Poll loop retries on next cadence; nothing surfaces to the user.
- `permanent_failure` — 4xx, parse error, structural mismatch. Loud log; surface in dashboard once item 6 lands.

No exceptions in the happy path. The base class wraps fetches and converts `httpx.RequestError` and unexpected parse errors into the appropriate status.

### 2. Per-source dedup keys

Each `EventRecord` carries a `dedup_key: str` the adapter computes. Recommended pattern (in the ABC docstring): use the canonical detail URL when stable; otherwise hash a stable subset of fields (typically `title + listed_date`). Item 4's reconcile logic stays generic — it just compares dedup keys.

DOJ FCPA actions adapter (first adapter): dedup key = absolute URL of the case-detail page or press-release link.

### 3. Source-specific metadata as a JSON-friendly dict

`EventRecord.metadata: dict[str, Any]`. Item 4 maps it to a JSON column on `LawEvent`. Each adapter populates whatever it can extract cheaply; no fixed schema. DOJ FCPA actions example keys: `defendant_type`, `resolution_type`, `case_number`, `district`, `penalty_usd`, `disgorgement_usd`, `industry`, `parallel_sec_action`. Most of these require link-following enrichment, which is out of scope for v1.

### 4. Universal `EventRecord` fields

Promoted to first-class because every event-list adapter must answer them, and the dashboard / search / filter renders against them uniformly:

| Field | Type | Notes |
|---|---|---|
| `dedup_key` | `str` | Per-source; see decision 2. |
| `source_id` | `str` | Adapter's own identifier (e.g. `"doj_fcpa_actions"`). Set from class attribute. |
| `event_date` | `date \| None` | When the event happened (filed / announced / dated). `None` only when the source genuinely lacks one. |
| `title` | `str` | Display headline. |
| `primary_actor` | `str \| None` | Defendant / respondent / speaker / requestor. `None` when the source has no clean answer. |
| `summary` | `str \| None` | One-line "why it matters" for dashboard preview. Encouraged but not mandatory. |
| `url` | `str` | Canonical primary-source link. |
| `country` | `str \| None` | ISO 3166-1 alpha-2 (`"US"`, `"AU"`, `"CL"`). `None` for multilateral / non-geographic sources (OECD, World Bank, generic speeches). Promoted to first-class on Tom's call 2026-04-25. |
| `metadata` | `dict[str, Any]` | Source-specific structured fields. See decision 3. |

`magnitude_usd` was considered and rejected — kept inside `metadata` per Tom 2026-04-25.

### 5. Unified `SourceAdapter` ABC

Single ABC; subclasses declare `kind` as a class attribute (`"document"` | `"event_list"` | `"both"`). For item 3, `PollResult` carries `events` only. The document side adds a `snapshot` field on `PollResult` when item 4 introduces the first document adapter. No predeclaration of document types now.

Per-source modules under `src/lawtracker/sources/`. Boilerplate (HTTP fetch, status classification, exception → `PollResult` mapping) lives in the base class. Concrete adapters supply only `parse(html: str) -> list[EventRecord]`.

### 6. Test strategy: fixture HTML, deterministic

`tests/fixtures/doj_fcpa_actions.html` is a committed snapshot of the live page. Tests parse the fixture; CI does not hit the network. Reasons: CI determinism (DOJ rate-limiting / outages must not redden the build), regression coverage (when DOJ restructures the page, fixture-vs-live diff is real signal), offline development.

One opt-in live smoke test (`@pytest.mark.live`, env-gated) for ad-hoc verification; not part of the default suite.

## Open questions

None at planning time. All the questions in ROADMAP item 3 (`PollResult` shape vs. fetch failure, dedup-key strategy, metadata persistence) are resolved above.

Anything that surfaces during implementation lands here as an addition before changing direction.

## Test fixtures needed

- `tests/fixtures/doj_fcpa_actions.html` — saved snapshot of `https://www.justice.gov/criminal/criminal-fraud/related-enforcement-actions`. Captured during dev with `curl` or `httpx`, committed. Refresh only when DOJ changes the page structure.

## External-service walkthrough

N/A — item 3 is local Python with one HTTP fetch from the public DOJ site. No accounts, secrets, DNS, or external service setup required from Tom.

## Commit sequence

Per ROADMAP discipline (status flip lands with the first artifact):

1. **Design note + ROADMAP `[ ]` → `[~]` for item 3.** This commit.
2. **`SourceAdapter` ABC + `PollResult` + `EventRecord`** in `src/lawtracker/sources/base.py`, plus `tests/test_sources_base.py` covering the four `PollResult` paths (ok / transient / permanent / parse-error).
3. **DOJ FCPA actions adapter + fixture HTML + adapter tests.**

The "Last session summary" block in `ROADMAP.md` is updated between each commit so a fresh-session pickup is clean.
