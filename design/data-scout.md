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
- AML, anti-money-laundering, money laundering
- OFAC, SDN list, sanctions, sanctions enforcement
- ITAR, export controls

Currently used by: `GibsonDunnAdapter`. Volkov Law and Global Anticorruption
Blog are single-topic outlets (every post is on-topic), so they run *without*
the filter.

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

## Findings during item 17 wave 4 (2026-04-25, Miller & Chevalier HTML pattern)

- **Tom flagged a path I'd missed**: many firms expose their FCPA-practice content via filterable HTML search pages even when they don't expose RSS. Miller & Chevalier's `/search?related_practice=8965&content_types[0]=publication` returns the firm's FCPA Winter / Autumn Reviews + client alerts cleanly.
- **Built `MillerChevalierFcpaAdapter`** that fetches publications + news + events in one poll via the multi-URL `urls` property. Drupal-driven; clean `<div class="search_result">` cards with date / title / sub-type. Fixture-tested.
- **Same Cloudflare TLS-fingerprint block** Gibson Dunn hits applies to Miller & Chevalier — returns 200 to curl during fixture capture, 403 to httpx at scout time. The block is on JA3 hash (TLS handshake fingerprint), not User-Agent or HTTP headers.
- **Generalizable insight**: the 404-RSS firms in possibleSources.txt (WilmerHale, Paul Weiss, Latham, Cleary, Hogan Lovells, Freshfields, Allens, Clayton Utz, KWM, A&O Shearman, etc.) likely have similar HTML patterns. Per-firm investigation needed; defer until item 18 picks priority targets.
- **Three unblock paths for Tom to choose at item 18**:
  1. **`curl_cffi`** as a runtime dep (drop-in httpx replacement, mimics curl TLS fingerprint, ~1 hour swap). Most pragmatic.
  2. **Playwright** headless browser (~half-day setup, beats CF + JS-rendered sites like ASIC).
  3. **Email-subscription parsing** for firm distribution lists (operational, no scraping).
