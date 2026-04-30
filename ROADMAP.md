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

**2026-04-29 (session wrap — full deploy stack live at lawmasolutions.com; next session = wire item 21 features into the deployed shell)**

- **lawmasolutions.com is live** over HTTPS, serving a styled "Coming Soon" page. Stack: FastAPI app in a Docker container on Fly.io (`iad`, free tier, scales to zero), reachable at the apex + `www` via Squarespace DNS pointing at Fly's anycast IPs, Let's Encrypt cert auto-issued. Resend domain verified for sending; `RESEND_API_KEY` set as a Fly secret. Full walkthrough captured in `design/deployment.md`. Items 9 and 10 flipped to `[~]` (functionally complete; awaiting Tom's signoff. Item 9's persistent-volume piece deferred until item 4 lands).
- **Item 3 closed** by Tom 2026-04-29 at SHA `d75d1b9` — source adapter framework + first adapter. Full prose in `COMPLETED.md`.
- **Active build target now**: item 21 application work, on top of the deployed shell. The FastAPI app today serves a single HTML route at `/`; next session wires the public Analysis + Source Links pages (mockup → Jinja2 templates), then admin auth (magic-link via Resend), then the draft/publish workflow. Mockups at `data/scout/{,admin}/*.html` are the visual + UX targets.
- **Open backlog at session end**: items 9, 10, 11, 21 `[~]` (deploy + DNS + CI all pending Tom's signoff; 21 active); item 22 `[ ]` filed (adapter health monitoring — design needs more thought); items 4 / 5 / 6 / 7 / 8 / 14 / 15 deferred. Items closed this week: 3 (d75d1b9), 16/17/19/20 (35da4c8).
- **Cold-pickup pointers**: `design/deployment.md` is THE source of truth for the live infrastructure (account setup, DNS, secrets, day-to-day ops, troubleshooting). `design/admin-app.md` is the architecture + UX spec for item 21's application layer. To redeploy from local: `fly deploy`. To check live status: `fly status` / `fly logs`. To add a secret: `fly secrets set NAME=value` (auto-redeploys).

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

3\. [x] Source adapter framework + first adapter — d75d1b9 — see COMPLETED.md

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

### 9. [~] Deployment: Fly.io

Dockerfile, `fly.toml`, persistent volume for SQLite, secrets configuration, first deploy. Health check endpoint for Fly's load balancer.

Live as of 2026-04-29 (`5d8231d` scaffold + `397e890` fly.toml + `5c44d3c` Coming Soon page). Hello-world FastAPI app deployed at `lawtracker.fly.dev`, scales to zero when idle. `RESEND_API_KEY` set as a Fly secret. Health-check endpoint at `/health` polled every 30s. **Persistent volume for SQLite** is the remaining piece — defer until item 4 (storage) lands. Full walkthrough captured in `design/deployment.md`.

### 10. [~] DNS: lawmasolutions.com → Fly

`www` CNAME and apex A/AAAA records configured at Squarespace; Fly issues the HTTPS cert. Verify both `lawmasolutions.com` and `www.lawmasolutions.com` resolve and serve the app.

Live as of 2026-04-29. Apex + www both serve the same Fly app over HTTPS via Let's Encrypt certs (90-day cycle, Fly auto-renews at the 60-day mark). Used Fly's shared anycast IPv4 (`66.241.125.32`) + dedicated IPv6 (`2a09:8280:1::10d:ecbc:0`); A and AAAA records at Squarespace for both apex and `www`. **Implementation choice that diverged from the original spec**: used A/AAAA for `www` instead of CNAME — Fly explicitly recommended A records and our use case doesn't benefit from CNAME indirection. Walkthrough in `design/deployment.md`.

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

**Priority note (2026-04-28):** items 16, 17, 19, 20 closed by Tom 2026-04-28 at SHA 35da4c8. Item 21 (FastAPI admin app with magic-link + shared-password gate + draft/publish workflow) is the active build target — it subsumes substantial portions of items 6 (web app skeleton), 7 (dashboard view), and 14 (auth); those items may be partially or fully closed by item 21's landing, revisit after it ships. Updated working order: 21 (admin app — currently mocking up the admin-side HTML before live FastAPI) → 4 (storage) → 5 (poll loop) → revisit 6 / 7 / 8 / 14.

---

16\. [x] Data scout CLI + Excel export — 35da4c8 — see COMPLETED.md

17\. [x] Pilot adapters + DOJ link-following enrichment — 35da4c8 — see COMPLETED.md

### 18. [ ] Scout review checkpoint

Tom + Ellen review `data/scout/events.xlsx` and `summary.txt` produced by items 16 + 17. Decisions to surface:

- Are the universal `EventRecord` fields the right ones? (`primary_actor`, `summary`, `country` populated correctly across sources?)
- Are the per-source metadata blobs giving the right detail?
- Are the right sources in the inventory? Anything to add or remove? Any source that's pure noise?
- Is signal-to-noise acceptable for Ellen's use?

Adjustments fall out as new items (schema changes, source list edits, adapter refinements). Item 4 (storage) lands after this checkpoint; on landing, item 4's scope expands to include a one-shot `lawtracker ingest-scout` to load the JSONL files from the pilot into the new DB so pilot data isn't lost. Items 5 (poll loop), 6+ (web app) follow item 4 as before.

19\. [x] Anthropic-API-backed analysis + prose interpretation — 35da4c8 — see COMPLETED.md

20\. [x] Static HTML preview mockups (`lawtracker render`) — 35da4c8 — see COMPLETED.md

### 21. [~] FastAPI admin app with two-tier auth + draft/publish workflow

Pulls items 6 + 7 + (subset of) 14 forward into a single coherent build, because the curation loop Tom wants — manually drop noisy articles → re-run LLM → review → publish — only works with a server.

Architecture pinned 2026-04-28 in `design/admin-app.md`. Highlights:

- **Two-tier auth**: shared password on public pages (cookie-gated; Tom shares the password with Ellen + clients verbally); magic-link to Tom's email on `/admin/*` (single-admin allowlist).
- **Draft / public file split**: `data/scout/draft/` is the admin's working state (latest scout output, current exclusions, current edits, latest LLM draft); `data/scout/public/` is what the public pages render from. Publish copies draft → public.
- **Article-level exclusions**, keyed by `dedup_key`, applied to both Sources page rendering and LLM analysis input.
- **Per-country edit textareas** on the admin Analysis page, keyed by exact country heading text. Edits persist until the next re-run; re-run discards edits (simpler model — re-edit if needed).
- **Re-run** on click triggers `analyze` against the filtered events. No cost-estimate prompt; just runs.
- **Publish in dev mode** = local file copy of `draft/` → `public/`. **Publish in prod mode** (post-deploy) will additionally trigger a deploy hook; structured so the second mode is one function to swap in later.
- **Per-event summary editing**: out of scope for this item; per-event summaries on the Sources page render as-is.
- **External-service dependency**: magic-link emails require an email-sending account (Resend or Postmark). Tom does not have one yet; the design note walks through Resend setup step by step (account, domain verification, API key, env var).

Plan approved 2026-04-25 (web app general scope) and 2026-04-28 (admin/draft/publish + auth specifics). No code yet; design note is the first artifact.

### 22. [ ] Adapter health monitoring + breakage alerts

What happens when a source site silently changes its layout and an adapter stops returning events without throwing? Filed 2026-04-28 from Tom's prompt — design needs more thought before implementation; this entry captures the rough scope so the next session has something to push against.

Two failure modes to distinguish:

- **Hard failures** (HTTP errors, parser exceptions, timeouts) — already visible in `summary.txt` per-adapter status, with auto-retry on transient errors. Gap is alerting: today you have to read the file to know.
- **Silent regressions** (layout change → parser stops finding events but doesn't crash → returns 0) — far more dangerous. Adapter looks `ok` in summary; events just stop. Easy to miss for weeks unless someone's specifically watching count trends.

Rough scope (revisit at design time):

- **Per-adapter health metrics persisted between runs** — `data/scout/health.json` keyed by `source_id` with last successful run, recent event-count rolling baseline (e.g. last 8 runs), consecutive-failure count.
- **Anomaly detection at scout end** — flag hard failures plus abrupt count drops vs. baseline. Per-adapter sensitivity matters: Fiscalía Chile's "0 most weeks" is signal, but DOJ's "0 this week after 12/week for a year" is not.
- **Email alert to Tom only** (not Ellen — adapter-down is an ops concern, not curation). Daily digest, not per-failure spam. Piggybacks on the Resend setup that lands with item 21.
- **Optional `/admin/health` dashboard** (later) showing each adapter's status + last poll + count trend.

Sequencing: cleanest after item 4 (storage) for the rolling-baseline data and item 21 (email infra) for the alert transport. A flat-file `health.json` + anomaly detection in scout could ship earlier as a stopgap if Tom wants the silent-regression coverage before then.

Out of scope (file separately if useful): snapshot-diffing of source HTML, field-level fill-rate health checks, circuit breaker on consecutive failures.

## Descoped / on hold

*None yet. Items parked here are not dead — they are off the active queue but preserved in case priorities shift. Revive by moving the full prose back under "Backlog" at the original number and flipping `[-]` → `[ ]`.*
