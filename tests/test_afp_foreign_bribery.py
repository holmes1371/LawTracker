"""Tests for the AFP foreign-bribery adapter."""

from pathlib import Path

import httpx

from lawtracker.sources.afp_foreign_bribery import AfpForeignBriberyAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "afp_foreign_bribery.html"


def _client_serving_fixture() -> httpx.Client:
    body = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_news_centre_results_only():
    with _client_serving_fixture() as client:
        result = AfpForeignBriberyAdapter().poll(client=client)

    assert result.status == "ok"
    assert result.events, "fixture should contain media-release results"

    for event in result.events:
        assert event.source_id == "afp_foreign_bribery"
        assert event.country == "AU"
        assert "/news-centre/" in event.url, "static crime-type pages must be filtered out"
        assert event.url.startswith("https://www.afp.gov.au/")
        assert event.dedup_key == event.url


def test_extracts_dates_and_categories():
    with _client_serving_fixture() as client:
        result = AfpForeignBriberyAdapter().poll(client=client)

    dated = [e for e in result.events if e.event_date is not None]
    assert dated, "expected at least one event with a parseable date"

    categorized = [e for e in result.events if e.metadata.get("category")]
    assert categorized, "expected at least one event with a category"


def test_dedup_keys_unique_within_poll():
    with _client_serving_fixture() as client:
        result = AfpForeignBriberyAdapter().poll(client=client)

    keys = [e.dedup_key for e in result.events]
    assert len(keys) == len(set(keys))
