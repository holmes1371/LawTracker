"""Tests for the data scout.

Use fake adapters returning canned EventRecord lists; verify the three
output files are written and well-formed. No live network.
"""

import json
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from lawtracker.scout import run
from lawtracker.sources import EventRecord, PollResult, SourceAdapter


class _OkAdapter(SourceAdapter):
    source_id = "fake_ok"
    kind = "event_list"
    url = "https://example.test/ok"

    def poll(self, *, client=None) -> PollResult:  # type: ignore[override]
        return PollResult(
            status="ok",
            events=[
                EventRecord(
                    dedup_key="https://example.test/case/1",
                    source_id="fake_ok",
                    event_date=date(2026, 3, 15),
                    title="Test Case A",
                    primary_actor="Acme Corp",
                    summary="Quick summary",
                    url="https://example.test/case/1",
                    country="US",
                    metadata={"industry": "pharma", "case_number": "1:26-cr-00001"},
                ),
                EventRecord(
                    dedup_key="https://example.test/case/2",
                    source_id="fake_ok",
                    event_date=date(2025, 11, 10),
                    title="Test Case B",
                    primary_actor="Beta Inc",
                    summary=None,
                    url="https://example.test/case/2",
                    country="AU",
                    metadata={"industry": "extractive"},
                ),
            ],
        )

    def parse(self, html: str) -> list[EventRecord]:
        return []


class _OtherOkAdapter(SourceAdapter):
    source_id = "fake_blog"
    kind = "event_list"
    url = "https://example.test/blog"

    def poll(self, *, client=None) -> PollResult:  # type: ignore[override]
        return PollResult(
            status="ok",
            events=[
                EventRecord(
                    dedup_key="https://blog.test/post/1",
                    source_id="fake_blog",
                    event_date=date(2026, 4, 20),
                    title="Post Title",
                    primary_actor=None,
                    summary="Post summary",
                    url="https://blog.test/post/1",
                    country=None,
                    metadata={"tags": "FCPA, anticorruption"},
                ),
            ],
        )

    def parse(self, html: str) -> list[EventRecord]:
        return []


class _FailingAdapter(SourceAdapter):
    source_id = "fake_fail"
    kind = "event_list"
    url = "https://example.test/fail"

    def poll(self, *, client=None) -> PollResult:  # type: ignore[override]
        return PollResult(status="permanent_failure", error="simulated failure")

    def parse(self, html: str) -> list[EventRecord]:
        return []


def test_scout_writes_three_files(tmp_path: Path):
    report = run([_OkAdapter, _OtherOkAdapter], tmp_path)
    assert (tmp_path / "events.xlsx").exists()
    assert (tmp_path / "events.jsonl").exists()
    assert (tmp_path / "summary.txt").exists()
    assert report["events_collected"] == 3


def test_xlsx_has_universal_columns_and_metadata_union(tmp_path: Path):
    run([_OkAdapter, _OtherOkAdapter], tmp_path)

    wb = load_workbook(tmp_path / "events.xlsx")
    ws = wb.active
    headers = [c.value for c in ws[1]]

    universal = [
        "event_date",
        "source_id",
        "country",
        "title",
        "primary_actor",
        "summary",
        "url",
        "dedup_key",
    ]
    assert headers[:8] == universal

    metadata_cols = headers[8:]
    assert metadata_cols == sorted(metadata_cols)
    assert "industry" in metadata_cols
    assert "case_number" in metadata_cols
    assert "tags" in metadata_cols
    assert ws.freeze_panes == "A2"


def test_jsonl_one_line_per_event(tmp_path: Path):
    run([_OkAdapter, _OtherOkAdapter], tmp_path)
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert all("dedup_key" in r for r in parsed)


def test_summary_includes_per_source_status_and_failure_error(tmp_path: Path):
    run([_OkAdapter, _OtherOkAdapter, _FailingAdapter], tmp_path)
    summary = (tmp_path / "summary.txt").read_text(encoding="utf-8")
    assert "fake_ok" in summary
    assert "fake_blog" in summary
    assert "fake_fail" in summary
    assert "permanent_failure" in summary
    assert "simulated failure" in summary


def test_summary_includes_country_and_industry_breakdowns(tmp_path: Path):
    run([_OkAdapter, _OtherOkAdapter], tmp_path)
    summary = (tmp_path / "summary.txt").read_text(encoding="utf-8")
    assert "Events per country" in summary
    assert "US" in summary
    assert "AU" in summary
    assert "(none)" in summary
    assert "Top 20 industries" in summary
    assert "pharma" in summary
    assert "extractive" in summary


def test_empty_run_still_writes_files(tmp_path: Path):
    report = run([_FailingAdapter], tmp_path)
    assert (tmp_path / "events.xlsx").exists()
    assert (tmp_path / "events.jsonl").exists()
    assert (tmp_path / "summary.txt").exists()
    assert report["events_collected"] == 0


def test_source_filter_restricts_to_one_adapter(tmp_path: Path):
    report = run(
        [_OkAdapter, _OtherOkAdapter, _FailingAdapter],
        tmp_path,
        source_filter="fake_ok",
    )
    assert report["events_collected"] == 2
    assert len(report["poll_log"]) == 1
    assert report["poll_log"][0]["source_id"] == "fake_ok"
