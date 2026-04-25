"""Tests for the post-scout analysis writer."""

from __future__ import annotations

from datetime import date

from lawtracker.analysis import build_analysis
from lawtracker.sources import EventRecord


def _event(
    *,
    source_id: str = "s1",
    title: str = "t",
    country: str | None = "US",
    event_date: date | None = None,
    industry: str | None = None,
    primary_actor: str | None = None,
) -> EventRecord:
    metadata: dict[str, str] = {}
    if industry:
        metadata["industry"] = industry
    return EventRecord(
        dedup_key=f"{source_id}-{title}",
        source_id=source_id,
        event_date=event_date,
        title=title,
        primary_actor=primary_actor,
        summary=None,
        url=f"https://example.test/{title}",
        country=country,
        metadata=metadata,
    )


def test_analysis_includes_deterministic_source_counts() -> None:
    events = [
        _event(source_id="doj_fcpa_actions", title="case1"),
        _event(source_id="doj_fcpa_actions", title="case2"),
        _event(source_id="afp_foreign_bribery", title="aupub", country="AU"),
    ]
    out = build_analysis(events)
    assert "## Source counts" in out
    assert "`doj_fcpa_actions`: 2" in out
    assert "`afp_foreign_bribery`: 1" in out
    assert "## Country counts" in out
    assert "US: 2" in out
    assert "AU: 1" in out


def test_analysis_includes_industry_section_when_present() -> None:
    events = [
        _event(industry="medical devices"),
        _event(industry="medical devices"),
        _event(industry="aerospace"),
    ]
    out = build_analysis(events)
    assert "## Industry counts" in out
    assert "medical devices: 2" in out
    assert "aerospace: 1" in out


def test_analysis_omits_industry_section_when_no_industry_metadata() -> None:
    events = [_event(), _event()]
    out = build_analysis(events)
    assert "## Industry counts" not in out


def test_analysis_in_stub_mode_includes_stub_marker() -> None:
    events = [_event()]
    out = build_analysis(events)
    assert "[STUB LLM RESPONSE]" in out


def test_analysis_includes_prompt_for_design_iteration() -> None:
    events = [_event()]
    out = build_analysis(events)
    # The prompt-design preview is wrapped in <details> for collapsibility
    # in markdown viewers; the system instruction header should land inside.
    assert "Prompt sent to LLM" in out
    assert "FCPA / global anti-corruption analyst" in out


def test_analysis_drops_translation_originals_from_prompt() -> None:
    """metadata.title_es / summary_es are reference-only — they shouldn't
    bloat the LLM context. Verify they're omitted from the embedded JSON."""
    e = EventRecord(
        dedup_key="a",
        source_id="s",
        event_date=None,
        title="English title",
        primary_actor=None,
        summary="English summary",
        url="https://example.test/a",
        country="CL",
        metadata={
            "title_es": "Título original",
            "summary_es": "Resumen original",
            "region": "Nacional",
        },
    )
    out = build_analysis([e])
    assert "Título original" not in out
    assert "Resumen original" not in out
    assert "region" in out  # other metadata still flows through
