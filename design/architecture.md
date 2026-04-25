# LawTracker — Architecture

Status: locked 2026-04-25 with Tom's approval. This note frames everything else; revisit before drifting.

## Product shape

LawTracker is a web dashboard that monitors **how the US government enforces and interprets anti-corruption law**, with FCPA and FEPA as the priority pilot scope. Pilot user is Ellen.

The statutes themselves are out of scope — they change rarely and are not the signal Ellen needs. What she needs is:

- **Enforcement actions** — DOJ and SEC FCPA cases as they are filed.
- **Government messaging** — policy announcements, senior-official speeches, press releases that signal enforcement priority and strategy.
- **Compliance expectations** — changes to DOJ/SEC corporate-enforcement guidance and policy memos.

Future scope (not pilot): trusted third-party trackers (law-firm alerts, FCPA Blog, Stanford FCPA Clearinghouse, etc.) under the same adapter framework; expansion to other US anti-corruption statutes (18 U.S.C. § 201 domestic bribery, AML Act, Magnitsky/OFAC) and other jurisdictions (UK Bribery Act, EU directives) once the pilot proves out.

## Two source shapes

Source adapters fall into two categories. The data model handles both first-class:

- **Document sources** — a single URL whose content evolves in place. Pattern: snapshot the rendered text on each poll; hash and diff against the previous snapshot; surface a `LawChange` when the diff is non-trivial. Examples: DOJ FCPA Resource Guide, JM 9-47.120, ECCP.
- **Event sources** — a list page (or feed) where new entries appear over time. Pattern: extract entries on each poll; reconcile against the stored set; emit a `LawEvent` for each new entry. Examples: DOJ FCPA enforcement actions list, SEC FCPA cases, DOJ press releases, senior-official speech feeds.

A single source can be both — e.g. a list page whose intro blurb is also tracked as a document. Adapters declare what they emit.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Host | Fly.io | Free tier covers PoC; always-on workers + managed Postgres available; clear scale path. |
| Web framework | FastAPI | Async (good for many concurrent source polls); same app serves HTML and JSON, so an API is "free" when SMS / mobile / external integrations come. |
| UI | Jinja2 + HTMX + Tailwind | Server-rendered, no SPA build pipeline. HTMX covers interactivity needs without a framework. |
| Database | SQLite on a Fly volume during PoC; migrate to managed Postgres when adding auth / multi-user. | One user, hourly writes — SQLite is correct. SQLAlchemy + Alembic from day one so the migration is config, not rewrite. |
| Scheduler | APScheduler in-process | Hourly poll loop in the same Python process. Move to a separate worker or Celery + Redis when load grows. |
| Scraping | httpx + beautifulsoup4 + Pydantic record models | Already in `pyproject.toml`. Per-source adapters under `src/lawtracker/sources/`. |
| Notifications | Adapter interface from day one; no concrete adapters in pilot | Email (Resend or Postmark) and SMS (Twilio) bolt on after the dashboard ships. |
| Auth | None for pilot — basic auth or IP allowlist gate | One user. Magic-link email when multi-user lands. |
| DNS | `www.lawmasolutions.com` CNAME → Fly app; apex via Fly A/AAAA | Squarespace remains registrar; we point records. |

## Data model (sketch)

Concrete schema lives in code; this is the conceptual shape:

- `Source` — adapter identity, URL, kind (`document` | `event_list` | `both`), poll cadence, active flag.
- `Snapshot` — a captured rendering of a `Source` at a point in time. Stores raw HTML, extracted text, content hash, fetched-at timestamp.
- `LawChange` — emitted when a `document`-kind source's hash changes meaningfully. References two `Snapshot`s; carries the diff.
- `LawEvent` — emitted when an `event_list`-kind source produces a new entry. Carries entry URL, title, date, source-specific metadata blob.

The web app reads from these. The poller writes to them. They are the contract between the two halves of the system.

## Repo layout (additions to ship)

```
src/lawtracker/
  config.py          # settings (env-driven)
  db.py              # SQLAlchemy session + engine
  models.py          # Source, Snapshot, LawChange, LawEvent
  sources/
    __init__.py
    base.py          # SourceAdapter ABC
    doj_fcpa_actions.py
    ...
  poller.py          # APScheduler loop; per-source dispatch
  notify/
    __init__.py
    base.py          # Notifier ABC (no concrete adapters in pilot)
  web/
    app.py           # FastAPI app
    routes.py
    templates/
    static/
migrations/          # Alembic
Dockerfile
fly.toml
```

## What this note does NOT decide

- Specific HTML/CSS layout of the dashboard. Defer to dashboard / detail-view items.
- Per-source extraction strategy (DOJ press-release list has weird HTML; some pages may eventually need playwright). Defer to per-adapter design notes as edge cases hit.
- Notification UX. Defer to the notification framework item.
- Authentication choice when multi-user lands. Defer.
