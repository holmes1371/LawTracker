"""Tests for law-firm and academic blog adapters.

Each is a thin RssFeedAdapter subclass; the heavy lifting is covered by
test_rss_feed.py. These tests verify the right configuration (URL,
country, keyword filter) and that the live fixture parses cleanly.
"""

from pathlib import Path

import httpx

from lawtracker.sources._filters import ANTI_CORRUPTION_EN
from lawtracker.sources.foley_llp import FoleyLlpAdapter
from lawtracker.sources.gibson_dunn import GibsonDunnAdapter
from lawtracker.sources.global_anticorruption_blog import GlobalAnticorruptionBlogAdapter
from lawtracker.sources.harvard_corpgov_fcpa import HarvardCorpGovFcpaAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def _client_for(fixture_name: str) -> httpx.Client:
    body = (FIXTURES / fixture_name).read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gibson_dunn_uses_anti_corruption_filter():
    """Mixed-topic firm feed must drop non-FCPA items via the keyword filter."""
    assert GibsonDunnAdapter.keyword_filter is ANTI_CORRUPTION_EN
    assert GibsonDunnAdapter.country == "US"
    assert GibsonDunnAdapter.url.endswith("/feed/")

    with _client_for("gibson_dunn.xml") as client:
        result = GibsonDunnAdapter().poll(client=client)

    assert result.status == "ok"
    # Filter should drop a lot — the feed has a class-action update, a
    # joint-employer rule, an ad announcement, etc., but should keep the
    # "EU Adopts Anti-Corruption Directive" item.
    titles = [e.title for e in result.events]
    assert any("Anti-Corruption" in t or "FCPA" in t for t in titles), (
        f"expected at least one anti-corruption item; got: {titles}"
    )
    # And should drop the joint-employer one.
    assert not any("Joint-Employer" in t for t in titles)


def test_foley_llp_uses_anti_corruption_filter_and_curl_cffi():
    assert FoleyLlpAdapter.keyword_filter is ANTI_CORRUPTION_EN
    assert FoleyLlpAdapter.use_curl_cffi is True
    assert FoleyLlpAdapter.country == "US"

    with _client_for("foley_llp.xml") as client:
        result = FoleyLlpAdapter().poll(client=client)
    assert result.status == "ok"
    # Filter trims a large mixed-topic feed; expect at least one anti-corruption hit.
    for event in result.events:
        haystack = (event.title + " " + (event.summary or "")).lower()
        keywords = (
            "fcpa",
            "fepa",
            "bribery",
            "bribe",
            "anti-corruption",
            "kleptocracy",
            "foreign official",
            "public official",
            "cartel",
        )
        assert any(kw in haystack for kw in keywords), (
            f"event passed filter without anti-corruption keyword: {event.title}"
        )


def test_harvard_corpgov_fcpa_no_filter_curl_cffi():
    assert HarvardCorpGovFcpaAdapter.keyword_filter is None
    assert HarvardCorpGovFcpaAdapter.use_curl_cffi is True
    assert "foreign-corrupt-practices-act" in HarvardCorpGovFcpaAdapter.url

    with _client_for("harvard_corpgov_fcpa.xml") as client:
        result = HarvardCorpGovFcpaAdapter().poll(client=client)
    assert result.status == "ok"
    for event in result.events:
        assert event.source_id == "harvard_corpgov_fcpa"


def test_global_anticorruption_blog_no_filter_all_on_topic():
    assert GlobalAnticorruptionBlogAdapter.keyword_filter is None
    assert GlobalAnticorruptionBlogAdapter.country == "US"

    with _client_for("global_anticorruption_blog.xml") as client:
        result = GlobalAnticorruptionBlogAdapter().poll(client=client)

    assert result.status == "ok"
    assert result.events
    for event in result.events:
        assert event.source_id == "global_anticorruption_blog"
        assert event.url.startswith("https://globalanticorruptionblog.com/")
