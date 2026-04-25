# LawTracker — Roadmap

Authoritative backlog for LawTracker, a Python tool to track when specific laws are updated. Edit in place; commit changes alongside code.

Always load the `karpathy-guidelines` skill before starting anything here.

Closed `[x]` items are archived in `COMPLETED.md` with their full post-mortem prose. Stubs below preserve the original numbering so past session summaries and commit messages still resolve.

## Last session summary

This section holds **exactly one block** — the current/most-recent session — and it MUST be short. The next agent needs a cold pickup, not a recap.

Strict rules for writing it:

1. **≤5 bullets, ≤1 sentence each where possible.** Trim ruthlessly. If a bullet needs a paragraph, the real content belongs in a design note or `COMPLETED.md`; link it.
2. **Only what is open, in-flight, or just-filed.** Do NOT restate design decisions, rationale, or commit-by-commit walkthroughs for closed items — those live in `COMPLETED.md`; the next agent can read them if needed.
3. **No standing guidance here.** Commit discipline, status-flag rituals — all of that lives in "For future agents" below. Do not duplicate.
4. **No cross-session carry-overs.** If something is still broken session-to-session, file it as a numbered ROADMAP item instead of repeating it here.
5. **Replace in place.** Do not append a new block and archive the old one below.

**2026-04-25 (item 17 wave 3: law-firm RSS audit + 2 new adapters)**

- Audited ~60 law-firm RSS URLs from `possibleSources.txt` plus alternates. Only **Gibson Dunn** had working RSS (intermittent — Cloudflare blocks httpx in some runs). Most firms hide behind enterprise CMS without RSS, or behind CDN bot rules (Sidley, Skadden, Debevoise, Dentons, HSF, Foley, Covington, Ropes & Gray, etc.).
- Added: `GibsonDunnAdapter` (with `ANTI_CORRUPTION_EN` keyword filter, since the firm's `/feed/` is mixed-topic) and `GlobalAnticorruptionBlogAdapter` (Harvard's academic blog, no filter — single-topic).
- Centralized keyword filters at `src/lawtracker/sources/_filters.py` so Ellen can review/tweak in one place without touching adapter code. Two regexes — `ANTI_CORRUPTION_EN` (FCPA/FEPA/bribery/anti-corruption/AML/OFAC/sanctions/ITAR) and `ANTI_CORRUPTION_ES` (cohecho/corrupción/soborno/lavado/Ley 20.393/funcionario público) — documented in `design/data-scout.md` "Keyword filters in use" section.
- Live scout: 45 events (DOJ 6, AFP 9, Fiscalía 0, Consejo 10, Volkov 10, Gibson Dunn 0 CF-blocked this run, GAB 10). Suite: 33 passing. Ruff + mypy clean. CI workflow already in place.
- Items 3, 11, 16, 17 all `[~]` pending Tom's manual signoff. Items 4 / 5 / 6+ still queued behind item 18 (scout review).
- Next: Ellen reviews the Excel + the keyword-filters section in `design/data-scout.md`. Adjustments either tweak `_filters.py` or add new RSS subclasses; firms on the blocked list need a different access strategy (headless browser, `curl_cffi`, email subscriptions).

## For future agents

Read this file at the start of any session where Tom mentions "LawTracker", "the law tracker", "the roadmap", or asks about the next feature. The prioritization below is settled — do not re-debate it without prompting. Work items in order unless Tom explicitly says otherwise.

Session discipline:

- Invoke the `karpathy-guidelines` skill via the Skill tool at the start of every session that touches code. Reading `reference/guidelines.md` directly does not count — the skill-load step is what anchors the discipline for the rest of the session.
- Before starting a non-trivial feature, write a short design note to `design/{feature-name}.md` capturing the scope, the decisions already made, and the test fixtures needed. A fresh session should be able to pick up mid-feature from that note plus the last commit, without re-litigating choices.
- Commit at every natural boundary, not just at feature completion. Half-finished work behind a clear commit message is recoverable; a dirty worktree is not.
- **Flip `[ ]` → `[~]` as soon as Tom approves the plan for a backlog item — before the design note, before any code.** The status flag tells the next agent what is actually in flight; flipping only at session end means a mid-session interruption leaves the item falsely marked "not started" even though a design note and half the commits exist. Record the flip in whichever commit introduces the first artifact for the item (usually the design note); if the plan is approved but no commit has landed yet, include the flip alongside the first real change so it does not need its own throwaway commit.
- End each session by updating this file — mark in-progress items, note any deviations or follow-ups — and commit the update. **Do not flip an item to `[x]` without explicit user signoff.** When the final code commit for an item lands, leave the item in `[~]`, record the SHA, and summarize what is pending manual verification. Tom pushes, tests manually, and either confirms the close (then the next session flips it to `[x]` with the SHA preserved) or returns feedback to address. Closing on your own reads as premature.
- **Update the "Last session summary" block between each commit during a multi-commit feature, not just at session end.** The block should always reflect what *just* landed and what is next, so a mid-feature handoff — mid-session or across agents — has a clean pickup point. The block is single-slot: replace in place, do not append. Older sessions' context lives in commit messages, `COMPLETED.md`, and `design/*.md`.
- **Closed items live in `COMPLETED.md`, not here.** When Tom signs off a `[~]` item, the next session moves its full prose into `COMPLETED.md` and leaves a one-line stub at the original item number in this file. Original numbers are stable — never renumber. When touching territory that overlaps a completed item, read its full entry in `COMPLETED.md` before re-deriving decisions.
- Tests live in `tests/` and (once CI is wired) run on every push + PR. A red test check blocks merge; do not mark a feature done with tests failing.
- Honor the standing order: deterministic work lives in Python modules; any agent/LLM step does only judgment and interpretation. If a feature tempts you to move mechanical work into agent-handled text, push back.
- **Items that require Tom to set up an external service** (Fly.io account, Squarespace DNS records, GitHub Actions secrets, Resend / Postmark / Twilio accounts, etc.) include a step-by-step walkthrough in the design note: every screen Tom will see, every value to paste, every secret to copy where. Tom is doing this from scratch and a missed step blocks the whole item. Do not assume prior familiarity with any service. When a step requires a value only Tom can produce (account email, payment method, custom domain), call it out explicitly and pause until he confirms it is done before moving on.

Status legend:

- `[ ]` not started
- `[~]` in progress — include a note with what is done and what remains
- `[x]` done — include the commit SHA
- `[-]` descoped / on hold — full prose preserved in "Descoped / on hold" at the bottom for possible future revival

## Backlog (priority order)

1\. [x] Architecture + stack design note — ceec7ec — see COMPLETED.md

2\. [x] Pilot source inventory — ceec7ec — see COMPLETED.md

### 3. [~] Source adapter framework + first adapter

Build the `SourceAdapter` ABC under `src/lawtracker/sources/base.py` plus the first concrete adapter — DOJ FCPA enforcement actions list — end to end. Adapter declares its kind (`document` | `event_list` | `both`) and emits Pydantic records the storage layer can persist. First adapter is the anchor that proves the `event_list` shape; items 6–9 in `design/sources.md` follow the same template.

Plan approved 2026-04-25 — see `design/source-adapter-framework.md`. The three open questions (poll-result shape vs. fetch failure, dedup-key strategy, metadata persistence) are resolved in the design note. `country` promoted to a first-class `EventRecord` field on Tom's call.

### 4. [ ] Storage + change detection

SQLAlchemy models for `Source`, `Snapshot`, `LawChange`, `LawEvent`. Alembic migrations from day one. Change-detection logic: hash comparison for `document` sources (with a tolerance for whitespace / boilerplate noise); set-reconciliation for `event_list` sources. Defer "what counts as a meaningful diff" tuning until real snapshots are in hand.

### 5. [ ] Hourly poll loop

APScheduler in-process; per-source dispatch; structured logging; idempotent re-runs (a crashed mid-poll should not double-emit `LawEvent`s on retry). Configurable cadence per source (default hourly; some sources may justify slower).

### 6. [ ] Web app skeleton

FastAPI app with Jinja2 + HTMX + Tailwind. One route renders a "tracked sources" list with last-poll timestamps and most-recent change/event counts. No auth gate yet — pilot is locked behind basic auth or IP allowlist at the deploy layer.

### 7. [ ] Dashboard view: recent changes and events

Reverse-chronological feed combining `LawChange` and `LawEvent` rows across all active sources. Filter chips per source. This is Ellen's primary view.

### 8. [ ] Detail view per source

Snapshot history for `document` sources with a unified diff between any two versions; entry list for `event_list` sources with deep links to the source URL.

### 9. [ ] Deployment: Fly.io

Dockerfile, `fly.toml`, persistent volume for SQLite, secrets configuration, first deploy. Health check endpoint for Fly's load balancer.

### 10. [ ] DNS: lawmasolutions.com → Fly

`www` CNAME and apex A/AAAA records configured at Squarespace; Fly issues the HTTPS cert. Verify both `lawmasolutions.com` and `www.lawmasolutions.com` resolve and serve the app.

### 11. [~] CI: pytest on push + PR

GitHub Actions workflow running the full pytest suite plus ruff and mypy on every push and PR. Red status blocks merge.

Pulled forward from its original priority slot on Tom's request 2026-04-25 — wanted the suite to run automatically on every push from now on. Workflow at `.github/workflows/ci.yml` runs ruff → mypy → pytest on Python 3.11 and 3.12, on every push to any branch and every PR to main. Closes when Tom confirms a green run on GitHub.

### 12. [ ] Notification framework + email adapter

`Notifier` ABC under `src/lawtracker/notify/`; first concrete adapter is email (Resend or Postmark — pick at design-note time). Wired to the poll loop so new `LawChange` / `LawEvent` rows can be dispatched. Subscription model is trivial in pilot (one user, all sources); proper subscription comes with item 14.

### 13. [ ] SMS adapter

Twilio. Same `Notifier` interface as item 12. Per-recipient rate limiting and message-length truncation with a deep link back to the dashboard.

### 14. [ ] Auth + multi-user subscriptions

Magic-link email login. User-level subscription model: pick which sources to follow and which notification channels to use. Migrate SQLite → managed Postgres in this item (or just before, if the timing works).

### 15. [ ] Trusted third-party sources

Add adapters for Tom's approved third-party trackers (law-firm client-alert pages, Stanford FCPA Clearinghouse, paid aggregators like Global Investigations Review, Harvard Anticorruption Blog, etc.) once Tom provides the list. Pure adapter work — schema unchanged from the framework established in item 3. (FCPA Blog was originally listed here; moved into pilot inventory on 2026-04-25.)

---

**Priority note (2026-04-25):** items 16–18 below land **before** items 4–15. The pilot was reframed from "build storage + poll loop + UI sequentially" to "validate the data shape via a one-shot scout before investing in storage / poll loop / web app." Items keep their numbers per the no-renumber discipline; the order is logical, not numeric. Effective working order: 3 (in flight) → 16 → 17 → 18 → 4 → 5 → 6 → … No hourly polling concern at this stage; the scout runs on demand.

---

### 16. [~] Data scout CLI + Excel export

One-shot data scout: a `lawtracker scout` CLI that runs every configured adapter, collects `EventRecord`s, and writes them to disk for Tom + Ellen to review. No DB, no scheduling, no state between runs — each invocation is a fresh snapshot.

Outputs under `data/scout/`:

- `events.xlsx` — flat tabular (openpyxl). Universal columns first (`event_date`, `source_id`, `country`, `title`, `primary_actor`, `summary`, `url`); then per-source metadata keys as additional columns, sparse where a source doesn't populate them. Ellen can pivot, sort, filter without dev tooling.
- `events.jsonl` — full-fidelity backup; preserves the `metadata` dict shape for cases where Excel flattening loses something.
- `summary.txt` — counts directed at the trend questions Tom called out: events per month per source (last 24 months) for "more or less prosecutions over the last 6 months than the prior 6"; events per country; events per source; top 20 industries; top 20 primary_actors; per-source `last_event_date` and total count.

Adds `openpyxl` to runtime deps. List-page-only initial scope; per-source extraction depth lands with the adapters in item 17 (DOJ specifically gets link-following enrichment there).

### 17. [~] Pilot adapters + DOJ link-following enrichment

Build the breadth needed for a meaningful first scout:

- **Source 16 (FCPA Blog)** — RSS adapter; walks archive pagination back ~12 months for trend depth.
- **Source 10 (AFP foreign-bribery media releases)** — non-US English-language agency. Depth limited by what AFP publishes on the recent-releases page.
- **Source 12 (Fiscalía Nacional Chile)** — Spanish-language extraction with cohecho / corrupción / soborno / Ley 20.393 keyword filter.
- **DOJ FCPA actions: historical-year support** — extend `DojFcpaActionsAdapter` with a `poll_year(year)` method (or equivalent); scout iterates 24 months back.
- **DOJ FCPA actions: link-following enrichment** (option (b) approved by Tom 2026-04-25). For each list-page entry, fetch the linked press-release / case-detail page and extract `industry`, `defendant`, `defendant_type`, `penalty_usd`, `disgorgement_usd`, `resolution_type` (DPA / NPA / plea / etc.) where parseable. Industry is needed for the "cases focused on a particular industry" trend question. Brittleness expected; tests use committed press-release fixture(s) under `tests/fixtures/`.

Each adapter follows the framework from item 3 (subclass `SourceAdapter`, parse the live page, commit a fixture, write parser tests).

### 18. [ ] Scout review checkpoint

Tom + Ellen review `data/scout/events.xlsx` and `summary.txt` produced by items 16 + 17. Decisions to surface:

- Are the universal `EventRecord` fields the right ones? (`primary_actor`, `summary`, `country` populated correctly across sources?)
- Are the per-source metadata blobs giving the right detail?
- Are the right sources in the inventory? Anything to add or remove? Any source that's pure noise?
- Is signal-to-noise acceptable for Ellen's use?

Adjustments fall out as new items (schema changes, source list edits, adapter refinements). Item 4 (storage) lands after this checkpoint; on landing, item 4's scope expands to include a one-shot `lawtracker ingest-scout` to load the JSONL files from the pilot into the new DB so pilot data isn't lost. Items 5 (poll loop), 6+ (web app) follow item 4 as before.

## Descoped / on hold

*None yet. Items parked here are not dead — they are off the active queue but preserved in case priorities shift. Revive by moving the full prose back under "Backlog" at the original number and flipping `[-]` → `[ ]`.*
