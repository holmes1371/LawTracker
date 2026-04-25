# LawTracker — Completed Items

Archive of closed (`[x]`) ROADMAP items with their full post-mortem prose. Items move here only after Tom's explicit signoff (see `ROADMAP.md` — "For future agents").

Original item numbers are stable and match the stubs in `ROADMAP.md`. Never renumber.

Each entry should include: the item number and title, the commit SHA(s), what was built, any non-obvious decisions worth preserving, and any follow-ups spun off into new ROADMAP items.

---

## 1. Architecture + stack design note — ceec7ec

Landed `design/architecture.md` as the single source of truth for product shape, source-tracking model, and stack choices. Closed by Tom 2026-04-25.

What was decided:

- **Pilot scope:** US anti-corruption *enforcement and government messaging*, not statutory text. FCPA and FEPA priority subject matter. Pilot user is Ellen. The statutes themselves are explicitly out of scope — Ellen needs enforcement and government messaging, not statutory text.
- **Two source shapes baked into the data model from day one:** `document` sources (URL whose content evolves in place; hash + diff) and `event_list` sources (list page where new entries appear; new-entry detection). A single source can be both. This shaped the conceptual data model — `Source`, `Snapshot`, `LawChange`, `LawEvent` — and prevents the future retrofit of "wait, this source has a different shape" pain.
- **Stack:** Fly.io (host, free tier covers PoC, scale path is clear) / FastAPI (async, same app serves HTML and JSON, free API surface for future integrations) / Jinja2 + HTMX + Tailwind (server-rendered, no SPA build pipeline) / SQLite on Fly volume during PoC then managed Postgres when adding auth (SQLAlchemy + Alembic from day one so the migration is config not rewrite) / APScheduler in-process (move to separate worker or Celery + Redis when load grows) / httpx + beautifulsoup4 + Pydantic for scraping / Notifier ABC interface from day one with no concrete adapters in pilot / no auth in pilot, basic auth or IP allowlist gate.
- **DNS:** `www.lawmasolutions.com` CNAME to Fly app, apex via Fly A/AAAA. Squarespace remains registrar.

Non-obvious decisions worth preserving:

- SQLite over Postgres for pilot is deliberate and reversed only when multi-user lands. Schema lives in SQLAlchemy + Alembic so the swap is a connection-string change, not a rewrite. Avoid the temptation to "just use Postgres now" — the operational simplicity of single-file SQLite during pilot is real value.
- Notification adapter interface lands in pilot even though no concrete adapters do. This pins the contract before any consumer exists, so when email and SMS land they are slot-ins.
- The data-model contract (`Source` / `Snapshot` / `LawChange` / `LawEvent`) is explicitly framed as the contract between the poller and the web app — they are decoupled around this surface and can be evolved independently.

Out of pilot scope by explicit decision (file as future ROADMAP items only if pilot expands): non-FCPA US anti-corruption statutes (18 U.S.C. § 201 domestic bribery, AML Act / Corporate Transparency Act, Magnitsky / OFAC SDN), non-US jurisdictions (UK Bribery Act, EU directives, OECD).

What this note explicitly did NOT decide and deferred to later items: dashboard HTML/CSS layout (items 6–7), per-source extraction strategy (per-adapter design notes as edge cases hit), notification UX (item 12), authentication mechanism for multi-user (item 14).

## 2. Pilot source inventory — ceec7ec

Landed `design/sources.md` with the concrete URL list for the pilot so item 3 (source adapter framework) has real targets, not hypotheticals. Closed by Tom 2026-04-25.

Nine pilot sources, split by shape:

**Document sources (4) — change rarely, each change high-signal:**

1. DOJ FCPA Resource Guide — joint DOJ/SEC compliance guidance, canonical interpretation document.
2. DOJ Corporate Enforcement Policy (JM 9-47.120) — voluntary self-disclosure / cooperation / remediation framework.
3. DOJ Evaluation of Corporate Compliance Programs (ECCP).
4. JM 9-28.000 — Principles of Federal Prosecution of Business Organizations.

**Event_list sources (5) — steady stream:**

5. DOJ FCPA enforcement actions list (the curated index — anchor adapter for item 3).
6. SEC FCPA enforcement actions.
7. DOJ FCPA Opinion Procedure releases.
8. DOJ press releases (FCPA-filtered) — ranked lower than the curated enforcement list because of higher noise.
9. DOJ senior-official speeches (AG, DAG, AAG-Criminal Division) — primary surface for enforcement-priority and strategy announcements.

Implementation order set: source #5 is the anchor adapter for item 3, exercising the `event_list` shape end to end; items 6–9 follow that template; documents 1–4 come after the event-list pattern is proven.

Future-expansion slot reserved (not pilot, not yet a ROADMAP item — filed as item 15 once the anchor adapter exists): trusted third-party trackers from Tom's approved list — large law-firm client-alert pages, FCPA Blog, Stanford FCPA Clearinghouse. Adapter framework is built so these slot in as additional `event_list` (or `document`) sources without schema changes.
