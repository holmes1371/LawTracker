"""Tests for the DOJ FCPA actions adapter.

The fixture is a snapshot of the live 2026 chronological page captured
during development; refresh when DOJ restructures the page or at year
rollover.

A `_SingleYearAdapter` overrides the production years tuple to a single
year so that mocked HTTP fetches don't multiply event counts (the production
adapter polls multiple years to give the scout 12-24 months of trend depth).
The mock transport serves the same fixture for every URL it sees, including
case-detail and press-release URLs that the link-following enrichment
attempts to reach — those return harmless data and the enrichment fails
soft, leaving the basic record intact.
"""

from datetime import date
from pathlib import Path

import httpx

from lawtracker.sources.doj_fcpa_actions import DojFcpaActionsAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "doj_fcpa_actions.html"


class _SingleYearAdapter(DojFcpaActionsAdapter):
    """Restricts the year iteration so the fixture isn't fetched twice."""

    years = (2026,)


def _client_serving_fixture() -> httpx.Client:
    body = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_known_case_from_fixture():
    adapter = _SingleYearAdapter()
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
    adapter = _SingleYearAdapter()
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
    adapter = _SingleYearAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="<html><body>nothing here</body></html>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = adapter.poll(client=client)

    assert result.status == "ok"
    assert result.events == []


def test_urls_property_iterates_year_tuple():
    adapter = DojFcpaActionsAdapter()
    urls = adapter.urls
    assert len(urls) == len(DojFcpaActionsAdapter.years)
    for year in DojFcpaActionsAdapter.years:
        assert any(str(year) in u for u in urls)


def test_press_release_enrichment_extracts_topic_and_amount():
    """Mock the enrichment chain end-to-end: case-detail page links to a
    press release, the press release exposes topic + body containing
    industry, resolution, and a dollar amount."""
    year_html = FIXTURE.read_text(encoding="utf-8")
    case_detail_html = (
        '<html><body>'
        '<a href="/opa/pr/example-press-release">Press Release</a>'
        '</body></html>'
    )
    press_release_html = """
    <html><body>
      <span class="field-formatter--string">DOJ resolves foreign bribery probe</span>
      <div class="node-topics"><div class="field__items">
        <div class="field__item">Financial Fraud</div>
        <div class="field__item">Foreign Corruption</div>
      </div></div>
      <div class="node-component"><div class="field__items">
        <div class="field__item">Criminal Division</div>
      </div></div>
      <div class="field_body">
        <p>The medical device company agreed to pay $1.2 million in disgorgement.
        The Department declined to prosecute the company under the
        Corporate Enforcement Policy.</p>
      </div>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/case/related-enforcement-actions/" in path:
            return httpx.Response(200, text=year_html)
        if "/opa/pr/" in path:
            return httpx.Response(200, text=press_release_html)
        if path.startswith("/criminal/fraud/fcpa/cases/"):
            return httpx.Response(200, text=case_detail_html)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _SingleYearAdapter().poll(client=client)

    assert result.status == "ok"
    assert result.events
    event = result.events[0]
    assert event.metadata.get("topic") == "Financial Fraud, Foreign Corruption"
    assert event.metadata.get("component") == "Criminal Division"
    assert event.metadata.get("industry") == "medical devices"
    assert event.metadata.get("resolution_type") == "declination"
    assert event.metadata.get("amount_usd") == 1_200_000
    assert event.metadata.get("press_release_url", "").endswith("example-press-release")
