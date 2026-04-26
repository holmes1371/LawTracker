"""Tests for the per-event article summary enrichment."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lawtracker.article_summary import enrich_summaries, summary_cache_key
from lawtracker.llm_cache import JsonCache
from lawtracker.sources import EventRecord


def _event(
    *,
    dedup_key: str = "k",
    title: str = "DOJ resolves bribery case with Acme",
    summary: str | None = None,
    country: str | None = "US",
    source_id: str = "doj_fcpa_actions",
    event_date: date | None = None,
) -> EventRecord:
    return EventRecord(
        dedup_key=dedup_key,
        source_id=source_id,
        event_date=event_date,
        title=title,
        primary_actor=None,
        summary=summary,
        url=f"https://example.test/{dedup_key}",
        country=country,
        metadata={},
    )


def test_stub_mode_generates_placeholder_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
    cache = JsonCache(tmp_path / "summaries.json")
    enriched = enrich_summaries([_event()], cache=cache)
    assert enriched[0].summary is not None
    assert enriched[0].summary.startswith("[STUB summary]")
    assert "doj_fcpa_actions" in enriched[0].summary


def test_stub_mode_caches_summary_to_disk(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
    cache = JsonCache(tmp_path / "summaries.json")
    enrich_summaries([_event(dedup_key="abc")], cache=cache)

    cache2 = JsonCache(tmp_path / "summaries.json")
    cached = cache2.get("stub|abc")
    assert isinstance(cached, dict)
    assert cached["mode"] == "stub"
    assert cached["summary"].startswith("[STUB summary]")


def test_cache_hit_skips_regeneration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
    cache = JsonCache(tmp_path / "summaries.json")
    cache.put(
        "stub|abc",
        {"summary": "Pre-existing cached summary.", "mode": "stub"},
    )

    enriched = enrich_summaries([_event(dedup_key="abc")], cache=cache)
    assert enriched[0].summary == "Pre-existing cached summary."
    # Cache should not have been re-written with a new placeholder
    assert cache.get("stub|abc")["summary"] == "Pre-existing cached summary."


def test_off_mode_leaves_summaries_untouched(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "off")
    cache = JsonCache(tmp_path / "summaries.json")
    enriched = enrich_summaries(
        [_event(summary="adapter-provided summary")], cache=cache
    )
    assert enriched[0].summary == "adapter-provided summary"
    assert len(cache) == 0


def test_anthropic_mode_uses_fetched_article(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")

    captured: dict[str, str] = {}

    def fake_fetch(url: str) -> str:
        captured["url"] = url
        return "Long article body about Acme Corp's FCPA resolution."

    def fake_anthropic(system: str, user: str, max_tokens: int, model: str) -> str:
        captured["user"] = user
        return (
            '{"drop": false, "summary": '
            '"Acme Corp settled FCPA charges with $30M disgorgement."}'
        )

    monkeypatch.setattr("lawtracker.llm._complete_anthropic", fake_anthropic)

    cache = JsonCache(tmp_path / "summaries.json")
    enriched = enrich_summaries(
        [_event(dedup_key="acme")],
        cache=cache,
        fetch_article_text=fake_fetch,
    )

    assert captured["url"] == "https://example.test/acme"
    assert "Long article body" in captured["user"]
    assert enriched[0].summary == "Acme Corp settled FCPA charges with $30M disgorgement."
    cached = cache.get("anthropic|acme")
    assert cached["mode"] == "anthropic"
    assert cached["drop"] is False


def test_anthropic_drop_decision_drops_event_and_caches_reason(
    tmp_path: Path, monkeypatch
) -> None:
    """Tom 2026-04-25: regex filter still misses event-noise. The LLM has
    full article context; let it decide. drop=true → event dropped."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")

    def fake_anthropic(system: str, user: str, max_tokens: int, model: str) -> str:
        return '{"drop": true, "reason": "podcast episode"}'

    monkeypatch.setattr("lawtracker.llm._complete_anthropic", fake_anthropic)

    cache = JsonCache(tmp_path / "summaries.json")
    enriched = enrich_summaries(
        [_event(dedup_key="podcast1", title="EMBARGOED!: South of the Border")],
        cache=cache,
        fetch_article_text=lambda url: "Welcome to this episode of EMBARGOED!...",
    )

    assert enriched == [], "drop=true must remove the event from the result list"
    cached = cache.get("anthropic|podcast1")
    assert cached["drop"] is True
    assert cached["reason"] == "podcast episode"


def test_drop_decision_cached_so_repeat_runs_skip_llm(tmp_path: Path, monkeypatch) -> None:
    """Cached drop decisions should drop the event without calling the LLM
    again — preserves the article-skip guarantee Tom asked for."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")
    cache = JsonCache(tmp_path / "summaries.json")
    cache.put(
        "anthropic|x",
        {"drop": True, "reason": "webinar promo", "mode": "anthropic"},
    )

    fetch_called = [0]

    def fetch_should_not_run(url: str) -> str:
        fetch_called[0] += 1
        return "body"

    def llm_should_not_run(system, user, max_tokens, model):
        raise AssertionError("LLM must not be called when cache is a drop")

    monkeypatch.setattr("lawtracker.llm._complete_anthropic", llm_should_not_run)

    enriched = enrich_summaries(
        [_event(dedup_key="x")],
        cache=cache,
        fetch_article_text=fetch_should_not_run,
    )

    assert enriched == []
    assert fetch_called[0] == 0


def test_old_cache_format_without_drop_field_still_works(
    tmp_path: Path, monkeypatch
) -> None:
    """Cache entries from before the drop-decision change look like
    `{summary, mode, generated_at, url}` with no `drop` field. They must
    continue to satisfy lookups as drop=false."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
    cache = JsonCache(tmp_path / "summaries.json")
    cache.put(
        "stub|legacy",
        {"summary": "Legacy summary text.", "mode": "stub"},  # no `drop`
    )

    enriched = enrich_summaries([_event(dedup_key="legacy")], cache=cache)
    assert len(enriched) == 1
    assert enriched[0].summary == "Legacy summary text."


def test_malformed_llm_response_falls_back_to_using_text_as_summary(
    tmp_path: Path, monkeypatch
) -> None:
    """If the LLM returns prose instead of JSON, salvage the text as a
    summary rather than losing the work entirely."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")

    def fake_anthropic(system, user, max_tokens, model):
        return "Acme Corp resolved the matter for $5M. (Forgot the JSON wrapper.)"

    monkeypatch.setattr("lawtracker.llm._complete_anthropic", fake_anthropic)
    cache = JsonCache(tmp_path / "summaries.json")
    enriched = enrich_summaries(
        [_event(dedup_key="m1")],
        cache=cache,
        fetch_article_text=lambda url: "body",
    )
    assert "Acme Corp resolved" in (enriched[0].summary or "")


def test_anthropic_mode_failed_fetch_leaves_summary_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")
    cache = JsonCache(tmp_path / "summaries.json")
    enriched = enrich_summaries(
        [_event(summary="adapter summary")],
        cache=cache,
        fetch_article_text=lambda url: None,  # simulate fetch failure
    )
    assert enriched[0].summary == "adapter summary"
    assert len(cache) == 0


def test_summary_source_preserved_in_metadata(tmp_path: Path, monkeypatch) -> None:
    """When the LLM replaces an existing summary, stash the original."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
    cache = JsonCache(tmp_path / "summaries.json")
    e = _event(summary="Adapter-provided summary from RSS.")
    enriched = enrich_summaries([e], cache=cache)
    assert enriched[0].metadata.get("summary_source") == "Adapter-provided summary from RSS."
    assert enriched[0].summary != "Adapter-provided summary from RSS."


def test_cache_key_is_mode_stamped(monkeypatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")
    assert summary_cache_key(_event(dedup_key="x")) == "stub|x"
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")
    assert summary_cache_key(_event(dedup_key="x")) == "anthropic|x"


def test_mode_change_invalidates_cache_hit(tmp_path: Path, monkeypatch) -> None:
    """Cache entries from one mode shouldn't satisfy lookups in another."""
    monkeypatch.setattr(
        "lawtracker.llm._complete_anthropic",
        lambda system, user, max_tokens, model: "fresh anthropic summary",
    )
    cache = JsonCache(tmp_path / "summaries.json")
    cache.put("stub|x", {"summary": "stub one", "mode": "stub"})

    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "anthropic")
    enriched = enrich_summaries(
        [_event(dedup_key="x")],
        cache=cache,
        fetch_article_text=lambda url: "body text",
    )
    # Should not see "stub one"; the anthropic cache slot is fresh.
    assert enriched[0].summary == "fresh anthropic summary"
    assert cache.get("anthropic|x") is not None
