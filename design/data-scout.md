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
