"""Tests for the generic RssFeedAdapter — exercised against Volkov Law's
WordPress RSS 2.0 fixture."""

import re
from pathlib import Path

import httpx

from lawtracker.sources.rss_feed import RssFeedAdapter
from lawtracker.sources.volkov_law import VolkovLawAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "volkov_law.xml"


def _client_serving_fixture() -> httpx.Client:
    body = FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_volkov_subclass_just_declares_url():
    """The reuse contract: a working RSS source = 4 lines of subclass."""
    assert VolkovLawAdapter.source_id == "volkov_law"
    assert VolkovLawAdapter.kind == "event_list"
    assert VolkovLawAdapter.url.endswith("/feed/")
    assert VolkovLawAdapter.country == "US"


def test_parses_rss_items_into_event_records():
    with _client_serving_fixture() as client:
        result = VolkovLawAdapter().poll(client=client)

    assert result.status == "ok"
    assert result.events, "Volkov RSS fixture should have items"

    for event in result.events:
        assert event.source_id == "volkov_law"
        assert event.country == "US"
        assert event.url.startswith("https://blog.volkovlaw.com/")
        assert event.dedup_key == event.url
        assert event.title


def test_extracts_pub_date_author_categories():
    with _client_serving_fixture() as client:
        result = VolkovLawAdapter().poll(client=client)

    dated = [e for e in result.events if e.event_date is not None]
    assert dated, "expected at least one item with a parseable pubDate"

    creators = [e for e in result.events if e.primary_actor]
    assert creators, "expected at least one item with a dc:creator author"

    cats = [e for e in result.events if e.metadata.get("categories")]
    assert cats, "expected at least one item with categories"


def test_summary_strips_html_from_description():
    with _client_serving_fixture() as client:
        result = VolkovLawAdapter().poll(client=client)

    summarized = [e for e in result.events if e.summary]
    assert summarized
    for event in summarized:
        # No raw <p> / <a> / <strong> markup should leak through.
        assert "<" not in event.summary
        assert ">" not in event.summary


def test_keyword_filter_restricts_emitted_records():
    """Subclasses can constrain what comes through with a regex filter."""

    class _FilteredAdapter(VolkovLawAdapter):
        source_id = "volkov_filtered"
        keyword_filter = re.compile(r"\bAI\b", re.IGNORECASE)

    with _client_serving_fixture() as client:
        result = _FilteredAdapter().poll(client=client)

    assert result.status == "ok"
    for event in result.events:
        haystack = (event.title + " " + (event.summary or "")).lower()
        assert "ai" in haystack


def test_atom_feed_also_parses():
    """Light Atom-format feed, asserts the secondary path works."""
    atom = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Sample Atom Feed</title>
      <entry>
        <title>An Atom Entry</title>
        <link href="https://example.test/atom-entry"/>
        <published>2026-01-15T10:00:00Z</published>
        <summary>Atom summary text</summary>
        <author><name>Atom Author</name></author>
      </entry>
    </feed>"""

    class _AtomAdapter(RssFeedAdapter):
        source_id = "atom_test"
        kind = "event_list"
        url = "https://example.test/atom"
        country = "US"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=atom)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _AtomAdapter().poll(client=client)

    assert result.status == "ok"
    assert len(result.events) == 1
    event = result.events[0]
    assert event.title == "An Atom Entry"
    assert event.url == "https://example.test/atom-entry"
    assert event.primary_actor == "Atom Author"
    assert event.country == "US"
