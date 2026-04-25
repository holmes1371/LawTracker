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

**2026-04-25**

- Pilot scope locked with Tom: US anti-corruption *enforcement and government messaging* (not statutory text). FCPA and FEPA priority. Pilot user is Ellen.
- Architecture and pilot-source inventory landed — `design/architecture.md` (Fly.io / FastAPI / Jinja+HTMX / SQLite-then-Postgres / APScheduler) and `design/sources.md` (9 sources across `document` and `event_list` shapes). Items 1–2 at `[~]` pending Tom's signoff.
- Backlog items 3–15 filed; next pickup is item 3 (source adapter framework + first adapter) using DOJ FCPA enforcement actions list as the anchor.
- Nothing else in flight.

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

Status legend:

- `[ ]` not started
- `[~]` in progress — include a note with what is done and what remains
- `[x]` done — include the commit SHA
- `[-]` descoped / on hold — full prose preserved in "Descoped / on hold" at the bottom for possible future revival

## Backlog (priority order)

### 1. [~] Architecture + stack design note

Capture the locked stack and product shape so every later item references one source of truth instead of re-deriving choices. Output: `design/architecture.md` covering pilot scope, the document-vs-event source distinction, the chosen stack (Fly.io / FastAPI / Jinja+HTMX / SQLite-then-Postgres / APScheduler), the conceptual data model (`Source` / `Snapshot` / `LawChange` / `LawEvent`), and repo layout additions.

In progress: design note landed this commit. Pending Tom's signoff before flipping to `[x]`.

### 2. [~] Pilot source inventory

Lock the concrete URL list for the pilot so item 3 has a real target list, not a hypothetical. Output: `design/sources.md` enumerating the nine pilot sources (4 `document`, 5 `event_list`), out-of-scope statutes/jurisdictions, the future plug-in slot for Tom's trusted third-party trackers, and the implementation order (anchor adapter = DOJ FCPA enforcement actions list).

In progress: source inventory landed this commit. Pending Tom's signoff before flipping to `[x]`.

### 3. [ ] Source adapter framework + first adapter

Build the `SourceAdapter` ABC under `src/lawtracker/sources/base.py` plus the first concrete adapter — DOJ FCPA enforcement actions list — end to end. Adapter declares its kind (`document` | `event_list` | `both`) and emits Pydantic records the storage layer can persist. First adapter is the anchor that proves the `event_list` shape; items 6–9 in `design/sources.md` follow the same template.

Design-note questions to resolve before coding: how the adapter signals "no change" vs. "transient fetch failure" so the poll loop can distinguish them; what the dedup key is for `event_list` entries (URL? URL + title hash? source-specific?); how to persist source-specific metadata without per-source columns.

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

### 11. [ ] CI: pytest on push + PR

GitHub Actions workflow running the full pytest suite plus ruff and mypy on every push and PR. Red status blocks merge.

### 12. [ ] Notification framework + email adapter

`Notifier` ABC under `src/lawtracker/notify/`; first concrete adapter is email (Resend or Postmark — pick at design-note time). Wired to the poll loop so new `LawChange` / `LawEvent` rows can be dispatched. Subscription model is trivial in pilot (one user, all sources); proper subscription comes with item 14.

### 13. [ ] SMS adapter

Twilio. Same `Notifier` interface as item 12. Per-recipient rate limiting and message-length truncation with a deep link back to the dashboard.

### 14. [ ] Auth + multi-user subscriptions

Magic-link email login. User-level subscription model: pick which sources to follow and which notification channels to use. Migrate SQLite → managed Postgres in this item (or just before, if the timing works).

### 15. [ ] Trusted third-party sources

Add adapters for Tom's approved third-party trackers (law-firm client-alert pages, FCPA Blog, Stanford FCPA Clearinghouse, etc.) once Tom provides the list. Pure adapter work — schema unchanged from the framework established in item 3.

## Descoped / on hold

*None yet. Items parked here are not dead — they are off the active queue but preserved in case priorities shift. Revive by moving the full prose back under "Backlog" at the original number and flipping `[-]` → `[ ]`.*
