# LawTracker — Data scout (item 16)

Status: in flight 2026-04-25. Plan approved by Tom in conversation that day.

## Scope

**In:**

- `src/lawtracker/scout.py` — orchestrator; runs every adapter in `PILOT_ADAPTERS`, writes outputs.
- `src/lawtracker/cli.py` — extended with a `scout` subcommand. Existing no-arg / `--version` behavior preserved.
- `tests/test_scout.py` — unit tests with fake adapters; verifies the three output files are produced and well-formed.
- `pyproject.toml` — adds `openpyxl>=3.1` to runtime deps.
- `data/` already in `.gitignore`; scout outputs are ephemeral across iterations.

**Out:**

- The pilot adapters themselves (FCPA Blog, AFP, Fiscalía, DOJ enrichment) — item 17.
- Live network testing — fakes return canned `EventRecord` lists.
- Scheduling, retries, dedup, cross-run state — every scout invocation is a fresh snapshot.
- Excel styling beyond a frozen header row.

## Decisions

### 1. Adapter registration: hardcoded list

`PILOT_ADAPTERS: list[type[SourceAdapter]] = [...]` at module level. Adding an adapter to the scout = importing it and appending. No registry pattern, no config file. Revisit if it ever crosses ~20 adapters.

For item 16 the list contains only `DojFcpaActionsAdapter`. Item 17 expands it.

### 2. Excel column strategy: universal first, then sparse metadata union

Header row, in order:

```
event_date | source_id | country | title | primary_actor | summary | url | dedup_key | <metadata keys, alphabetized>
```

The metadata-key portion is the alphabetized union of every key seen in any event's `metadata` dict across the run. Sparse — most cells empty per row. `dedup_key` last because it's an implementation detail.

Header row frozen, column widths best-fit (capped at 60).

### 3. JSONL is the lossless backup

One `EventRecord.model_dump_json()` per line, in the same order as Excel rows. If Excel flattening loses something (nested metadata, etc.), the JSONL is the source of truth.

### 4. Summary stats — directly mapped to Tom's trend questions

Plain text, monospaced. Sections:

- **Per-source totals** — count, `last_event_date`, status from the most recent poll, error if any.
- **Events per month per source (last 24 months)** — wide table, months as rows, sources as columns. Answers "more or less prosecutions over the last 6 months than the prior 6."
- **Events per country** — `Counter` ordered by frequency.
- **Top 20 industries** — from `metadata.industry` where present. Empty if no source emits industry yet (item 17 will).
- **Top 20 primary_actors** — recurring defendants jump out fast.

If specific cuts are missing after the first scout run, easy to add.

### 5. Output dir: `data/scout/`, fixed

Default. `--output-dir` flag overrides. Not configurable beyond that for v1.

## CLI shape

The existing `lawtracker` CLI takes `--version` and prints a placeholder line. Extend with subparsers:

```
lawtracker --version          # unchanged
lawtracker scout              # runs every adapter in PILOT_ADAPTERS
lawtracker scout --source=doj_fcpa_actions   # runs one adapter only
lawtracker scout --output-dir=path/to/out    # custom output dir
```

Three invocation styles all work:

- `lawtracker scout` — entry point on PATH after `pip install -e .`.
- `python -m lawtracker scout` — via `__main__.py`.
- `python -m lawtracker.scout` — `__main__` block on `scout.py` itself.

## Test strategy

Three fakes:

- `_OkAdapter` — returns two events with overlapping + disjoint metadata keys, two different countries, two different event_dates.
- `_OtherOkAdapter` — returns one event, country=None (multilateral-style), different metadata shape.
- `_FailingAdapter` — returns `permanent_failure`, no events.

Tests verify:

- All three output files exist after a run.
- Excel headers contain the universal columns first, then alphabetized metadata-key union.
- JSONL has N lines, parseable JSON.
- Summary contains every source_id, the failure error message, country counts including `(none)`.
- Empty run (only failures) still writes all three files.
- `--source` filter restricts to a single adapter.

Date range for the events-per-month-per-source matrix is left lightly tested — windowed against `date.today()`, exact rows would flake across days. The section header presence is asserted; content not exact-matched.

## External-service walkthrough

N/A — local Python; no accounts, secrets, or external setup.

## Commit sequence

Single commit: scout module + CLI extension + tests + pyproject update + design note + ROADMAP `[ ]` → `[~]` flip + summary block update.

## Findings during item 17 buildout (2026-04-25)

- **FCPA Blog blocked.** All candidate URLs return HTTP 401 with a Cloudflare bot-protection page even from a realistic Chrome User-Agent. No adapter possible without changes to access. Captured in `design/sources.md` source #16; revisit options at scout review (item 18).
- **AFP general news has zero foreign-bribery signal.** The originally-listed `/news-media/media-releases` returns 30+ pages of mostly domestic crime; zero hits on bribery / corruption / FCPA keywords. Switched the adapter target to AFP's site search (`/search?keys=foreign+bribery`) which yields ~12 actual foreign-bribery media releases on page 0.
- **Fiscalía Chile URL was wrong.** `/Fiscalia/sala_prensa` is a 404; the press section is now under `/actualidad/noticias/nacionales`. Anti-corruption signal is sparse on the front page — keyword filter (`cohecho`, `corrupción`, `soborno`, `lavado`, `fraude al fisco`, `Ley 20.393`, `funcionario público`) usually returns zero matches per page. Tom + Ellen will see this in the scout output and can decide whether to pursue regional pages, broader keyword set, or a different Chilean source.

## Keyword filters in use (for Ellen's review)

All filter regexes live in `src/lawtracker/sources/_filters.py` so they can
be tweaked without touching adapter code. Two are in active use:

**`ANTI_CORRUPTION_EN`** — applied to law-firm blogs and any English-language
broad-topic feed. Matches (case-insensitive):

- FCPA / FEPA
- foreign corrupt (practices), foreign bribery, foreign briber, foreign bribing
- anti-bribery, anti-bribe, anti-corruption, anti-corrupt
- bribery / bribe / briber / bribing
- kleptocracy
- foreign official, public official
- cartel / cartels (added 2026-04-25 per Ellen)

Edits 2026-04-25 from Ellen's first review: removed AML / money laundering /
OFAC / SDN list / sanctions / ITAR / export controls — they pulled too much
off-topic content from broad firm feeds.

Currently used by: `GibsonDunnAdapter`, `FoleyLlpAdapter`, `MillerChevalierFcpaAdapter`
(M&C is filtered server-side via the FCPA practice-area parameter, but
event/news content can still drift). Volkov Law, Global Anticorruption
Blog, and Harvard CorpGov FCPA tag are single-topic outlets (every post
is on-topic), so they run *without* the filter.

**`ANTI_CORRUPTION_ES`** — applied to Spanish-language broad-topic feeds.
Matches:

- cohecho (bribery)
- corrupción / corrupcion
- soborno / sobornos
- lavado de activos / lavado de dinero (money laundering)
- fraude al fisco (fraud against the state)
- delitos económicos (economic crimes)
- Ley 20.393 (Chile's corporate criminal liability statute)
- funcionario público (public official)

Currently used by: `FiscaliaChileAdapter`.

**Adapters running without a keyword filter:**

- `DojFcpaActionsAdapter` — source is *already* the DOJ-curated FCPA case list, no filter needed.
- `AfpForeignBriberyAdapter` — uses AFP's own `?keys=foreign+bribery` site search; AFP filters server-side.
- `ConsejoTransparenciaClAdapter` — single-topic outlet (Chilean transparency / probity).
- `VolkovLawAdapter` — single-topic blog ("Corruption, Crime & Compliance").
- `GlobalAnticorruptionBlogAdapter` — single-topic academic blog.

If Ellen sees noise (irrelevant items) in the Excel for a particular source,
the fix is either to add a filter or tighten the existing one in
`_filters.py`. If she sees missing items (relevant cases that didn't make
it through), loosen the regex or add new keywords there.

## Findings during item 17 wave 2 (2026-04-25, possibleSources.txt expansion)

- **Generic `RssFeedAdapter` landed** as the reuse mechanism Tom asked about. New WordPress / Atom RSS sources are now ~5-line subclass declarations (URL + source_id + country, plus optional keyword regex). Used by Volkov Law and Consejo para la Transparencia in this wave.
- **httpx default User-Agent gets 403'd.** Volkov Law's WordPress nginx blocks `python-httpx/x.x` UA but accepts curl's `Mozilla/5.0`. Added a default browser User-Agent on `SourceAdapter` (Chrome on Windows). All adapters now look like a normal browser request — necessary for pilot scraping. Production polish: maybe a self-identifying UA like `LawTracker/0.1 (+https://lawmasolutions.com)` once we have a real site.
- **Sources blocked or unreachable from this dev environment** (mostly CDN bot rules, occasionally geo / IP blocks):
  - **SEC FCPA cases** — HTTP 403 on `/spotlight/fcpa/...`, `/enforce/fcpa/...`, `/spotlight/fcpa.htm`. All three blocked.
  - **OECD anti-bribery** — HTTP 403 on `/en/topics/sub-issues/anti-bribery-convention.html` and `/corruption/anti-bribery/`.
  - **CDPP, NACC, AUSTRAC** — all timed out at 30s from this environment, likely IP-range / geo blocks against non-AU traffic.
  - **ASIC** — HTTP 200 but pages are JavaScript-rendered with no inline JSON; no article cards in static HTML. Needs Playwright / headless browser.
  - **Contraloría Chile** — reachable but Liferay news-portlet structure is heavy; deferred for now (lower priority than Consejo / Fiscalía coverage).
- **Production environment will need a different access strategy** for the blocked sources: residential proxy, headless browser (Playwright), API access where available, or running from a different network. Captured for the scout-review session — Tom + Ellen decide which sources matter enough to invest in alternative access.
- **Scout state at end of wave 2:** 5 working adapters, 35 events end-to-end. DOJ 6, AFP 9, Fiscalía 0 (sparse signal), Consejo Transparencia 10, Volkov Law 10.

## Findings during item 17 wave 3 (2026-04-25, law-firm RSS expansion)

- **Probed ~60 law-firm RSS URLs across the firms in `possibleSources.txt`.** Direct results:
  - Working: **Gibson Dunn** (`/feed/`, WordPress, RSS 2.0). One firm out of ~20.
  - 404 / no exposed feed: Miller & Chevalier, WilmerHale, Paul Weiss, Latham, Cleary Gottlieb, Hogan Lovells, Freshfields, Allens, Clayton Utz, A&O Shearman, King Spalding, Lexology.
  - 403 (CDN bot block, even with browser User-Agent): Sidley, Skadden, Debevoise, Dentons, Herbert Smith Freehills, Foley LLP, Foley Hoag, Covington, Ropes & Gray, Harvard CorpGov Forum.
  - 429 (rate-limited): DLA Piper.
- **Gibson Dunn is intermittent** — returns 200 + RSS to curl but 403 to httpx in some test runs. Cloudflare appears to fingerprint TLS / connection style; httpx doesn't always pass. To make this reliable in production we'd need a TLS-fingerprint-spoofing client (`curl_cffi`) or Playwright. For pilot, keep it in `PILOT_ADAPTERS` so the scout reports the failure mode.
- **Found one academic blog beyond `possibleSources.txt`**: **Global Anticorruption Blog** (Matthew Stephenson at Harvard, `globalanticorruptionblog.com/feed/`). Single-topic, runs without keyword filter, 10 items per refresh.
- **Pattern**: most large law firms host on enterprise CMS (Sitecore / Vignette / custom) without standard RSS, OR sit behind aggressive bot protection. Subscription via firm email or scraping HTML pages directly with a headless browser are the realistic alternatives — defer for now and prioritize at item 18 review based on which firms Ellen actually wants to follow.
- **Scout state at end of wave 3:** 6–7 working adapters depending on Gibson Dunn's mood. 45 events on this run. DOJ 6, AFP 9, Fiscalía 0, Consejo 10, Volkov 10, Gibson Dunn 0 (CF blocked this run), GAB 10.

## Findings during item 17 wave 6 (2026-04-25, ES → EN translation)

- **Translation helper landed** at `src/lawtracker/translate.py`. Uses MyMemory's free translation API — no API key, no Python dep beyond httpx, fail-soft (returns original text on any failure). In-memory cache avoids retranslating duplicates within a scout run.
- **Opt-in flag on `SourceAdapter`**: `translate_summary_from: ClassVar[str | None] = None`. Set to `"es"` (or future `"fr"`/`"pt"`/etc.) and the base class translates `title` and `summary` to English on every emitted record, stashing the originals in metadata as `title_<lang>` and `summary_<lang>`.
- **Applied to FiscaliaChileAdapter and ConsejoTransparenciaClAdapter.** Live scout: Consejo's titles + summaries now arrive in English; Spanish preserved in metadata for reference. Fiscalía has zero current entries so nothing to translate yet.
- **Trade-offs for Ellen's review:**
  - MyMemory free tier ~5000 chars/day per IP; pilot scout volume is well below that.
  - Quality is community-contributed memory + machine translation — okay for general prose, occasionally clumsy on legal terminology.
  - Outgrow / quality issues → swap options: argostranslate (offline, ~250MB model, deterministic), DeepL API (paid, best quality), Google Cloud Translate (paid, well-supported). All swap behind `translate()`; adapters don't change.
  - **Translation is the cleanest first place to consider an Anthropic-API call** — Claude could translate legal Spanish to English with FCPA-domain awareness, preserving terminology like "cohecho" → "bribery" (not "corruption"). See "LLM-API opportunities" section below.

## LLM-API opportunities (open question for Tom)

Tom's standing rule: deterministic work in Python; LLM steps do "judgment and interpretation." The current pipeline is all Python; there are several places where an Anthropic API call would be a clean fit. Each would need explicit approval and adds the `anthropic` SDK as a runtime dep + an API key.

- **SEC FCPA cases prose parsing** (deferred earlier). The page is one long narrative — year headers + bolded company names + free-text paragraphs. Regex would be brittle; Claude could read the page and emit structured records. **Highest-value LLM use** in the current backlog.
- **Per-event summary generation.** Many sources emit records with `summary=None` because no clean summary text is available (DOJ list page, AFP search results). Claude could read the linked detail page and write a one-line "why this matters" for the dashboard row. Big UX win for Ellen's triage.
- **Industry / resolution-type classification** for DOJ press releases. Currently keyword regex; Claude could read the press release prose and classify with higher accuracy and less brittleness.
- **Translation** (current pilot uses MyMemory). Claude with an FCPA-domain prompt would handle legal terminology better than commodity translation.
- **Cross-source dedup.** When DOJ press releases overlap with FCPA-actions list entries (and FCPA Blog and Volkov Law cover the same case), Claude could match them by reading both. Currently scoped to "post-storage."

Trade-offs of LLM steps (across all of the above):
- Adds `anthropic` dep + `ANTHROPIC_API_KEY` env var.
- Cost — pilot-scale usage is cents per scout run; bigger volumes scale.
- Non-determinism — small variability between runs (Claude is mostly stable but not byte-identical).
- Latency — each call adds 1-3s; 50 events with summaries = ~1-2 min added to scout time.
- Auditability — Ellen sees the LLM's output, not the raw source. Need to keep raw source preserved for verification.

## LLM-as-judge for event-noise (2026-04-25, Tom's wave-3 fix)

Tom flagged that even with a widened regex + post-enrichment filter, M&C
podcast publications like `EMBARGOED!: South of the Border` were still
slipping through — the regex couldn't tell from the title alone. His
suggestion: have the LLM, while it's already reading each article,
classify whether the article is event-noise (podcast / webinar /
conference / etc.) and flag it for drop.

How it works now:

1. The summary system prompt instructs Claude to return one of two
   JSON shapes:
   - `{"drop": true, "reason": "<short phrase>"}` — for podcast
     episodes, webinars, CLE webcasts, conference promos, networking
     gatherings, panel discussions, fireside chats, awards
     announcements, etc.
   - `{"drop": false, "summary": "<1-2 sentence summary>"}` — for
     substantive enforcement / policy / case content.
2. `enrich_summaries` parses the JSON, drops events with `drop=true`,
   and uses the summary otherwise.
3. Both decisions are cached so repeat runs skip the LLM call entirely.
4. Backward-compatible with the previous cache format (entries without
   a `drop` field are treated as `drop=false`).

Three layers of event-noise filtering now stack:

- **Parse-time regex** (cheapest, runs always): catches obvious patterns
  in title / summary / URL — `webinar`, `podcast`, `Conference:`,
  `RSVP`, `summit`, etc. Drops items before the LLM is even consulted,
  saving API spend on obvious cases.
- **LLM-as-judge** (most accurate, anthropic mode only): catches the
  cases where the title is opaque but the article body reveals the
  nature.
- **Post-enrichment regex** (safety net): re-runs the parse-time regex
  over LLM-generated summaries, catching anything where the LLM
  mentions "podcast" but didn't return `drop=true`.

In stub mode, the stub returns valid JSON `{"drop": false, "summary":
"[STUB summary] ..."}` so the parser path is exercised end-to-end.

## Per-event summary + caching (2026-04-25, Ellen's wave-2 ask)

Ellen: "The LLM will need to go into each of the articles and provide a
summary - we should have a caching system so it doesn't have to
reevaluate the same article multiple times and it knows to skip over
articles that have already been analyzed."

How it works:

- `src/lawtracker/llm_cache.py` — generic disk-backed JSON cache
  (`JsonCache`). One file per cache; loaded on construct, written
  through after every put.
- `src/lawtracker/article_summary.py` — `enrich_summaries(events, cache)`
  iterates events, looks up `mode|dedup_key` in the cache, and either
  reuses the cached summary or generates a fresh one.
- Cache file: `data/scout/.cache/summaries.json` (gitignored).
- Cache keys are mode-stamped (`stub|...` vs `anthropic|...`) so
  switching between stub and live LLM doesn't reuse stub placeholders
  as if they were real analyses.

Per-mode behavior:

- **stub**: synthesizes a deterministic placeholder summary from event
  metadata (no HTTP fetch, no API spend). Visible at a glance — every
  stub starts with `[STUB summary]`.
- **anthropic**: fetches the article URL via curl_cffi (handles both
  plain sites and Cloudflare-protected ones), strips chrome, sends
  title + body to Claude. ~1-2 sentence summaries, FCPA-practitioner
  framing.
- **off**: leaves existing summaries untouched. Cache untouched.

When the LLM replaces an existing adapter-provided summary (e.g. an RSS
description), the original is preserved at `metadata.summary_source` for
reference — no information lost.

Cache verification on a second run: 0 stub regenerations across 83
events; cache lookup is the path for everything.

## LLM mode (2026-04-25, stub-first per Tom)

The scout calls Claude in two places: post-aggregation analysis (writes `analysis.md`) and the SEC FCPA cases adapter (extracts structured records from a narrative page). Both go through `src/lawtracker/llm.py`.

Three modes via `LAWTRACKER_LLM_MODE` env var (or `--llm-mode` CLI flag):

- **`stub`** (default) — returns the caller's `stub` argument verbatim. No API spend, no `anthropic` SDK required. Tom uses this during design iteration so prompts can be refined without burning tokens. The stub responses are obvious-but-plausible: analysis is a markdown placeholder with `[STUB LLM RESPONSE]` markers; SEC adapter emits 2 placeholder records labeled `[STUB] SEC v. ...`.
- **`anthropic`** — calls the real Claude API. Lazy-imports the `anthropic` SDK (raises a clear `RuntimeError` if not installed). Reads `ANTHROPIC_API_KEY` from env.
- **`off`** — returns `""`. Useful for measuring how the rest of the pipeline behaves without LLM contribution.

When Tom is ready to flip on real Claude calls:

1. `pip install anthropic` (and add to `pyproject.toml` runtime deps).
2. `export ANTHROPIC_API_KEY=...`
3. `lawtracker scout --llm-mode=anthropic`

The stub-first design is preserved — tests use stub mode by default via `tests/conftest.py` so the suite never hits the API.

## Findings during item 17 wave 5 (2026-04-25, curl_cffi unlock)

- **`curl_cffi` runtime dep approved by Tom.** Drop-in client that mimics Chrome's TLS handshake (JA3 hash) — beats Cloudflare fingerprint blocks. Wired into `SourceAdapter` as an opt-in `use_curl_cffi: ClassVar[bool] = False` flag plus `curl_cffi_impersonate: ClassVar[str] = "chrome120"`. When True, `poll()` builds a `curl_cffi.requests.Session` instead of an `httpx.Client`. The two duck-type the same `.get(url) → response.{status_code,text}` interface, so no other framework code changed.
- **`parse(html, client)` signature relaxed** from `httpx.Client` to `Any` to accept either client transparently. All adapters updated.
- **Re-probed every previously-403'd source with curl_cffi**:
  - **Newly accessible (HTTP 200):** SEC FCPA cases, Foley & Lardner LLP RSS, Skadden (HTML AngularJS shell — not actual feed), Covington (HTML — same as before), Harvard CorpGov FCPA-tag RSS.
  - **Still blocked / no feed:** OECD anti-bribery (404 — site moved), FCPA Blog (still 401, auth wall not bot block), Sidley / Debevoise / Dentons / Herbert Smith Freehills / Ropes & Gray / DLA Piper (404 — these firms genuinely don't expose RSS).
- **Built two new RSS adapters:**
  - `FoleyLlpAdapter` — Foley & Lardner LLP `/feed/`, mixed-topic so uses `ANTI_CORRUPTION_EN`. `use_curl_cffi = True`. 0 events on this snapshot — feed currently has Sripetch / cannabis / IP-podcast posts; no anti-corruption hits today. Will catch matching posts as they appear.
  - `HarvardCorpGovFcpaAdapter` — Harvard Law School Forum on Corporate Governance, FCPA-tagged feed only. Single-topic, no filter. `use_curl_cffi = True`. 0 events on this snapshot — the FCPA tag genuinely has no current entries.
- **Both Miller & Chevalier and Gibson Dunn now flow live** via `use_curl_cffi = True` (from 0 events to 60 + 1 respectively).
- **SEC FCPA cases adapter deferred.** Page is reachable but is a single long narrative document — year headers + free-text case paragraphs, not a structured list. Parser will need careful regex/prose work; deferred to its own commit.
- **Scout state at end of wave 5:** 10 adapters (8 working with non-zero events), 106 events. DOJ 6, AFP 9, Fiscalía 0, Consejo 10, Volkov 10, Gibson Dunn 1, GAB 10, Miller & Chevalier 60, Foley LLP 0, Harvard CorpGov 0.

## Findings during item 17 wave 4 (2026-04-25, Miller & Chevalier HTML pattern)

- **Tom flagged a path I'd missed**: many firms expose their FCPA-practice content via filterable HTML search pages even when they don't expose RSS. Miller & Chevalier's `/search?related_practice=8965&content_types[0]=publication` returns the firm's FCPA Winter / Autumn Reviews + client alerts cleanly.
- **Built `MillerChevalierFcpaAdapter`** that fetches publications + news + events in one poll via the multi-URL `urls` property. Drupal-driven; clean `<div class="search_result">` cards with date / title / sub-type. Fixture-tested.
- **Same Cloudflare TLS-fingerprint block** Gibson Dunn hits applies to Miller & Chevalier — returns 200 to curl during fixture capture, 403 to httpx at scout time. The block is on JA3 hash (TLS handshake fingerprint), not User-Agent or HTTP headers.
- **Generalizable insight**: the 404-RSS firms in possibleSources.txt (WilmerHale, Paul Weiss, Latham, Cleary, Hogan Lovells, Freshfields, Allens, Clayton Utz, KWM, A&O Shearman, etc.) likely have similar HTML patterns. Per-firm investigation needed; defer until item 18 picks priority targets.
- **Three unblock paths for Tom to choose at item 18**:
  1. **`curl_cffi`** as a runtime dep (drop-in httpx replacement, mimics curl TLS fingerprint, ~1 hour swap). Most pragmatic.
  2. **Playwright** headless browser (~half-day setup, beats CF + JS-rendered sites like ASIC).
  3. **Email-subscription parsing** for firm distribution lists (operational, no scraping).
