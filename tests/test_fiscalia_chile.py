"""Tests for the Fiscalía Chile adapter.

Fixture is a saved snapshot of the nacionales news page page=5 — chosen
for dev because it contains items that pass the anti-corruption keyword
filter; the live current page often returns zero matches, which is itself
the expected behavior for sparse signal.
"""

from pathlib import Path

import httpx

from lawtracker.sources.fiscalia_chile import FiscaliaChileAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "fiscalia_chile.html"


def _client_serving_fixture() -> httpx.Client:
    body = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_keyword_filter_emits_only_anticorruption_items():
    with _client_serving_fixture() as client:
        result = FiscaliaChileAdapter().poll(client=client)

    assert result.status == "ok"
    assert result.events, "fixture should contain at least one filter-passing item"

    pattern_words = (
        "cohecho",
        "corrupc",
        "soborn",
        "lavado",
        "fraude",
        "delitos econ",
        "20.393",
        "20,393",
        "funcionario p",
    )
    for event in result.events:
        haystack = (event.title + " " + (event.summary or "")).lower()
        assert any(w in haystack for w in pattern_words), (
            f"event passed filter without keyword: {event.title}"
        )


def test_country_and_source_id_set():
    with _client_serving_fixture() as client:
        result = FiscaliaChileAdapter().poll(client=client)

    for event in result.events:
        assert event.country == "CL"
        assert event.source_id == "fiscalia_chile"
        assert event.url.startswith("https://www.fiscaliadechile.cl/")
        assert event.dedup_key == event.url


def test_dates_parsed_from_dd_mm_yyyy():
    with _client_serving_fixture() as client:
        result = FiscaliaChileAdapter().poll(client=client)

    dated = [e for e in result.events if e.event_date is not None]
    assert dated, "expected at least one event with a parseable date"
    for event in dated:
        assert 2010 <= event.event_date.year <= 2030


def test_empty_html_returns_empty_events():
    adapter = FiscaliaChileAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="<html><body></body></html>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = adapter.poll(client=client)

    assert result.status == "ok"
    assert result.events == []
