"""Tests for the SourceAdapter base contract.

Cover the four `PollResult` paths through `poll()`: ok, transient_failure
(transport error, 5xx), and permanent_failure (4xx, parse error).
"""

from collections.abc import Callable

import httpx

from lawtracker.sources import EventRecord, SourceAdapter

Handler = Callable[[httpx.Request], httpx.Response]


class _FakeAdapter(SourceAdapter):
    source_id = "fake"
    kind = "event_list"
    url = "https://example.test/list"

    def parse(self, html: str, client: httpx.Client) -> list[EventRecord]:
        if html == "boom":
            raise ValueError("intentional parse failure")
        return [
            EventRecord(
                dedup_key="https://example.test/case/1",
                source_id="fake",
                event_date=None,
                title="Test case",
                primary_actor=None,
                summary=None,
                url="https://example.test/case/1",
                country="US",
            )
        ]


def _client(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _respond(status: int, body: str = "") -> Handler:
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status, text=body)

    return h


def _raise(exc: Exception) -> Handler:
    def h(request: httpx.Request) -> httpx.Response:
        raise exc

    return h


def test_ok_status_with_events():
    with _client(_respond(200, "<html>ok</html>")) as client:
        result = _FakeAdapter().poll(client=client)
    assert result.status == "ok"
    assert result.error is None
    assert len(result.events) == 1
    event = result.events[0]
    assert event.dedup_key == "https://example.test/case/1"
    assert event.source_id == "fake"
    assert event.country == "US"


def test_5xx_is_transient_failure():
    with _client(_respond(503)) as client:
        result = _FakeAdapter().poll(client=client)
    assert result.status == "transient_failure"
    assert result.events == []
    assert "503" in result.error


def test_4xx_is_permanent_failure():
    with _client(_respond(404)) as client:
        result = _FakeAdapter().poll(client=client)
    assert result.status == "permanent_failure"
    assert result.events == []
    assert "404" in result.error


def test_transport_error_is_transient_failure():
    with _client(_raise(httpx.ConnectError("network down"))) as client:
        result = _FakeAdapter().poll(client=client)
    assert result.status == "transient_failure"
    assert "request error" in result.error


def test_parse_error_is_permanent_failure():
    with _client(_respond(200, "boom")) as client:
        result = _FakeAdapter().poll(client=client)
    assert result.status == "permanent_failure"
    assert "parse error" in result.error
    assert "ValueError" in result.error


class _SpanishAdapter(SourceAdapter):
    """Fake adapter that opts into ES → EN translation."""

    source_id = "fake_es"
    kind = "event_list"
    url = "https://example.test/es"
    translate_summary_from = "es"

    def parse(self, html: str, client) -> list[EventRecord]:
        return [
            EventRecord(
                dedup_key="https://example.test/case/1",
                source_id="fake_es",
                event_date=None,
                title="Título original",
                primary_actor=None,
                summary="Resumen original",
                url="https://example.test/case/1",
                country="CL",
            )
        ]


class _NoisyAdapter(SourceAdapter):
    """Returns a mix of substantive + event-noise items."""

    source_id = "fake_noisy"
    kind = "event_list"
    url = "https://example.test/noisy"

    def parse(self, html: str, client) -> list[EventRecord]:
        return [
            EventRecord(
                dedup_key="ev-1",
                source_id="fake_noisy",
                event_date=None,
                title="DOJ resolves foreign bribery case with Acme Corp",
                primary_actor="Acme Corp",
                summary="Substantive enforcement news.",
                url="https://example.test/case-1",
                country="US",
            ),
            EventRecord(
                dedup_key="ev-2",
                source_id="fake_noisy",
                event_date=None,
                title="Webinar: 2026 FCPA Trends — Register Now",
                primary_actor=None,
                summary="Join us for a 60-minute webinar.",
                url="https://example.test/webinar",
                country="US",
            ),
            EventRecord(
                dedup_key="ev-3",
                source_id="fake_noisy",
                event_date=None,
                title="Podcast Episode 42: The CEP One Year Later",
                primary_actor=None,
                summary=None,
                url="https://example.test/podcast",
                country="US",
            ),
            EventRecord(
                dedup_key="ev-4",
                source_id="fake_noisy",
                event_date=None,
                title="Speaking Engagement: ABA FCPA Forum",
                primary_actor=None,
                summary=None,
                url="https://example.test/forum",
                country="US",
            ),
            EventRecord(
                dedup_key="ev-5",
                source_id="fake_noisy",
                event_date=None,
                title="Networking Reception at the Stanford FCPA Conference",
                primary_actor=None,
                summary=None,
                url="https://example.test/networking",
                country="US",
            ),
        ]


def test_event_noise_filter_drops_conference_webinar_podcast_networking():
    """Ellen 2026-04-25: ads for conferences / webinars / podcasts /
    networking events should be dropped before reaching translation, the
    LLM, or the final table."""
    with _client(_respond(200, "<html>ok</html>")) as client:
        result = _NoisyAdapter().poll(client=client)

    assert result.status == "ok"
    titles = [e.title for e in result.events]
    assert any("Acme Corp" in t for t in titles), "substantive item must survive"
    assert not any("Webinar" in t for t in titles)
    assert not any("Podcast" in t for t in titles)
    assert not any("Speaking Engagement" in t for t in titles)
    assert not any("Networking" in t for t in titles)


class _ConferenceyAdapter(SourceAdapter):
    """Tom 2026-04-25: filter must apply to ALL adapters, not just M&C.
    Tests the title-prefix and `summit` / `annual forum` patterns."""

    source_id = "fake_confy"
    kind = "event_list"
    url = "https://example.test/confy"

    def parse(self, html: str, client) -> list[EventRecord]:
        items = [
            "Acme Corp pleads guilty in $50M FCPA scheme",  # keep
            "Conference: 2026 Anti-Corruption Forum",  # drop (prefix)
            "Forum: Compliance Trends in LATAM",  # drop (prefix)
            "Annual FCPA Summit — Save the Date",  # drop
            "Join us for our Quarterly FCPA Roundtable",  # drop
            "RSVP: Spring Compliance Conference",  # drop
            "Tickets available for the ABA Symposium",  # drop
            "DAG Lisa Monaco delivers keynote at ABA Conference",  # keep — substantive content
        ]
        return [
            EventRecord(
                dedup_key=f"k{i}",
                source_id="fake_confy",
                event_date=None,
                title=t,
                primary_actor=None,
                summary=None,
                url=f"https://example.test/{i}",
                country="US",
            )
            for i, t in enumerate(items)
        ]


def test_event_noise_filter_applies_to_every_adapter_not_just_m_and_c():
    """Tom 2026-04-25: drop-event-content guidance is universal."""
    with _client(_respond(200, "<html>ok</html>")) as client:
        result = _ConferenceyAdapter().poll(client=client)

    titles = [e.title for e in result.events]
    assert any("Acme Corp" in t for t in titles)
    assert any("Lisa Monaco" in t for t in titles), (
        "speeches AT conferences must survive — they're substantive"
    )
    assert not any(t.startswith("Conference:") for t in titles)
    assert not any(t.startswith("Forum:") for t in titles)
    assert not any("Summit" in t for t in titles)
    assert not any("Roundtable" in t for t in titles)
    assert not any(t.startswith("RSVP:") for t in titles)
    assert not any("Tickets available" in t for t in titles)


def test_translate_summary_from_swaps_title_and_summary(monkeypatch):
    translations = {
        "Título original": "Original title",
        "Resumen original": "Original summary",
    }
    monkeypatch.setattr(
        "lawtracker.translate.translate",
        lambda text, **kwargs: translations.get(text, text),
    )

    with _client(_respond(200, "<html>ok</html>")) as client:
        result = _SpanishAdapter().poll(client=client)

    assert result.status == "ok"
    event = result.events[0]
    assert event.title == "Original title"
    assert event.summary == "Original summary"
    assert event.metadata["title_es"] == "Título original"
    assert event.metadata["summary_es"] == "Resumen original"
