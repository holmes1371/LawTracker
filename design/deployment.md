# LawTracker — Deployment walkthrough

How LawTracker gets to lawmasolutions.com over HTTPS, with email and
secrets configured. Walkthrough done end-to-end with Tom 2026-04-29
across 7 phases. This note is the source of truth for replaying any
of it (e.g. spinning up a staging environment, recovering from a
disaster, onboarding a co-maintainer).

## Stack at a glance

- **Host**: Fly.io (`iad` region, US East / Ashburn). App name
  `lawtracker`. Free tier: shared CPU, 256MB memory, scales to zero
  when idle.
- **Domain**: lawmasolutions.com, registered at Squarespace (which is
  also where DNS is managed).
- **Email**: Resend (`us-east-1`), used for magic-link admin auth +
  transactional email. Sending-only API key; domain verified for
  DKIM + SPF + bounces.
- **HTTPS**: Let's Encrypt cert auto-provisioned + auto-renewed by
  Fly. 90-day cert; Fly renews at the 60-day mark.
- **Public URLs**: lawmasolutions.com and www.lawmasolutions.com
  (both served by the same Fly app). Internal alias
  lawtracker.fly.dev kept for diagnostics.

App config in `fly.toml`; container in `Dockerfile`; entry point in
`src/lawtracker/web.py`. Secrets set with `fly secrets set` (not
committed to git).

## Phase 1 — Fly.io account

1. https://fly.io → Sign Up (top right). Email + password or GitHub
   OAuth — either works.
2. Verify the email if email-signup.
3. **Add a payment method.** Required even on the free tier (Fly
   wants a card on file to deter abuse). Free tier = 3 small VMs +
   3GB volume + 160GB outbound; pilot usage stays inside it.
4. Note your organization slug — usually `personal` (lowercase).

## Phase 2 — Resend account

1. https://resend.com → Sign Up.
2. After signup, the dashboard nudges to "Add and verify a domain" —
   skip; we do this in Phase 7 alongside other DNS work.

## Phase 3 — flyctl CLI install + login

PowerShell:

```powershell
# Install
iwr https://fly.io/install.ps1 -useb | iex
```

**Close and reopen PowerShell** so PATH picks up the new binary.

```powershell
fly version          # should print v0.X.X
fly auth login       # opens browser, sign in with the Phase 1 account
fly auth whoami      # verify
```

## Phase 4 — FastAPI hello-world + Dockerfile

Files committed at SHA `5d8231d`:

- `src/lawtracker/web.py` — FastAPI app exposing `/` (HTML hello)
  and `/health` (JSON for Fly's load balancer).
- `Dockerfile` — single-stage `python:3.12-slim`, installs from
  `pyproject.toml`, listens on internal port 8080.
- `.dockerignore` — excludes `.git`, `.venv`, `data/`, design notes,
  tests, caches; keeps `README.md` (referenced by pyproject).
- `pyproject.toml` — added `fastapi >= 0.110` and
  `uvicorn[standard] >= 0.27` to runtime deps.

Local test before deploy:

```powershell
py -m pip install -e ".[dev]"
py -m uvicorn lawtracker.web:app --reload
# visit http://localhost:8000 and /health and /docs
```

## Phase 5 — First Fly deploy

Avoid the `fly launch` interactive flow if you have an existing
`fly.toml`; it's confusing and the prompts have changed across
versions. Hand-write the config and use `fly apps create` +
`fly deploy` directly.

`fly.toml` committed at SHA `397e890`. Highlights:

- `app = "lawtracker"` — auto-claimed during the first launch
  attempt; we kept it.
- `primary_region = "iad"`.
- `[http_service]` with `internal_port = 8080`, `force_https = true`,
  `auto_stop_machines = "stop"`, `auto_start_machines = true`,
  `min_machines_running = 0` (scales to zero when idle).
- `[[http_service.checks]]` probing `/health` every 30s.
- `[[vm]]` with shared CPU, 256MB memory.

Deploy:

```powershell
fly deploy
```

Takes ~2-3 minutes. Builds the image (locally if Docker is running,
otherwise on Fly's remote builder), pushes to Fly's registry, boots
a VM, runs health checks, swaps traffic.

After deploy:

```powershell
fly status        # see machine state
fly logs          # tail logs
```

App is reachable at https://lawtracker.fly.dev.

## Phase 6 — Custom domain + DNS at Squarespace

### Get the IP addresses + start cert provisioning

```powershell
fly ips list
fly certs create lawmasolutions.com
fly certs create www.lawmasolutions.com
```

`fly ips list` outputs the public IPv4 + IPv6 addresses your app is
reachable on. `fly certs create` registers a cert request — it
prints the recommended DNS records and starts the Let's Encrypt
flow.

Example values (your IPs will differ):

- IPv4: `66.241.125.32` (shared)
- IPv6: `2a09:8280:1::10d:ecbc:0` (dedicated — Fly may give you one
  for free)

### Squarespace DNS quirks

Squarespace's DNS UI uses the columns **TYPE / NAME / DATA / TTL /
PRIORITY**. Notes:

- **NAME field requires a value.** Leaving it blank for the apex
  fails validation — use `@` instead.
- The DATA column is labeled **IP ADDRESS** when TYPE is A; it
  renames to a generic field for TXT / CNAME / MX. Just paste the
  value either way.
- Squarespace expands compressed IPv6 addresses
  (e.g. `2a09:8280:1::10d:ecbc:0` becomes
  `2a09:8280:1:0:0:10d:ecbc:0`) — same address, leave it alone.
- **PRIORITY** column shows a dash for non-MX records; it's only
  needed for MX (use `10` for Resend's MX).
- **Squarespace's default records** for the domain (A records on `@`
  pointing to Squarespace IPs, CNAME on `www` pointing to
  `ext-cust.squarespace.com`) **must be deleted** if present, or
  they'll conflict with the Fly records.

### Records to add for Fly

| TYPE | NAME | DATA | PRIORITY |
|------|------|------|----------|
| A    | `@`  | `<your IPv4>`  | — |
| AAAA | `@`  | `<your IPv6>`  | — |
| A    | `www` | `<your IPv4>` | — |
| AAAA | `www` | `<your IPv6>` | — |

### Verify

DNS propagates in 5-15 minutes (sometimes faster). Check:

```powershell
fly certs check lawmasolutions.com
fly certs check www.lawmasolutions.com

nslookup lawmasolutions.com 8.8.8.8
nslookup www.lawmasolutions.com 8.8.8.8
```

Look for `Configured: true` and an `Issued` timestamp on the certs.
Hit https://lawmasolutions.com in a browser to confirm.

## Phase 7 — Resend domain verification + API key

### Add the domain

1. Resend → Domains → **Add Domain**.
2. Enter `lawmasolutions.com`.
3. Region: **us-east-1** (matches Fly's `iad` for low latency).
4. Click Add. Resend lands on the domain detail page with three DNS
   records to add.

### Records to add at Squarespace

(Values are unique per Resend account; copy from the domain page —
the displayed `[...]` is just truncation, click the copy button to
get the full string.)

| TYPE | NAME | DATA | PRIORITY |
|------|------|------|----------|
| TXT  | `resend._domainkey` | `p=MIGfMA...wIDAQAB` (long DKIM key) | — |
| MX   | `send`              | `feedback-smtp.us-east-1.amazonses.com` | `10` |
| TXT  | `send`              | `v=spf1 include:amazonses.com ~all` | — |

**Important**: in NAME, type exactly `resend._domainkey` and `send`.
Squarespace appends `.lawmasolutions.com` automatically; if you type
`send.lawmasolutions.com`, you end up with
`send.lawmasolutions.com.lawmasolutions.com`.

### Verify

Back in Resend, the domain page polls every ~30s. The status
progression is **Domain added → DNS verified → Domain verified**.
The list view at /domains may stay "Pending" for a few minutes after
the detail view shows Verified — list view is cached; refresh.

### Create the API key

1. Resend → API Keys → **Create API Key**.
2. Name: `lawtracker-prod` (or `-dev` for staging keys).
3. Permission: **Sending access** (NOT Full access — Sending access
   activates the Domain dropdown so you can scope the key to
   `lawmasolutions.com`. Full access is global and disables
   per-domain scoping; we don't need it.)
4. Domain: `lawmasolutions.com`.
5. Click **Add**.
6. Copy the key (`re_...`) immediately — Resend shows it exactly
   once.

### Set as a Fly secret

```powershell
fly secrets set RESEND_API_KEY=re_paste_your_key_here
```

Fly auto-redeploys with the new secret in the environment. About
1 minute. Verify:

```powershell
fly secrets list
```

You'll see `RESEND_API_KEY` with a digest hash (Fly never reveals
secret values back to you — that's the point).

## Day-to-day operations

### Push a new version

```powershell
# from the project root, with whatever changes you want deployed
fly deploy
```

Fly snapshots the local files (committed or not — Fly doesn't read
git), builds, deploys, runs health checks, swaps traffic.

### See what's running

```powershell
fly status        # machine + region + version
fly logs          # tail logs (Ctrl+C to exit)
fly logs -n       # last N log lines, no tail
```

### Roll back

```powershell
fly releases               # list past deploys
fly releases rollback <id> # revert to a previous one
```

### Add / update / remove a secret

```powershell
fly secrets set NAME=value
fly secrets unset NAME
fly secrets list
```

Each `secrets set` triggers a redeploy.

### Scale up / down

```powershell
fly scale count 2          # run 2 VMs
fly scale memory 512       # bump memory
fly scale show             # current config
```

256MB is plenty for the FastAPI hello-world; bump if the admin app
starts hitting OOM (visible in `fly logs`).

## Troubleshooting

- **`fly version` says command not found after install** — close and
  reopen PowerShell so the new PATH takes effect.
- **Cert stuck at `Configured: false`** — DNS hasn't propagated.
  Wait 5-15 min; recheck with `fly certs check` and `nslookup`. If
  > 30 min, double-check the records were saved at Squarespace and
  the values match `fly ips list` exactly.
- **App returns 502 right after deploy** — health check probably not
  passing. `fly logs` to see what's failing. The /health route
  must return 200 within 5s for Fly's check to pass.
- **Resend domain stuck "Pending" in list view** — list view is
  cached. Detail page is authoritative; F5 the list.
- **DKIM TXT verification fails** — almost always a paste-truncation
  issue. The DKIM value is ~200+ chars; use the copy button, don't
  hand-type.
- **Email won't send despite verified domain + API key in secrets**
  — check `fly logs` for auth errors; common cause is the secret
  was set but the app wasn't redeployed yet (each `fly secrets set`
  triggers a redeploy automatically; if not, force one with
  `fly deploy`).

## What's still to do

This walkthrough gets a hello-world live on lawmasolutions.com with
email infrastructure ready. **Application work** (admin auth,
mockup → Jinja2 templates, the actual draft/publish workflow) is
item 21 territory and lands on top of this skeleton.

Persistent storage (item 4) will need a Fly volume for SQLite —
`fly volumes create lawtracker_data --region iad --size 1` and a
`[mounts]` block in fly.toml. Defer until item 4 starts.
