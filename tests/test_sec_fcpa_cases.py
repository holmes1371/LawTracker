"""Tests for the SEC FCPA cases adapter (LLM-extracted)."""

from __future__ import annotations

import json

import httpx
import pytest

from lawtracker.sources.sec_fcpa_cases import (
    SecFcpaCasesAdapter,
    _records_from_llm_response,
    _slice_to_recent_years,
)

_PAGE = """\
<html><body><article>
<h1>SEC FCPA Cases</h1>
<p>FCPA enforcement is a high priority area for the SEC.</p>
<h2>2025</h2>
<p><b>Acme Corp.</b> agreed to pay $10 million to resolve FCPA charges (07/15/2025). SEC Order.</p>
<h2>2024</h2>
<p><b>Beta Industries</b> settled a civil action for $5 million (12/01/2024).</p>
<h2>2023</h2>
<p>Older case from 2023 — should be excluded by the recent-years slice.</p>
</article></body></html>
"""


def test_slice_keeps_only_most_recent_n_years() -> None:
    excerpt = _slice_to_recent_years(_PAGE, n_years=2)
    assert "Acme Corp." in excerpt  # 2025 entry — most recent
    assert "Beta Industries" in excerpt  # 2024 entry — second-most-recent
    assert "Older case from 2023" not in excerpt  # 3rd most recent — excluded


def test_slice_returns_empty_when_page_has_no_year_headings() -> None:
    no_year_page = (
        "<html><body><article>Just a sentence with no year headings.</article></body></html>"
    )
    excerpt = _slice_to_recent_years(no_year_page, n_years=2)
    assert excerpt == ""


def test_slice_handles_n_larger_than_available() -> None:
    """If the page only has 2 years and we ask for 5, slice returns those 2."""
    excerpt = _slice_to_recent_years(_PAGE, n_years=5)
    assert "Acme Corp." in excerpt
    assert "Beta Industries" in excerpt


def test_records_from_valid_llm_response() -> None:
    response = json.dumps(
        [
            {
                "title": "SEC v. Sample Corp.",
                "event_date": "2025-09-15",
                "primary_actor": "Sample Corp.",
                "summary": "Civil enforcement action.",
                "detail_url": "https://www.sec.gov/litigation/admin/sample.pdf",
                "metadata": {
                    "action_type": "administrative_proceeding",
                    "country": "BR",
                    "industry": "extractive",
                },
            }
        ]
    )
    records = _records_from_llm_response(response)
    assert len(records) == 1
    e = records[0]
    assert e.source_id == "sec_fcpa_cases"
    assert e.country == "US"
    assert e.title == "SEC v. Sample Corp."
    assert e.event_date is not None and e.event_date.year == 2025
    assert e.metadata["action_type"] == "administrative_proceeding"
    assert e.metadata["country"] == "BR"  # case country (different from outlet country)
    assert e.dedup_key.endswith("sample.pdf")


def test_records_from_response_strips_code_fence() -> None:
    response = '```json\n[{"title": "X", "detail_url": "https://x"}]\n```'
    records = _records_from_llm_response(response)
    assert len(records) == 1
    assert records[0].title == "X"


def test_records_from_invalid_json_returns_empty() -> None:
    assert _records_from_llm_response("definitely not json") == []
    assert _records_from_llm_response("") == []
    assert _records_from_llm_response("{}") == []  # not a list


def test_stub_mode_emits_placeholder_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """In stub mode, the adapter still emits structured records so the
    pipeline (Excel / JSONL / analysis) can be exercised end-to-end
    during design iteration."""
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "stub")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_PAGE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SecFcpaCasesAdapter().poll(client=client)

    assert result.status == "ok"
    assert result.events, "stub should emit at least one placeholder record"
    for event in result.events:
        assert event.source_id == "sec_fcpa_cases"
        assert event.country == "US"
        assert "[STUB]" in event.title


def test_off_mode_returns_no_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAWTRACKER_LLM_MODE", "off")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_PAGE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SecFcpaCasesAdapter().poll(client=client)

    assert result.status == "ok"
    assert result.events == []
