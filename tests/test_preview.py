"""Tests for the static HTML mockup renderer."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lawtracker.preview import render_pages
from lawtracker.sources import EventRecord


def _write_jsonl(path: Path, events: list[EventRecord]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(e.model_dump_json() + "\n")


def _write_analysis_md(path: Path, narrative: str) -> None:
    """Wrap a narrative body in the same scaffold `build_analysis` produces."""
    path.write_text(
        "# Anti-Corruption Enforcement Analysis — 2026-04-28\n\n"
        "_n events from m sources..._\n\n"
        "## Source counts\n- foo: 1\n\n"
        "## Country counts\n- US: 1\n\n"
        "---\n\n"
        "## Narrative analysis\n\n"
        f"{narrative}\n\n"
        "---\n\n"
        "<details>\n<summary>Prompt sent to LLM</summary>\nstuff\n</details>\n",
        encoding="utf-8",
    )


def test_render_writes_all_four_pages(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="k1",
                source_id="src",
                event_date=date(2026, 3, 15),
                title="Test event",
                primary_actor="Acme",
                summary="A summary",
                url="https://example.test/1",
                country="US",
                metadata={},
            )
        ],
    )
    _write_analysis_md(
        tmp_path / "analysis.md",
        "## United States\n- DOJ resolved a case.\n",
    )
    out_pa, out_ps, out_aa, out_as = render_pages(tmp_path)
    assert out_pa.exists() and out_pa.name == "analysis.html"
    assert out_ps.exists() and out_ps.name == "sources.html"
    assert out_aa.exists() and out_aa.parent.name == "admin"
    assert out_as.exists() and out_as.parent.name == "admin"


def test_render_errors_when_no_jsonl(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="No events.jsonl"):
        render_pages(tmp_path)


def test_sources_page_uses_dd_month_yyyy_date_format(tmp_path: Path) -> None:
    """Tom 2026-04-28: date format is `dd MONTH yyyy` (e.g. 15 March 2026),
    not ISO with dashes."""
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="k1",
                source_id="src",
                event_date=date(2026, 3, 15),
                title="T",
                primary_actor=None,
                summary=None,
                url="https://example.test",
                country="US",
                metadata={},
            )
        ],
    )
    render_pages(tmp_path)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    assert "15 March 2026" in html
    assert "2026-03-15" not in html


def test_sources_page_groups_by_country_us_first_then_alpha(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="b",
                source_id="src",
                event_date=date(2026, 1, 1),
                title="B event",
                primary_actor=None,
                summary=None,
                url="https://example.test/b",
                country="Brazil",
                metadata={},
            ),
            EventRecord(
                dedup_key="u",
                source_id="src",
                event_date=date(2026, 1, 1),
                title="U event",
                primary_actor=None,
                summary=None,
                url="https://example.test/u",
                country="US",
                metadata={},
            ),
            EventRecord(
                dedup_key="a",
                source_id="src",
                event_date=date(2026, 1, 1),
                title="A event",
                primary_actor=None,
                summary=None,
                url="https://example.test/a",
                country="Argentina",
                metadata={},
            ),
        ],
    )
    render_pages(tmp_path)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    us_idx = html.index("US")
    arg_idx = html.index("Argentina")
    bra_idx = html.index("Brazil")
    assert us_idx < arg_idx < bra_idx, "US must come first; rest alphabetical"


def test_sources_page_reverse_chrono_within_country(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="old",
                source_id="src",
                event_date=date(2025, 6, 1),
                title="OLDER EVENT",
                primary_actor=None,
                summary=None,
                url="https://example.test/old",
                country="US",
                metadata={},
            ),
            EventRecord(
                dedup_key="new",
                source_id="src",
                event_date=date(2026, 4, 1),
                title="NEWER EVENT",
                primary_actor=None,
                summary=None,
                url="https://example.test/new",
                country="US",
                metadata={},
            ),
        ],
    )
    render_pages(tmp_path)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    assert html.index("NEWER EVENT") < html.index("OLDER EVENT")


def test_analysis_page_us_first_then_alpha(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "events.jsonl", [])
    _write_analysis_md(
        tmp_path / "analysis.md",
        "## Brazil\n- Brazilian bullet.\n\n"
        "## United States\n- US bullet.\n\n"
        "## Argentina\n- Argentine bullet.\n",
    )
    render_pages(tmp_path)
    html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
    us_idx = html.index("United States")
    arg_idx = html.index("Argentina")
    bra_idx = html.index("Brazil")
    assert us_idx < arg_idx < bra_idx


def test_analysis_page_renders_bold_and_bullets(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "events.jsonl", [])
    _write_analysis_md(
        tmp_path / "analysis.md",
        "## United States\n- **DOJ FCPA Unit** resolved a case.\n",
    )
    render_pages(tmp_path)
    html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
    assert "<strong>DOJ FCPA Unit</strong>" in html
    assert "<li>" in html


def test_analysis_page_drops_stub_blockquote_marker(tmp_path: Path) -> None:
    """The stub-mode marker is a `>` blockquote; it shouldn't render."""
    _write_jsonl(tmp_path / "events.jsonl", [])
    _write_analysis_md(
        tmp_path / "analysis.md",
        "> _**[STUB LLM RESPONSE]** noise._\n\n"
        "## United States\n- Real bullet.\n",
    )
    render_pages(tmp_path)
    html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
    assert "STUB LLM RESPONSE" not in html
    assert "Real bullet" in html


def test_analysis_page_handles_missing_analysis_md(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "events.jsonl", [])
    render_pages(tmp_path)
    html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
    assert "No analysis available" in html


def test_analysis_keeps_all_country_sections_when_llm_uses_hr_separators(
    tmp_path: Path,
) -> None:
    """Regression: Claude often emits `---` between country sections.
    The previous parser cut at the first `---`, dropping every section
    after the first one. Tom hit this 2026-04-28 (US present, AUS + UK
    missing on analysis.html)."""
    _write_jsonl(tmp_path / "events.jsonl", [])
    _write_analysis_md(
        tmp_path / "analysis.md",
        "## United States\n- US bullet.\n\n"
        "---\n\n"
        "## Australia\n- AUS bullet.\n\n"
        "---\n\n"
        "## United Kingdom\n- UK bullet.\n",
    )
    render_pages(tmp_path)
    html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
    assert "United States" in html
    assert "Australia" in html
    assert "United Kingdom" in html
    assert "AUS bullet" in html
    assert "UK bullet" in html
    # The `---` separator itself shouldn't render as a paragraph.
    assert "<p>---</p>" not in html


def test_pages_link_to_each_other(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "events.jsonl", [])
    render_pages(tmp_path)
    a_html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
    s_html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    assert 'href="sources.html"' in a_html
    assert 'href="analysis.html"' in s_html


def test_admin_sources_has_hide_buttons_per_source_link(tmp_path: Path) -> None:
    """Admin Sources page shows a 'Hide Source Link' button per event
    so Ellen can flag noise before re-running analysis. Terminology
    "Source Link" set by Tom 2026-04-28 — replaces the earlier
    "article" wording across the admin UI."""
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="k1",
                source_id="s",
                event_date=date(2026, 1, 1),
                title="Event 1",
                primary_actor=None,
                summary=None,
                url="https://example.test/1",
                country="US",
                metadata={},
            ),
            EventRecord(
                dedup_key="k2",
                source_id="s",
                event_date=date(2026, 1, 2),
                title="Event 2",
                primary_actor=None,
                summary=None,
                url="https://example.test/2",
                country="US",
                metadata={},
            ),
        ],
    )
    render_pages(tmp_path)
    admin_sources = (tmp_path / "admin" / "sources.html").read_text(encoding="utf-8")
    # Two events → two Hide buttons.
    assert admin_sources.count("Hide Source Link") == 2
    # Public Sources page must NOT have hide buttons.
    public_sources = (tmp_path / "sources.html").read_text(encoding="utf-8")
    assert "Hide Source Link" not in public_sources


def test_admin_analysis_has_edit_textarea_per_entry(tmp_path: Path) -> None:
    """Tom 2026-04-28: edit boxes are per-entry (one per bullet), not
    per-country. Easier for Ellen to read each entry against its
    source side-by-side."""
    _write_jsonl(tmp_path / "events.jsonl", [])
    _write_analysis_md(
        tmp_path / "analysis.md",
        "## United States\n- US bullet 1.\n- US bullet 2.\n- US bullet 3.\n\n"
        "## Brazil\n- Brazil bullet.\n",
    )
    render_pages(tmp_path)
    admin_analysis = (tmp_path / "admin" / "analysis.html").read_text(encoding="utf-8")
    # 3 US bullets + 1 Brazil bullet = 4 textareas, 4 Save buttons.
    assert admin_analysis.count("<textarea") == 4
    assert admin_analysis.count(">\n          Save\n        </button>") == 4
    # Each bullet's source pre-populates its textarea.
    for s in ("US bullet 1.", "US bullet 2.", "US bullet 3.", "Brazil bullet."):
        assert s in admin_analysis
    # Public analysis page must NOT have textareas.
    public_analysis = (tmp_path / "analysis.html").read_text(encoding="utf-8")
    assert "<textarea" not in public_analysis


def test_admin_analysis_textarea_does_not_include_leading_bullet_marker(
    tmp_path: Path,
) -> None:
    """The textarea shows just the bullet's text content, not the
    leading `- ` marker. The marker is implicit (every entry on this
    page is a bullet); making Ellen edit around it would be friction."""
    _write_jsonl(tmp_path / "events.jsonl", [])
    _write_analysis_md(
        tmp_path / "analysis.md",
        "## United States\n- DOJ resolved a case.\n",
    )
    render_pages(tmp_path)
    admin_analysis = (tmp_path / "admin" / "analysis.html").read_text(encoding="utf-8")
    # Locate the textarea content. It should contain "DOJ resolved a case."
    # but NOT "- DOJ resolved a case."
    import re as _re

    textarea_match = _re.search(
        r'<textarea[^>]*>(.*?)</textarea>', admin_analysis, _re.DOTALL
    )
    assert textarea_match is not None
    textarea_value = textarea_match.group(1)
    assert "DOJ resolved a case." in textarea_value
    assert not textarea_value.lstrip().startswith("- ")


def test_admin_sources_has_hidden_drawer_and_toast_infrastructure(
    tmp_path: Path,
) -> None:
    """Hide/Undo/Restore mockup wiring (Tom 2026-04-28). Each article
    card carries its dedup_key, drawer + toast containers exist, and
    the JS that ties them together is present."""
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="https://example.test/case/1",
                source_id="s",
                event_date=date(2026, 1, 1),
                title="Case 1",
                primary_actor=None,
                summary=None,
                url="https://example.test/case/1",
                country="US",
                metadata={},
            )
        ],
    )
    render_pages(tmp_path)
    admin_sources = (tmp_path / "admin" / "sources.html").read_text(encoding="utf-8")

    # Article carries data-dedup-key so JS can match it on Hide.
    assert 'data-dedup-key="https://example.test/case/1"' in admin_sources
    # Hide button uses class-based wiring, not inline alert().
    assert 'class="hide-btn ' in admin_sources
    # Drawer + toast containers present.
    assert 'id="hidden-drawer"' in admin_sources
    assert 'id="drawer-list"' in admin_sources
    assert 'id="toast"' in admin_sources
    # Live JS handlers (sessionStorage + DOM wiring).
    assert "sessionStorage" in admin_sources
    assert "hideArticle" in admin_sources
    assert "restoreArticle" in admin_sources


def test_admin_pages_have_generate_and_publish_buttons(tmp_path: Path) -> None:
    """Header on every admin page shows Generate-new-analysis +
    Publish-to-site buttons."""
    _write_jsonl(tmp_path / "events.jsonl", [])
    render_pages(tmp_path)
    for page in ("admin/analysis.html", "admin/sources.html"):
        html_text = (tmp_path / page).read_text(encoding="utf-8")
        assert "Generate new analysis" in html_text, page
        assert "Publish to site" in html_text, page


def test_admin_uses_ellen_friendly_terminology(tmp_path: Path) -> None:
    """Ellen, not a developer, drives the admin dashboard. Surface
    plain-language labels and avoid jargon. Locks in: 'Source Links'
    instead of 'Sources', 'Hide Source Link' instead of 'Exclude',
    'Generate new analysis' instead of 'Re-run'."""
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="k",
                source_id="s",
                event_date=date(2026, 1, 1),
                title="t",
                primary_actor=None,
                summary=None,
                url="https://example.test",
                country="US",
                metadata={},
            )
        ],
    )
    render_pages(tmp_path)
    admin_sources = (tmp_path / "admin" / "sources.html").read_text(encoding="utf-8")
    assert "Source Links" in admin_sources
    assert "Hide Source Link" in admin_sources
    assert "Exclude" not in admin_sources
    assert "dedup_key" not in admin_sources


def test_admin_pages_link_back_to_public(tmp_path: Path) -> None:
    """Admin pages need a way out — a 'View public site' link in the
    nav. Cross-links go up one directory because admin/ is a subdir."""
    _write_jsonl(tmp_path / "events.jsonl", [])
    render_pages(tmp_path)
    admin_analysis = (tmp_path / "admin" / "analysis.html").read_text(encoding="utf-8")
    assert 'href="../analysis.html"' in admin_analysis
    assert "View public site" in admin_analysis


def test_event_url_is_clickable_in_sources_page(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "events.jsonl",
        [
            EventRecord(
                dedup_key="k",
                source_id="src",
                event_date=date(2026, 1, 1),
                title="Event title",
                primary_actor=None,
                summary="Summary text",
                url="https://example.test/article",
                country="US",
                metadata={},
            )
        ],
    )
    render_pages(tmp_path)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    assert 'href="https://example.test/article"' in html
    assert "Summary text" in html
