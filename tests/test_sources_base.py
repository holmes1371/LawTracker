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
