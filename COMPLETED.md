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

## 16. Data scout CLI + Excel export — 35da4c8

Landed `lawtracker scout` CLI plus the Excel / JSONL / summary outputs Ellen needs to review the pilot data without touching code. Closed by Tom 2026-04-28 alongside items 17, 19, 20.

What was built (final shape after the 2026-04-28 pipeline split):

- **`py -m lawtracker scout`** (or `python -m lawtracker scout`). One-shot, on demand. No DB, no scheduler. Each run is a fresh snapshot. `--source <id>` restricts to one adapter; `--output-dir` overrides the default `data/scout/`.
- **Outputs under `data/scout/`** (analysis decoupled into item 19 in the pipeline split — see below):
  - `events.xlsx` — flat table with universal columns (`event_date`, `source_id`, `country`, `title`, `primary_actor`, `summary`, `url`, `dedup_key`) followed by a sparse union of per-source metadata keys. Title column hyperlinked to the event URL (Ellen's wave-1 ask). `openpyxl` is the runtime dep.
  - `events.jsonl` — full-fidelity backup; preserves `metadata` dicts that Excel flattening loses.
  - `summary.txt` — counts directed at Tom's trend questions: events per month per source (last 24 months), events per country, top 20 industries, top 20 primary_actors, per-source `last_event_date` and total count.
- **Live progress output** during scout runs (per-source status + per-event enrichment progress in anthropic mode), added 2026-04-25 because long live-mode runs were silent for minutes.
- **Per-event LLM enrichment** integrated into scout: summary generation + LLM-as-judge noise classification, with disk-backed cache under `data/scout/.cache/summaries.json` keyed by mode-stamped keys so stub and anthropic outputs don't collide.
- **Three-layer event-noise filter** (Tom 2026-04-25): parse-time regex → LLM-as-judge → post-enrichment regex. The post-enrichment pass catches entries whose innocuous titles only reveal their podcast / webinar nature once the LLM reads the article (M&C "EMBARGOED!: South of the Border" was the canonical case).

Pipeline split landed 2026-04-28 (see item 19 entry below): the LLM analysis step was decoupled from `scout` into a separate `analyze` subcommand, so scout now produces only `events.xlsx` + `events.jsonl` + `summary.txt`. `analysis.md` lives under item 19's territory.

Non-obvious decisions worth preserving:

- **Sparse-union Excel column strategy** vs. one column per source: kept all events in one sheet so Ellen can pivot/filter without dev tooling. Columns adopted on first appearance and never dropped, even if a later run has zero events for a given metadata key.
- **JSONL is the lossless backup**, not the primary surface: dataclass-shaped records survive Excel flattening loss. When item 4 (storage) lands, `lawtracker ingest-scout` will read JSONL not XLSX.
- **No DB / no scheduler** was deliberate. Tom's reframing was "validate the data shape before investing in storage / poll loop / web app." This item carries that pivot.

Follow-ups spun off into other items: storage + change detection (item 4); hourly poll loop (item 5); admin curation UI (item 21).

## 17. Pilot adapters + DOJ link-following enrichment — 35da4c8

Built the breadth needed for a meaningful first scout. Closed by Tom 2026-04-28.

Adapters landed (11 total, 8+ producing non-zero events depending on environment):

- **DOJ FCPA enforcement actions** (`doj_fcpa_actions`) — the anchor `event_list` adapter. Includes link-following enrichment (option (b) approved 2026-04-25): for each list-page entry, fetch the linked press-release / case-detail page and extract `industry`, `defendant`, `defendant_type`, `penalty_usd`, `disgorgement_usd`, `resolution_type` (DPA / NPA / plea / etc.) where parseable. Industry is needed for the "cases focused on a particular industry" trend question. Historical-year support (`poll_year`) iterates the scout 24 months back.
- **SEC FCPA cases** (`sec_fcpa_cases`) — LLM-extracted (item 19 priority 2). The page is a single long narrative — year headers + bolded company names + free-text paragraphs. Claude reads the page and emits structured `EventRecord`s for the most recent 1-2 years only (Ellen confirmed only the recent slice is relevant).
- **AFP foreign-bribery media releases** (`afp_foreign_bribery`) — non-US English-language agency.
- **Fiscalía Nacional Chile** (`fiscalia_chile`) and **Consejo para la Transparencia Chile** (`consejo_transparencia_cl`) — Spanish-language extraction with cohecho / corrupción / soborno / Ley 20.393 keyword filter; auto-translated via MyMemory at parse time, originals preserved as `metadata.title_es` / `summary_es`.
- **Volkov Law** (`volkov_law`), **Gibson Dunn** (`gibson_dunn`), **Foley LLP** (`foley_llp`), **Global Anticorruption Blog** (`global_anticorruption_blog`), **Harvard CorpGov FCPA** (`harvard_corpgov_fcpa`), **Miller & Chevalier FCPA practice** (`miller_chevalier`) — practitioner commentary feeds (RSS where available; HTML search pages for non-RSS firms via the framework Tom flagged 2026-04-25).
- **`curl_cffi`** added 2026-04-25 to bypass Cloudflare's TLS-fingerprint (JA3) block on Gibson Dunn + Miller & Chevalier (returned 200 to curl during fixture capture, 403 to httpx at scout time). Dropped in as `use_curl_cffi = True` per-adapter.

Each adapter follows the framework from item 3 (subclass `SourceAdapter`, parse the live page, commit a fixture, write parser tests).

Sources flagged blocked / JS-rendered / no-RSS at end of item: FCPA Blog (CDN 401), OECD WGB (CDN 403), AUSTRAC / NACC / CDPP (timeout — likely AU geo-block), ASIC (JS-rendered, no inline data), and a long list of law firms with no exposed RSS or CDN 403/404 (WilmerHale / Sidley / Skadden / Debevoise / Latham / Cleary / Hogan Lovells / Freshfields / Herbert Smith Freehills / DLA Piper / Foley Hoag / Covington / Ropes & Gray). Three unblock paths flagged for later prioritization: `curl_cffi` extension to more sites, Playwright headless browser, or email-subscription parsing.

Non-obvious decisions worth preserving:

- **Country promoted to a first-class `EventRecord` field** on Tom's call (instead of metadata). Adapter-level value is a best-effort hint from the publisher, not authoritative — the LLM derives effective country from event text during analysis (item 19 priority 1).
- **Translation cache** (Ellen's wave-2 ask) avoids re-paying MyMemory for unchanged Spanish titles across runs.
- **HTML search pages as a parsing surface** (Tom 2026-04-25): many firms expose FCPA-practice content via filterable HTML even when no RSS exists. M&C's `/search?related_practice=8965` was the worked example; pattern is reusable.

Follow-ups spun off into other items: unblocking blocked sources (item 21 polish or new item); LLM-aware translation upgrade (item 19 priority 5, deferred); per-event country derivation persistence (flagged in `design/admin-app.md` as future polish).

## 19. Anthropic-API-backed analysis + prose interpretation — 35da4c8

Landed `src/lawtracker/llm.py` plus integrated Claude calls at the priority points Tom set. Closed by Tom 2026-04-28.

What was built:

- **`llm.complete()` helper** with three modes via `LAWTRACKER_LLM_MODE` env var (or `--llm-mode` flag): `stub` (default; canned per-call placeholders, no API spend), `anthropic` (real Claude Sonnet 4.5 calls), `off` (empty string for measuring no-LLM baseline). `ANTHROPIC_API_KEY` env var required for anthropic mode; fast-fail with PowerShell setup snippet if missing (added 2026-04-28 because the SDK's native auth error was a 50-line stack trace).
- **Priority 1 — post-aggregation trend analysis** (Ellen's primary ask, evolved through Tom's feedback). Reframed 2026-04-28 to a per-country structure for in-house corporate compliance professionals: US first (up to 5 bullets), other countries alpha (2-3 each, more if "major changes"). Bucket events by enforcing authority not jurisdiction-of-conduct (Tom's TIGO/Petrobras feedback): a US DOJ FCPA action involving Guatemalan officials goes under United States; a foreign jurisdiction gets its own section only when its government brought a coordinated action (Petrobras/Lava Jato, Airbus, etc.). Country grouping derived from event text, not adapter `country` field. Stub mirrors the per-country structure so prompt iteration in stub mode shows the right shape.
- **Priority 2 — SEC FCPA cases adapter** (item 17). The page is a single long narrative; Claude extracts structured `EventRecord`s for the most recent 1-2 years.
- **Priority 3 — per-event summary generation** (Ellen's wave-2 ask). Where adapters cannot extract a clean summary at parse time (DOJ list page, AFP search results, M&C entries), the per-event LLM call reads the linked detail page and writes a one-line "why this matters." Dual-purpose call — also returns the LLM-as-judge drop/keep decision in the same payload (`{"drop": bool, "summary": str?, "reason": str?}`) so each event hits the API at most once. Cached in `data/scout/.cache/summaries.json`.
- **Priorities 4-6 deferred**: industry/resolution-type classification stayed regex (good enough for pilot); FCPA-aware translation deferred unless Ellen surfaces MyMemory quality issues; cross-source dedup waits for storage (item 4).

Pipeline split landed 2026-04-28 on Tom's directive:

- `lawtracker scout` produces `events.{xlsx,jsonl}` + `summary.txt` only — no LLM analysis call at scout time.
- `lawtracker analyze` reads `data/scout/events.jsonl`, calls Claude, writes `data/scout/analysis.md`. Re-runnable while iterating on the prompt without re-polling adapters.
- Two-step pipeline lets Tom review the spreadsheet before paying for the analysis call (~$0.05-$0.20 per analyze run depending on event volume; ~30-90s).

Operational notes:

- `anthropic` SDK is **runtime-optional**: it is only imported when `LAWTRACKER_LLM_MODE=anthropic` is set. CI runs in stub mode and does not install the package; tests that exercise the import-error / API-key paths inject fakes via `sys.modules`.
- Fail-soft per Tom's standing rule: missing SDK or missing API key raises a clear `RuntimeError` at the LLM call site — the deterministic pipeline (xlsx / jsonl / summary) still completes.
- Prompt caching deferred — Sonnet 4.5 input prices at pilot scale don't justify the integration complexity yet.

Non-obvious decisions worth preserving:

- **Stub-first** was Tom's call 2026-04-25. The reason: Tom expected to iterate heavily on prompt design and output formats before flipping to live calls, and stub mode lets that iteration happen for free. Stub stayed the default mode end-to-end.
- **Bucket by enforcing authority, not jurisdiction-of-conduct** (Tom 2026-04-28): the LLM's natural inclination was to surface every foreign country whose officials appeared in a US DOJ press release, which created noisy 1-event country sections. The corrected rule produces tight per-country sections that mirror how compliance professionals actually think about jurisdictional risk. Coordinated-resolution exception preserved for Petrobras-style cases where multiple governments did genuinely act in parallel.
- **Per-event LLM call returns structured JSON** (drop/summary in one payload) rather than two separate calls, halving API spend on the per-event layer.

Follow-ups spun off: per-event country derivation persisted into `events.jsonl` (flagged in `design/admin-app.md` as future polish); editable per-country sections + click-to-exclude curation (item 21).

## 20. Static HTML preview mockups (`lawtracker render`) — 35da4c8

Pre-FastAPI mockup target so Tom + Ellen could react to layout / visual decisions before the live web app was built. Closed by Tom 2026-04-28.

What was built:

- **`py -m lawtracker render`**. Reads `data/scout/events.jsonl` + `data/scout/analysis.md`; writes `data/scout/analysis.html` + `data/scout/sources.html`. Tailwind via CDN in `<head>`; no JS framework, no build tooling. Open the output files by double-click in Explorer or `start data\scout\analysis.html` in PowerShell.
- **`analysis.html`** — country-by-country sections, blog-style. United States first; remaining countries alphabetical; cross-jurisdictional last if present. Bullets render with bold/italic/links via a small hand-rolled markdown→HTML converter. LLM blockquote stub-markers stripped. Horizontal-rule separators between LLM-emitted country sections collapsed silently (regression test in place — earlier parser cut at the first `---` and dropped Australia + UK).
- **`sources.html`** — events grouped by country (US first, alpha rest, "(uncategorized)" last). Within each country, reverse-chronological by `event_date`. Each event shows: date in `dd MONTH yyyy` format (e.g. `15 March 2026`), primary actor when present, title (clickable to source URL, opens new tab), summary. Source IDs hidden per Tom 2026-04-28.
- **Shared top nav** linking the two pages; static-mockup footer noting the production target is lawmasolutions.com.

Non-obvious decisions worth preserving:

- **Hand-rolled markdown→HTML** rather than pulling in `markdown` or `mistune` as a dep. The LLM's output shape is constrained (headers + bullets + bold + inline code + links + horizontal rules) — ~30 lines of regex covers it without a new runtime dep.
- **`country` field on the Sources page is the adapter-level value** (best-effort hint from the publisher), not the LLM-derived effective country used on the Analysis page. This means a US blog covering a Brazilian case shows under US on Sources but under Brazil on Analysis. Misalignment is a known limitation; deferred until Ellen calls it out specifically. Persisting per-event LLM-derived country is filed under `design/admin-app.md` "Future polish."
- **Markup is intentionally Jinja2-friendly** so it carries forward into item 21's FastAPI templates with minimal rework. Tailwind class lists are the same shape; the structure is just static HTML where item 21 will inject template variables.

Follow-ups spun off: live FastAPI rendering with admin curation features (item 21).
