# Admin app — design note (item 21)

Living design note for the FastAPI admin app. Tom approved the architecture
2026-04-28; admin-side static mockups landed the same day at
`data/scout/admin/{analysis,sources}.html`. Live FastAPI buildout is the
next major work block.

**Primary admin user is Ellen** (clarified by Tom 2026-04-28). She does the
review, edits, and publishes — the dashboard must be intuitive for a
non-developer. Tom retains admin access too (co-admin model). UX language
in the mockup uses plain English ("Hide Source Link", "Generate new
analysis", "Publish to site") rather than developer terminology
("exclude", "re-run", "deploy"). User-facing terminology updated by
Tom 2026-04-28: "Source Link" replaces the earlier "article" wording
across the admin UI.

## Why this exists

The curation loop Tom wants — eyeball the raw events, manually drop Source Links
that dilute the LLM analysis, re-run the LLM, review the new draft, edit
country sections, publish — only works with a server. Static rendering
(item 20) carried us through layout/visual feedback; this item turns the
mockup into an interactive admin experience.

## Scope

In-scope:

- Two-tier auth: shared password (public), magic-link (admin).
- Source-Link-level exclusions persisted to disk; applied to both Sources
  rendering and LLM analysis input.
- Per-country edit textareas on the admin Analysis page.
- "Re-run analysis" button that calls `analyze` against the filtered
  event set; clears any pending country edits.
- "Publish" button that promotes draft → public file state.
- Public pages render from `data/scout/public/`; admin pages render from
  `data/scout/draft/`.

Out-of-scope (for this item):

- Per-event summary editing on the Sources page.
- Cost estimates before the re-run button fires.
- Multi-admin auth.
- Storage in a real database (item 4 territory; pilot stays file-based).
- Real deploy hook (item 9).

## Decisions (locked 2026-04-28)

### 1. Stack: FastAPI + Jinja2 + HTMX + Tailwind

Already in the roadmap (item 6). Jinja2 templates reuse the markup we
shipped as static HTML in item 20. HTMX handles the click-to-exclude
+ re-run + publish interactions without a SPA build step. Tailwind
continues via CDN during pilot; bundle later if performance demands it.

### 2. Two-tier auth

- **Public** (`/`, `/sources`): gated by a single shared password. User
  hits the site, sees a password prompt, types it once, gets an
  HTTP-only cookie that survives until they clear cookies. Tom shares
  the password with Ellen + clients out-of-band (Signal, verbal,
  whatever). Anyone he shares with can re-share; no per-user
  revocation. Acceptable for pilot.
- **Admin** (`/admin/*`): magic-link to allowlisted emails. Allowlist
  is `ADMIN_EMAILS` env var (comma-separated) — currently Ellen
  (primary) and Tom (co-admin). User enters email at the login page;
  if the email is on the allowlist, server emails a one-time URL
  with a token; clicking sets an admin session cookie (longer-lived
  than public, e.g. 7 days). Token is single-use, 15-minute expiry.
  Magic-link emails go through Resend (see "External-service
  walkthrough" below).

Local-dev mode (`LAWTRACKER_DEV=1`): both gates disabled so iteration is
fast; we verify auth manually before deploy.

### 3. Draft / public file split

```
data/scout/
├── draft/              # admin working state
│   ├── events.jsonl    # latest scout output
│   ├── exclusions.json # {"excluded": ["dedup_key_1", "dedup_key_2", ...]}
│   ├── edits.json      # {"United States": "edited markdown...", ...}
│   └── analysis.md     # latest LLM draft (raw, edits NOT applied)
└── public/             # what the public pages render from
    ├── events.jsonl    # filtered through exclusions at publish time
    └── analysis.md     # baked: edits applied + scaffold-stripped
```

Scout writes to `draft/`. Analyze reads `draft/events.jsonl` filtered
through `draft/exclusions.json`, writes `draft/analysis.md`. Render
(static HTML) is replaced by Jinja2 templates that render directly from
`draft/` (admin) or `public/` (public). Publish copies/bakes
`draft/` → `public/`.

### 4. Exclusion model

Source-Link-level only (one Source Link = one event). One JSON file: `draft/exclusions.json` with shape
`{"excluded": [{"dedup_key": "...", "hidden_at": "ISO-8601"}, ...]}`.
The `hidden_at` timestamp drives the 60-day auto-purge (see below).

Applied to both:

- **Sources rendering**: hidden events are visually removed from the
  main feed but appear in the "Hidden Source Links" drawer at the
  bottom of the admin Source Links page. The public Sources page
  hides them outright.
- **LLM input**: hidden events are filtered out of the JSON payload
  sent to Claude during `analyze`.

`dedup_key` survives re-scouting (it's set by the adapter from the
canonical URL or equivalent), so exclusions persist across scout runs.
If a hidden Source Link's `dedup_key` no longer appears in the event set,
silently skip it; show a count in the admin UI of "stale exclusions"
so Ellen can clean up.

#### Hide / Undo / Restore UX (Tom 2026-04-28)

Live in the static mockup at `data/scout/admin/sources.html` using
vanilla JS + `sessionStorage`. Live FastAPI version uses the same
markup with click handlers POSTing to `/admin/exclude/{dedup_key}` and
`/admin/restore/{dedup_key}`.

- **Click Hide Source Link** on any card → the Source Link fades out
  of its country section.
- **Toast** appears bottom-right for 10 seconds: _"'[Source Link
  title]' hidden — Undo"_. Click Undo to restore immediately. (Toasts
  are per-Source-Link; rapid Hides replace the previous toast.)
- **Past the 10s window** → the Source Link shows up in a "Hidden
  Source Links ([N])" collapsible section at the bottom of the page
  (collapsed when empty, expanded automatically when count > 0). Each
  hidden item lists title + a Restore button.
- **State persists** across page reloads in `sessionStorage` (mockup)
  / server-side JSON (live).

#### 60-day auto-purge

In the live app, hidden Source Links are fully deleted after 60 days
from `hidden_at`. Garbage control — Ellen doesn't need a permanent
record of every Source Link she ever dismissed. Implementation: a
small startup hook (or scheduled cleanup task once item 5's poll
loop lands) walks `exclusions.json` and drops entries older than 60
days. After purge, the underlying Source Link may still appear in
fresh scout output; if Ellen still doesn't want it, she hides it
again.

The 60-day window is per-`hidden_at`, not per-`scout-run`, so a
Source Link hidden today survives 60 days of repeated scouts.

### 5. Edit model

Per-country edits keyed by exact country heading text:

```json
{
  "United States": "## United States\n\n- Edited bullet 1\n- Edited bullet 2\n",
  "Brazil": "## Brazil\n\n- ...\n"
}
```

Stored in `draft/edits.json`. The admin Analysis page renders each
country section with an edit textarea pre-populated from `edits.json`
if a key matches; otherwise from the raw LLM output in
`draft/analysis.md`. Saving a textarea updates the JSON.

**Re-run discards edits.** When Tom clicks "re-run analysis", the new
LLM output overwrites `draft/analysis.md`, and `draft/edits.json` is
truncated to `{}`. Rationale: re-running is usually because Tom removed
noisy Source Links and wants the LLM to redo the analysis on the clean
set; whatever edits he'd made before don't necessarily apply. The
simpler model is fewer footguns.

If a country heading appears in `edits.json` but not in the new LLM
output (e.g. Claude no longer emits "Australia" because the only AUS
event was excluded), the orphan edit is dropped at publish time; flag
it in the admin UI before publish.

### 6. Publish

Publish in dev/pilot mode:

1. Read `draft/events.jsonl`, `draft/exclusions.json`,
   `draft/analysis.md`, `draft/edits.json`.
2. Filter events: exclude those with `dedup_key` in
   `exclusions.json["excluded"]`.
3. Bake analysis: parse `draft/analysis.md` into per-country sections;
   for each section heading, if a key matches in `edits.json`, replace
   the section body with the edited markdown; otherwise keep the LLM
   output. Reassemble. Drop any country sections whose only events
   were excluded.
4. Write filtered events + baked analysis to `public/`.
5. (Future post-deploy) Trigger deploy hook. Structured so this is one
   function call to swap in.

Confirmation step: publish shows a diff summary first ("publishing 87
events; 12 excluded; 4 country sections, 2 with edits") and requires
explicit click-to-confirm. Avoids accidental publish.

### 7. UI / UX

Admin-side static mockups landed 2026-04-28 at
`data/scout/admin/{analysis,sources}.html`. Open by double-click;
buttons are non-functional (`alert()` stubs explain what they would
do). The mockup is the visual + UX spec for the live FastAPI build.

Header (every admin page):

- Brand: `LawTracker · Admin`
- Tabs: **Analysis** / **Source Links** (note: "Source Links" not
  "Sources" — Ellen-friendly plain-language label set by Tom
  2026-04-28). Underlined when active.
- Right-side action buttons: **Generate new analysis** (slate
  outline) / **Publish to site** (emerald solid).
- Trailing crumb: `View public site →` for quick switch out.

**Admin Source Links** (`/admin/sources`): country-grouped feed
(same ordering as public). Banner at top: "{N} Source Links available
· {K} currently hidden". Help text: "Hide Source Links that aren't
relevant or might dilute the analysis. Hidden Source Links won't
appear on the public site or be sent to the analysis." Each Source
Link card has a right-side **Hide Source Link** button. Live wiring:
button POSTs to `/admin/exclude/{dedup_key}`, page re-renders with
the Source Link dimmed and the button changed to **Restore**.

**Admin Analysis** (`/admin/analysis`): country sections in a
two-column layout — left column shows the rendered preview (what
readers will see); right column is a markdown textarea pre-filled with
the section source. Per-country **Save** button (amber). Banner at
top: "Analysis ready for review · {N} Source Links fed · {K} edits saved
· not yet published". Help text explains the workflow. Live wiring:
Save POSTs to `/admin/edit/{country}`; textarea remains the source of
truth until next re-run.

**Generate new analysis** (header button, every admin page): POSTs to
`/admin/rerun`. Shows a spinner; on completion redirects back to
`/admin/analysis`. Flash message confirms event count fed to the LLM
and warns that any pending edits were discarded.

**Publish to site** (header button, every admin page): GETs
`/admin/publish` which renders a confirmation page summarizing what's
about to change ("publishing 87 Source Links, 12 hidden; 4 country
sections, 2 edited"). Confirm button POSTs and bakes draft → public.

Container width: `max-w-6xl` on admin (vs. `max-w-4xl` on public) to
make room for the side-by-side preview/edit columns on the Analysis
page.

### 8. Defaults and answers to Tom's earlier questions

| Question | Answer |
|---|---|
| Exclusion granularity | Source-Link-level only (drop from both Sources + LLM) |
| Cost estimate before re-run | No; just run on click |
| Publish target | Local file copy in dev; deploy hook in prod (deferred) |
| Admin auth | Magic-link to Tom only |
| Public auth | Shared password |
| Per-event summary editing | Out of scope |
| Re-run behavior with pending edits | Discard edits |

## External-service walkthrough — Resend (magic-link emails)

Tom has not set up an email-sending service. Resend is the simplest fit
(free tier 3K emails/month; clean Python SDK). Step-by-step:

1. **Create account**: go to https://resend.com, sign up with Tom's
   email. Free tier requires no payment method.
2. **Verify a sending domain**: in the Resend dashboard, "Domains" →
   "Add Domain". Use `lawmasolutions.com` (the production domain). You
   will be given DNS records (SPF, DKIM, optional DMARC) to add at
   Squarespace. Each record is shown with the value to paste.
   - At Squarespace: Settings → Domains → lawmasolutions.com → DNS
     Settings → "Add Custom Record" for each entry.
   - Wait for Resend to show "Verified" (typically 5-30 min).
   - For pre-deploy local testing only, you can skip domain
     verification and use `onboarding@resend.dev` as the from address;
     it sends to any verified address but rate-limits to 100/day.
3. **Get an API key**: Resend dashboard → "API Keys" → "Create API
   Key" → name it `lawtracker-prod` (or `-dev`). Copy the value once
   shown — it is not retrievable later.
4. **Set the env var**:

   ```powershell
   [Environment]::SetEnvironmentVariable("RESEND_API_KEY", "re_...", "User")
   ```

   Close + reopen PowerShell. Verify: `$env:RESEND_API_KEY` echoes the
   key.
5. **Set the admin email allowlist** (Ellen + Tom; comma-separated):

   ```powershell
   [Environment]::SetEnvironmentVariable("ADMIN_EMAILS", "ellen@...,tom@...", "User")
   ```

6. **Set the public shared password** (same env-var pattern):

   ```powershell
   [Environment]::SetEnvironmentVariable("LAWTRACKER_PUBLIC_PASSWORD", "<long random string>", "User")
   ```

7. **Test**: when item 21 ships, run `lawtracker email-test
   tom@...` (we'll add this) — sends a one-line test email to the
   given address. If you get the email, Resend + DNS are wired
   correctly.

If Resend free-tier limits become a problem (>3K emails/month is
unlikely for this use case), Postmark and SendGrid are drop-in
swaps; SDK abstraction in `src/lawtracker/email.py` will isolate the
provider.

## Test strategy

- Unit-test exclusion logic against fake events.
- Unit-test edit baking: given `edits.json` + `analysis.md`, produce
  the expected baked markdown.
- Unit-test publish: assert `draft/` is unchanged after publish; assert
  `public/` reflects exclusions + edits.
- FastAPI route tests with `httpx.AsyncClient`: auth gates,
  click-to-exclude flow, re-run flow (mocked LLM), publish flow.
- Auth tests: hit `/admin/*` without session → 401; hit `/` without
  password cookie → 401; magic-link token consumed once.
- No live emails in CI: stub the email-send adapter the same way we
  stub Anthropic.

## Open questions

None at this time. The four sub-decisions Tom flagged 2026-04-28 are
all answered (see decisions table above).

## Future polish (not item 21 scope)

- LLM-derived per-event country tag persisted into `events.jsonl`, so
  the Sources page can group by the same country the Analysis page
  uses. Currently the Sources page groups by adapter-level `country`,
  which is unreliable (a US blog covering a Brazilian case is tagged
  US). Defer until Ellen's feedback specifically calls it out.
- Bulk-exclude UI ("exclude all from this source" / "exclude all
  podcasts").
- Edit history (track Tom's per-section edits over time).
- Per-event summary editing (Tom said no for now; revisit if Ellen
  asks).
