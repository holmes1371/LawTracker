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

from lawtracker import __version__

app = FastAPI(
    title="LawTracker",
    description="Anti-corruption enforcement tracker.",
    version=__version__,
)


@app.get("/")
def index() -> dict[str, str]:
    """Root — hello-world placeholder. Replaced by the public Analysis
    page when item 21 wires the Jinja2 templates."""
    return {
        "status": "ok",
        "message": "LawTracker — coming soon at lawmasolutions.com",
        "version": __version__,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Health endpoint for Fly's load balancer + uptime checks."""
    return {"status": "ok"}
