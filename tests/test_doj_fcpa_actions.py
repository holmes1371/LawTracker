"""Tests for the DOJ FCPA actions adapter.

The fixture is a snapshot of the live current-year page captured during
development; refresh when DOJ restructures the page or at year rollover.
"""

from datetime import date
from pathlib import Path

import httpx

from lawtracker.sources.doj_fcpa_actions import DojFcpaActionsAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "doj_fcpa_actions.html"


def _client_serving_fixture() -> httpx.Client:
    body = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_known_case_from_fixture():
    adapter = DojFcpaActionsAdapter()
    with _client_serving_fixture() as client:
        result = adapter.poll(client=client)

    assert result.status == "ok"
    assert result.events, "expected at least one case from the 2026 fixture"

    ferrera = next(
        (e for e in result.events if "Ferrera" in e.title),
        None,
    )
    assert ferrera is not None, "fixture is expected to contain U.S. v. Ferrera"
    assert ferrera.source_id == "doj_fcpa_actions"
    assert ferrera.country == "US"
    assert ferrera.title.startswith("United States v.")
    assert ferrera.primary_actor and ferrera.primary_actor.startswith("David Ferrera")
    assert ferrera.event_date == date(2026, 3, 4)
    assert ferrera.url.startswith("https://www.justice.gov/")
    assert ferrera.dedup_key == ferrera.url
    assert ferrera.metadata.get("case_number") == "8:26-cr-00030-DOC"
    assert ferrera.metadata.get("district") == "Central District of California"


def test_dedup_keys_are_unique_and_stable_on_reparse():
    adapter = DojFcpaActionsAdapter()
    with _client_serving_fixture() as client:
        first = adapter.poll(client=client)
    with _client_serving_fixture() as client:
        second = adapter.poll(client=client)

    keys = [e.dedup_key for e in first.events]
    assert len(keys) == len(set(keys)), "dedup keys must be unique within a poll"
    assert keys == [e.dedup_key for e in second.events], (
        "re-parsing the same fixture must produce identical dedup keys"
    )


def test_returns_empty_events_on_unrelated_html():
    adapter = DojFcpaActionsAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="<html><body>nothing here</body></html>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = adapter.poll(client=client)

    assert result.status == "ok"
    assert result.events == []
