"""Tests for the Miller & Chevalier FCPA-practice search adapter."""

from pathlib import Path

import httpx

from lawtracker.sources.miller_chevalier import MillerChevalierFcpaAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "miller_chevalier_publications.html"


def _client_serving_fixture() -> httpx.Client:
    body = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_urls_iterate_publications_and_news_only():
    """Per Ellen 2026-04-25: events content type (speaking engagements)
    is dropped — only substantive publications and news flow through."""
    urls = MillerChevalierFcpaAdapter().urls
    assert len(urls) == 2
    assert any("content_types%5B0%5D=publication" in u for u in urls)
    assert any("content_types%5B0%5D=news" in u for u in urls)
    assert not any("content_types%5B0%5D=event" in u for u in urls)


def test_parses_search_results_and_tags_content_type():
    """The fixture is the publications page; every result link is /publication/.
    `content_type` metadata field should reflect that on every record."""
    with _client_serving_fixture() as client:
        result = MillerChevalierFcpaAdapter().poll(client=client)

    assert result.status == "ok"
    # urls iterates 2 times (publications, news); mock returns the
    # publications fixture for both, so we expect 2 × 20 = 40 records.
    assert len(result.events) == 40

    for event in result.events:
        assert event.source_id == "miller_chevalier_fcpa"
        assert event.country == "US"
        assert event.url.startswith("https://www.millerchevalier.com/")
        assert event.dedup_key == event.url
        assert event.metadata.get("content_type") == "publication"


def test_extracts_dates_and_known_publication():
    with _client_serving_fixture() as client:
        result = MillerChevalierFcpaAdapter().poll(client=client)

    titles = [e.title for e in result.events]
    assert any("FCPA" in t for t in titles), (
        f"expected at least one FCPA Review in results; got {titles[:5]}"
    )

    dated = [e for e in result.events if e.event_date is not None]
    assert dated, "expected at least one result with a parseable datetime"
