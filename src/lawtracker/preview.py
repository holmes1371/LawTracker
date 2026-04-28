"""HTML mockup renderer for the scout outputs.

Produces two static pages from `events.jsonl` + `analysis.md`:

- `analysis.html` — country-by-country narrative analysis, blog-style.
  Alphabetical, US first.
- `sources.html` — event feed grouped by country (US first, rest alpha),
  reverse-chronological within each country. Title + summary per event.

Both pages are self-contained: Tailwind via CDN, no JS framework, no
build step. Open by double-click in Explorer or via `start
data\\scout\\analysis.html` in PowerShell. Final hosting will be on
lawmasolutions.com (item 9 / 10) — markup carries forward into the
Jinja2 templates when item 6 lands.
"""

from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

from lawtracker.sources import EventRecord


def render_pages(input_dir: Path) -> tuple[Path, Path]:
    """Render analysis.html and sources.html from input_dir contents.

    Returns (analysis_path, sources_path).
    """
    analysis_md = input_dir / "analysis.md"
    jsonl = input_dir / "events.jsonl"
    if not jsonl.exists():
        raise RuntimeError(
            f"No events.jsonl at {jsonl}. Run `lawtracker scout` first."
        )

    analysis_html = _render_analysis_page(analysis_md)
    sources_html = _render_sources_page(jsonl)

    out_a = input_dir / "analysis.html"
    out_s = input_dir / "sources.html"
    out_a.write_text(analysis_html, encoding="utf-8")
    out_s.write_text(sources_html, encoding="utf-8")
    return out_a, out_s


# ---- Analysis page ------------------------------------------------------


def _render_analysis_page(analysis_md_path: Path) -> str:
    if analysis_md_path.exists():
        sections = _extract_country_sections(analysis_md_path.read_text(encoding="utf-8"))
    else:
        sections = {}

    if not sections:
        body = (
            "<p class='text-slate-600'>No analysis available. Run "
            "<code class='bg-slate-100 px-1 rounded'>lawtracker analyze "
            "--llm-mode=anthropic</code> first.</p>"
        )
    else:
        body = _render_country_articles(_sort_country_sections(sections))

    return _wrap_html("Analysis", "analysis", body)


def _extract_country_sections(md: str) -> dict[str, str]:
    """Pull per-country sections out of the narrative analysis block.

    The analysis.md structure is:
        # title
        deterministic counts
        ---
        ## Narrative analysis
        > stub-marker (optional)
        ## United States
        bullets...
        ## Brazil
        bullets...
        ---
        <details>prompt preview</details>

    We slice between `## Narrative analysis` and the trailing `---` /
    `<details>`, then split on `## ` headings.
    """
    head, _, tail = md.partition("## Narrative analysis")
    if not tail:
        return {}
    # Cut off the prompt-preview footer. The LLM frequently uses `---`
    # between country sections, so we cannot cut on `---` here — the
    # `<details>` boundary alone is the structural marker for the footer.
    tail = tail.split("<details>", 1)[0]

    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in tail.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current is None:
            # Lines before the first `## ` heading (e.g. stub-marker
            # blockquote) — drop.
            continue
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()

    return {k: v for k, v in sections.items() if v}


def _sort_country_sections(sections: dict[str, str]) -> list[tuple[str, str]]:
    """US first, cross-jurisdictional last, everything else alpha."""

    def key(item: tuple[str, str]) -> tuple[int, str]:
        name = item[0]
        lower = name.lower()
        if lower in ("united states", "usa", "us"):
            return (0, lower)
        if "cross-jurisdictional" in lower or "global" in lower:
            return (2, lower)
        return (1, lower)

    return sorted(sections.items(), key=key)


def _render_country_articles(sections: list[tuple[str, str]]) -> str:
    parts = []
    for country, body in sections:
        body_html = _md_to_html(body)
        article_class = (
            "mb-10 pb-10 border-b border-slate-200 last:border-0 last:mb-0 last:pb-0"
        )
        parts.append(
            f"""<article class="{article_class}">
  <h2 class="text-2xl font-semibold text-slate-900 mb-4">{html.escape(country)}</h2>
  <div class="space-y-3 text-slate-800 leading-relaxed">{body_html}</div>
</article>"""
        )
    return "\n".join(parts)


def _md_to_html(text: str) -> str:
    """Tiny markdown → HTML for the LLM's output shape: bullets + bold +
    inline code + links. Hand-rolled to avoid a new dependency."""
    lines = text.splitlines()
    out: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            if not in_list:
                out.append("<ul class='list-disc ml-6 space-y-2'>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        elif stripped.startswith(">"):
            close_list()
            # Drop blockquotes — these are stub-marker meta noise.
            continue
        elif re.fullmatch(r"-{3,}", stripped):
            # Horizontal rules (---) — country headings already provide
            # the visual separation; suppress to keep the page clean.
            close_list()
            continue
        elif not stripped:
            close_list()
        else:
            close_list()
            out.append(f"<p>{_inline(stripped)}</p>")
    close_list()
    return "\n".join(out)


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)")
_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    text = html.escape(text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)
    text = _CODE_RE.sub(r"<code class='bg-slate-100 px-1 rounded'>\1</code>", text)
    text = _LINK_RE.sub(
        r'<a href="\2" class="text-blue-700 hover:underline" target="_blank">\1</a>',
        text,
    )
    return text


# ---- Sources page -------------------------------------------------------


def _render_sources_page(jsonl_path: Path) -> str:
    events: list[EventRecord] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(EventRecord.model_validate_json(line))

    grouped: dict[str, list[EventRecord]] = {}
    for e in events:
        bucket = e.country or "(uncategorized)"
        grouped.setdefault(bucket, []).append(e)

    def country_key(name: str) -> tuple[int, str]:
        lower = name.lower()
        if lower in ("united states", "usa", "us"):
            return (0, lower)
        if name == "(uncategorized)":
            return (2, lower)
        return (1, lower)

    sorted_countries = sorted(grouped.keys(), key=country_key)

    body_parts = []
    for country in sorted_countries:
        items = grouped[country]
        items.sort(key=lambda e: e.event_date or date.min, reverse=True)
        body_parts.append(_render_country_section(country, items))

    if not body_parts:
        body = (
            "<p class='text-slate-600'>No events. Run "
            "<code class='bg-slate-100 px-1 rounded'>lawtracker scout</code> "
            "first.</p>"
        )
    else:
        body = "\n".join(body_parts)
    return _wrap_html("Sources", "sources", body)


def _render_country_section(country: str, events: list[EventRecord]) -> str:
    items_html = "\n".join(_render_event_card(e) for e in events)
    return f"""<section class="mb-12">
  <h2 class="text-2xl font-semibold text-slate-900 mb-5 pb-2 border-b border-slate-300">
    {html.escape(country)}
    <span class="text-base font-normal text-slate-500">({len(events)})</span>
  </h2>
  <div class="space-y-6">
{items_html}
  </div>
</section>"""


def _render_event_card(e: EventRecord) -> str:
    # Display format Tom set 2026-04-28: "dd MONTH yyyy", no dashes
    # (e.g. "15 March 2026"). %d is zero-padded; full month name via %B.
    date_str = e.event_date.strftime("%d %B %Y") if e.event_date else "—"
    if e.url:
        title_html = (
            f'<a href="{html.escape(e.url)}" '
            f'class="text-blue-700 hover:underline" target="_blank">'
            f"{html.escape(e.title)}</a>"
        )
    else:
        title_html = html.escape(e.title)

    summary_html = (
        f"<p class='text-slate-700 mt-1'>{html.escape(e.summary)}</p>"
        if e.summary
        else ""
    )

    actor_html = (
        f"<span class='text-slate-500'> · {html.escape(e.primary_actor)}</span>"
        if e.primary_actor
        else ""
    )

    meta_html = (
        f'<div class="text-sm text-slate-500">{date_str}{actor_html}</div>'
    )
    return f"""    <article>
      {meta_html}
      <h3 class="font-semibold text-slate-900 mt-1 leading-snug">{title_html}</h3>
      {summary_html}
    </article>"""


# ---- Shared layout ------------------------------------------------------


def _wrap_html(title: str, current_page: str, body: str) -> str:
    def nav_class(page: str) -> str:
        if page == current_page:
            return "font-semibold text-slate-900 border-b-2 border-slate-900 pb-1"
        return "text-slate-600 hover:text-slate-900 pb-1"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LawTracker — {html.escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900 antialiased">
<header class="border-b border-slate-200 bg-white">
  <div class="max-w-4xl mx-auto px-6 py-4 flex items-baseline justify-between">
    <a href="analysis.html" class="text-xl font-semibold tracking-tight">LawTracker</a>
    <nav class="space-x-6 text-sm">
      <a href="analysis.html" class="{nav_class("analysis")}">Analysis</a>
      <a href="sources.html" class="{nav_class("sources")}">Sources</a>
    </nav>
  </div>
</header>
<main class="max-w-4xl mx-auto px-6 py-10">
  <h1 class="text-3xl font-bold tracking-tight text-slate-900 mb-10">{html.escape(title)}</h1>
  {body}
</main>
<footer class="max-w-4xl mx-auto px-6 py-8 mt-10 text-sm text-slate-500 border-t border-slate-200">
  Static mockup — generated by
  <code class="bg-slate-100 px-1 rounded">lawtracker render</code>.
  Production target: lawmasolutions.com.
</footer>
</body>
</html>
"""
