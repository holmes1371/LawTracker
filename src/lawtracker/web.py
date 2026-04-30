"""Minimal FastAPI app — the deployment skeleton.

Phase 4 hello-world to validate the deploy chain (FastAPI → Docker →
Fly.io → DNS → HTTPS) before wiring item 21's actual admin / public
features. Real routes (admin auth, magic-link, draft/publish, mockup
→ Jinja2 templates) land on top of this in subsequent commits.

Run locally:
    py -m uvicorn lawtracker.web:app --reload

Run in container (production):
    uvicorn lawtracker.web:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from lawtracker import __version__

app = FastAPI(
    title="LawTracker",
    description="Anti-corruption enforcement tracker.",
    version=__version__,
)


COMING_SOON_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LawTracker — coming soon</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="LawTracker — anti-corruption enforcement and compliance, watched and summarized.">
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900 antialiased min-h-screen flex items-center justify-center px-6">
  <main class="max-w-xl text-center">
    <div class="text-xs uppercase tracking-widest text-slate-400 mb-6">lawmasolutions.com</div>
    <h1 class="text-5xl sm:text-6xl font-bold tracking-tight text-slate-900 mb-5">LawTracker</h1>
    <p class="text-lg text-slate-600 mb-10 leading-relaxed">
      Anti-corruption enforcement and compliance,<br class="hidden sm:block"> watched and summarized.
    </p>
    <p class="text-sm font-medium text-slate-500 uppercase tracking-wider">Coming soon</p>
  </main>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Public landing — Coming Soon placeholder. Replaced by the
    public Analysis page when item 21 wires the Jinja2 templates."""
    return COMING_SOON_HTML


@app.get("/health")
def health() -> dict[str, str]:
    """Health endpoint for Fly's load balancer + uptime checks.
    Stays JSON — load balancers don't read HTML."""
    return {"status": "ok"}
