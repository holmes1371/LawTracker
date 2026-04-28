from datetime import date
from pathlib import Path

from lawtracker.cli import main
from lawtracker.sources import EventRecord


def test_main_runs(capsys):
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "LawTracker" in captured.out


def test_analyze_subcommand_writes_analysis_md(tmp_path: Path, capsys):
    """`lawtracker analyze` reads events.jsonl from a prior scout run and
    writes analysis.md. The two-step split (Tom 2026-04-28) lets the
    spreadsheet be reviewed before the LLM analysis call."""
    e = EventRecord(
        dedup_key="k1",
        source_id="fake_src",
        event_date=date(2026, 3, 1),
        title="Test event",
        primary_actor="Acme",
        summary="A summary",
        url="https://example.test/1",
        country="US",
        metadata={},
    )
    (tmp_path / "events.jsonl").write_text(e.model_dump_json() + "\n", encoding="utf-8")

    rc = main(["analyze", "--input-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert (tmp_path / "analysis.md").exists()
    assert "Analyzed 1 events" in captured.out


def test_analyze_subcommand_errors_when_no_jsonl(tmp_path: Path, capsys):
    rc = main(["analyze", "--input-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "No events.jsonl" in captured.out
