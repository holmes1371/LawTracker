"""HTML mockup renderer for the scout outputs.

Produces four static pages from `events.jsonl` + `analysis.md`:

- `analysis.html` (public) — country-by-country narrative, blog-style.
- `sources.html` (public) — event feed grouped by country.
- `admin/analysis.html` — admin variant with per-country edit textareas
  + Save buttons; status banner with last LLM run + edit count;
  Re-run / Publish controls in the header.
- `admin/sources.html` — admin variant with per-event "Exclude"
  buttons; status banner with event/exclusion counts; Re-run / Publish
  controls in the header.

All four pages are self-contained: Tailwind via CDN, no JS framework
beyond a couple of `alert()` stubs on the admin action buttons (the
mockup demonstrates UI shape; interactions wire up in item 21's live
FastAPI buildout). Tom + Ellen open by double-click in Explorer or
`start data\\scout\\analysis.html` in PowerShell.

The admin / public split mirrors the URL split planned for the live
app (`/admin/*` vs `/`), so markup carries forward into Jinja2
templates with minimal rework.
"""

from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

from lawtracker.sources import EventRecord


def render_pages(input_dir: Path) -> tuple[Path, Path, Path, Path]:
    """Render the four mockup pages from input_dir contents.

    Returns (public_analysis, public_sources, admin_analysis,
    admin_sources) paths.
    """
    analysis_md = input_dir / "analysis.md"
    jsonl = input_dir / "events.jsonl"
    if not jsonl.exists():
        raise RuntimeError(
            f"No events.jsonl at {jsonl}. Run `lawtracker scout` first."
        )

    events = _load_events(jsonl)
    analysis_md_text = (
        analysis_md.read_text(encoding="utf-8") if analysis_md.exists() else ""
    )
    sections = _extract_country_sections(analysis_md_text)

    public_analysis_html = _render_public_analysis(sections)
    public_sources_html = _render_public_sources(events)
    admin_analysis_html = _render_admin_analysis(sections, events)
    admin_sources_html = _render_admin_sources(events)

    out_pa = input_dir / "analysis.html"
    out_ps = input_dir / "sources.html"
    admin_dir = input_dir / "admin"
    admin_dir.mkdir(parents=True, exist_ok=True)
    out_aa = admin_dir / "analysis.html"
    out_as = admin_dir / "sources.html"

    out_pa.write_text(public_analysis_html, encoding="utf-8")
    out_ps.write_text(public_sources_html, encoding="utf-8")
    out_aa.write_text(admin_analysis_html, encoding="utf-8")
    out_as.write_text(admin_sources_html, encoding="utf-8")
    return out_pa, out_ps, out_aa, out_as


def _load_events(jsonl_path: Path) -> list[EventRecord]:
    events: list[EventRecord] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(EventRecord.model_validate_json(line))
    return events


# ---- Analysis page (public) ---------------------------------------------


def _render_public_analysis(sections: dict[str, str]) -> str:
    if not sections:
        body = (
            "<p class='text-slate-600'>No analysis available. Run "
            "<code class='bg-slate-100 px-1 rounded'>lawtracker analyze "
            "--llm-mode=anthropic</code> first.</p>"
        )
    else:
        body = _render_country_articles(_sort_country_sections(sections))

    return _wrap_html("Analysis", "analysis", body, mode="public")


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


# ---- Sources page (public) ----------------------------------------------


def _render_public_sources(events: list[EventRecord]) -> str:
    by_country = _group_events_by_country(events)
    body_parts = [
        _render_country_section(country, items, admin=False)
        for country, items in by_country
    ]

    if not body_parts:
        body = (
            "<p class='text-slate-600'>No events. Run "
            "<code class='bg-slate-100 px-1 rounded'>lawtracker scout</code> "
            "first.</p>"
        )
    else:
        body = "\n".join(body_parts)
    return _wrap_html("Sources", "sources", body, mode="public")


def _group_events_by_country(
    events: list[EventRecord],
) -> list[tuple[str, list[EventRecord]]]:
    """Group events by country (US first, alpha rest, '(uncategorized)' last);
    reverse-chrono within each country."""
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

    out: list[tuple[str, list[EventRecord]]] = []
    for country in sorted(grouped.keys(), key=country_key):
        items = grouped[country]
        items.sort(key=lambda e: e.event_date or date.min, reverse=True)
        out.append((country, items))
    return out


def _render_country_section(
    country: str, events: list[EventRecord], *, admin: bool
) -> str:
    items_html = "\n".join(_render_event_card(e, admin=admin) for e in events)
    return f"""<section class="mb-12">
  <h2 class="text-2xl font-semibold text-slate-900 mb-5 pb-2 border-b border-slate-300">
    {html.escape(country)}
    <span class="text-base font-normal text-slate-500">({len(events)})</span>
  </h2>
  <div class="space-y-6">
{items_html}
  </div>
</section>"""


def _render_event_card(e: EventRecord, *, admin: bool) -> str:
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

    if admin:
        # Hide button has no inline onclick — admin script wires up
        # click handlers via querySelectorAll('.hide-btn') on
        # DOMContentLoaded, which avoids quote-escaping `dedup_key`
        # values into JS string literals.
        safe_dedup = html.escape(e.dedup_key, quote=True)
        return f"""    <article class="article-card flex gap-4 items-start" data-dedup-key="{safe_dedup}">
      <div class="flex-1 min-w-0">
        {meta_html}
        <h3 class="font-semibold text-slate-900 mt-1 leading-snug">{title_html}</h3>
        {summary_html}
      </div>
      <button type="button" class="hide-btn text-sm text-slate-500 hover:text-red-600 border border-slate-300 hover:border-red-400 rounded px-3 py-1 whitespace-nowrap self-start">
        Hide article
      </button>
    </article>"""

    return f"""    <article>
      {meta_html}
      <h3 class="font-semibold text-slate-900 mt-1 leading-snug">{title_html}</h3>
      {summary_html}
    </article>"""


# ---- Admin pages --------------------------------------------------------


def _render_admin_sources(events: list[EventRecord]) -> str:
    """Admin variant of the Sources page. Each article gets a "Hide
    article" button. Hidden articles move to a collapsible drawer at
    the bottom of the page; a toast notification offers an immediate
    Undo. State persists in sessionStorage across reloads (mockup
    only; live app stores server-side and auto-deletes after 60 days
    per Tom 2026-04-28)."""
    by_country = _group_events_by_country(events)
    n_total = len(events)

    banner = f"""<div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
  <div class="text-amber-900 font-semibold">{n_total} articles available</div>
  <div class="text-sm text-amber-800 mt-1"><span id="hidden-count">0</span> currently hidden &middot; last analysis run not yet performed</div>
</div>"""

    help_text = """<p class="text-slate-600 mb-8 leading-relaxed">
Review the articles below. <strong>Hide</strong> any that aren't relevant or
that might dilute the analysis &mdash; medium-quality commentary, off-topic
posts, items duplicated across other sources. Hidden articles will not appear
on the public site, and they will not be sent to the analysis when you click
<strong>Generate new analysis</strong>. If you hide one by mistake, click
<strong>Undo</strong> in the notification or <strong>Restore</strong> from the
"Hidden articles" section at the bottom.
</p>"""

    body_parts = [
        _render_country_section(country, items, admin=True)
        for country, items in by_country
    ]
    if not body_parts:
        sections_html = (
            "<p class='text-slate-600'>No articles. Run "
            "<code class='bg-slate-100 px-1 rounded'>lawtracker scout</code> "
            "first.</p>"
        )
    else:
        sections_html = "\n".join(body_parts)

    drawer = """<section id="hidden-drawer" class="mt-12 pt-8 border-t border-slate-300 hidden">
  <h2 class="text-xl font-semibold text-slate-900 mb-2">
    Hidden articles
    <span class="text-base font-normal text-slate-500">(<span id="drawer-count">0</span>)</span>
  </h2>
  <p class="text-sm text-slate-600 mb-4">
    These articles are excluded from the public site and the next analysis.
    Click <strong>Restore</strong> to bring one back. (Live app: hidden
    articles are automatically purged after 60 days.)
  </p>
  <ul id="drawer-list" class="bg-white border border-slate-200 rounded-lg divide-y divide-slate-200"></ul>
</section>"""

    body = banner + help_text + sections_html + drawer
    return _wrap_html("Articles", "sources", body, mode="admin")


def _render_admin_analysis(
    sections: dict[str, str], events: list[EventRecord]
) -> str:
    """Admin variant of the Analysis page. Each country section shows
    the rendered preview AND an editable textarea pre-filled with the
    markdown source. Save button per section (visual only)."""
    n_events = len(events)

    if not sections:
        body = (
            "<p class='text-slate-600'>No analysis yet. Click "
            "<strong>Generate new analysis</strong> in the header to "
            "produce one.</p>"
        )
        return _wrap_html("Analysis", "analysis", body, mode="admin")

    banner = f"""<div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
  <div class="text-amber-900 font-semibold">Analysis ready for review</div>
  <div class="text-sm text-amber-800 mt-1">{n_events} articles fed to the analysis &middot; 0 edits saved &middot; not yet published</div>
</div>"""

    help_text = """<p class="text-slate-600 mb-8 leading-relaxed">
Review each country's analysis below. The text on the left is what readers will
see; the box on the right is editable. Make any changes you'd like &mdash;
correct facts, soften phrasing, drop a bullet that doesn't quite work &mdash;
then click <strong>Save</strong> for that country. When everything looks good,
click <strong>Publish to site</strong> in the header.
</p>"""

    sorted_sections = _sort_country_sections(sections)
    section_blocks = []
    for country, body_md in sorted_sections:
        section_blocks.append(_render_admin_country_block(country, body_md))

    body = banner + help_text + "\n".join(section_blocks)
    return _wrap_html("Analysis", "analysis", body, mode="admin")


def _render_admin_country_block(country: str, body_md: str) -> str:
    """Render a country section with one edit card per entry (bullet or
    paragraph). Tom 2026-04-28: per-entry editing is more readable than
    one giant textarea per country.
    """
    safe_country = html.escape(country)
    entries = _split_body_into_entries(body_md)

    if not entries:
        return f"""<section class="mb-10 pb-10 border-b border-slate-200 last:border-0">
  <h2 class="text-2xl font-semibold text-slate-900 mb-4">{safe_country}</h2>
  <p class="text-slate-500 italic">No entries.</p>
</section>"""

    entry_blocks = "\n".join(
        _render_admin_entry_card(country, idx, entry)
        for idx, entry in enumerate(entries)
    )
    return f"""<section class="mb-12 pb-10 border-b border-slate-200 last:border-0">
  <h2 class="text-2xl font-semibold text-slate-900 mb-5">{safe_country}</h2>
  <div class="space-y-4">
    {entry_blocks}
  </div>
</section>"""


def _render_admin_entry_card(country: str, idx: int, entry: dict[str, str]) -> str:
    """One editable card per bullet/paragraph. Preview on top, textarea
    + Save below. Save alerts so Ellen knows the static mockup isn't
    actually persisting."""
    kind = entry["kind"]
    inline_md = entry["inline"]  # markdown stripped of leading "- " for the textarea

    if kind == "bullet":
        bullet_glyph = (
            '<span class="text-slate-400 mt-0.5">&#8226;</span>'  # &bull;
        )
        preview_html = (
            f'<div class="flex gap-3 items-start text-slate-800 leading-relaxed">'
            f"{bullet_glyph}<span>{_inline(inline_md)}</span></div>"
        )
    else:  # paragraph
        preview_html = (
            f'<p class="text-slate-800 leading-relaxed">{_inline(inline_md)}</p>'
        )

    safe_country_id = re.sub(r"[^a-z0-9]+", "-", country.lower()).strip("-")
    textarea_id = f"edit-{safe_country_id}-{idx}"
    safe_textarea_value = html.escape(inline_md)

    save_alert = (
        "In the live app, this would save your edit for this entry "
        + f"({html.escape(country)}, item {idx + 1}). "
        + "Static mockup — no action taken."
    ).replace("'", "&apos;")

    return f"""    <div class="bg-white border border-slate-200 rounded-lg p-4">
      <div class="mb-3">{preview_html}</div>
      <div class="flex gap-3 items-start">
        <textarea id="{textarea_id}"
          class="flex-1 font-mono text-sm bg-slate-50 border border-slate-300 rounded p-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
          rows="2">{safe_textarea_value}</textarea>
        <button type="button"
          onclick="alert('{save_alert}');"
          class="bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded px-4 py-2 whitespace-nowrap self-stretch">
          Save
        </button>
      </div>
    </div>"""


def _split_body_into_entries(body: str) -> list[dict[str, str]]:
    """Split a country-section body into discrete entries: bullets and
    paragraphs. Each entry has `kind` ('bullet'|'paragraph'), `markdown`
    (the raw line(s) including any leading marker), and `inline` (the
    text without the leading bullet marker, suitable for inline rendering
    and for the per-entry textarea).

    Skips horizontal rules (`---`), blockquotes (`>`-prefix lines used
    by the stub LLM marker), and empty lines.
    """
    entries: list[dict[str, str]] = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("- "):
            inline = stripped[2:].rstrip()
            entries.append({"kind": "bullet", "markdown": stripped, "inline": inline})
            i += 1
        elif stripped.startswith(">") or re.fullmatch(r"-{3,}", stripped):
            i += 1  # skip blockquotes + horizontal rules
        elif not stripped:
            i += 1  # skip blank lines
        else:
            # Paragraph: gather contiguous non-empty, non-bullet lines.
            para_lines = [stripped]
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if (
                    not nxt
                    or nxt.startswith("- ")
                    or nxt.startswith(">")
                    or re.fullmatch(r"-{3,}", nxt)
                ):
                    break
                para_lines.append(nxt)
                i += 1
            joined = " ".join(para_lines)
            entries.append({"kind": "paragraph", "markdown": joined, "inline": joined})

    return entries


# ---- Shared layout ------------------------------------------------------


def _wrap_html(title: str, current_page: str, body: str, *, mode: str) -> str:
    """Render a page in either `public` or `admin` mode.

    Layout / Tailwind classes are shared; `mode` controls nav links
    (admin pages live under `admin/`, so cross-links go up one level)
    and whether action buttons (Generate / Publish) appear in the
    header. Container width is wider on admin so side-by-side
    preview/edit columns on the analysis page have room.
    """
    is_admin = mode == "admin"

    def nav_class(page: str) -> str:
        if page == current_page:
            return "font-semibold text-slate-900 border-b-2 border-slate-900 pb-1"
        return "text-slate-600 hover:text-slate-900 pb-1"

    if is_admin:
        analysis_href = "analysis.html"
        sources_href = "sources.html"
        cross_href = "../analysis.html"
        cross_label = "View public site"
        sources_label = "Articles"  # plain-language tab for Ellen
        container_class = "max-w-6xl"
        brand = "LawTracker · Admin"
    else:
        analysis_href = "analysis.html"
        sources_href = "sources.html"
        cross_href = "admin/analysis.html"
        cross_label = "Admin"
        sources_label = "Sources"
        container_class = "max-w-4xl"
        brand = "LawTracker"

    actions_html = ""
    if is_admin:
        generate_alert = (
            "In the live app, this would re-run the LLM analysis using "
            "only the articles you have not hidden. Static mockup — no "
            "action taken."
        )
        publish_alert = (
            "In the live app, this would publish your reviewed/edited "
            "analysis (and the visible articles) to the public site at "
            "lawmasolutions.com. You would see a confirmation step "
            "first. Static mockup — no action taken."
        )
        actions_html = f"""<div class="flex items-center gap-3">
      <button type="button"
        onclick="alert('{generate_alert}');"
        class="text-sm font-medium text-slate-700 hover:text-slate-900 border border-slate-300 hover:border-slate-500 rounded px-4 py-2">
        Generate new analysis
      </button>
      <button type="button"
        onclick="alert('{publish_alert}');"
        class="text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded px-4 py-2">
        Publish to site
      </button>
    </div>"""

    nav_html = f"""<nav class="flex items-center gap-6 text-sm">
      <a href="{analysis_href}" class="{nav_class("analysis")}">Analysis</a>
      <a href="{sources_href}" class="{nav_class("sources")}">{sources_label}</a>
      <a href="{cross_href}" class="text-slate-400 hover:text-slate-700 text-xs">{cross_label} &rarr;</a>
    </nav>"""

    header_inner = f"""<a href="{analysis_href}" class="text-xl font-semibold tracking-tight">{brand}</a>
    {nav_html}
    {actions_html}"""

    toast_html = ""
    script_html = ""
    if is_admin:
        toast_html = """<div id="toast" class="fixed bottom-6 right-6 z-50 hidden"></div>"""
        script_html = "<script>" + _ADMIN_JS + "</script>"

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
  <div class="{container_class} mx-auto px-6 py-4 flex items-center justify-between gap-6 flex-wrap">
    {header_inner}
  </div>
</header>
<main class="{container_class} mx-auto px-6 py-10">
  <h1 class="text-3xl font-bold tracking-tight text-slate-900 mb-8">{html.escape(title)}</h1>
  {body}
</main>
<footer class="{container_class} mx-auto px-6 py-8 mt-10 text-sm text-slate-500 border-t border-slate-200">
  Static mockup — most buttons are non-functional placeholders. Hide /
  Undo / Restore on the Articles page do work in this mockup
  (sessionStorage). Live functionality lands with item 21
  (FastAPI admin app). Production target: lawmasolutions.com.
</footer>
{toast_html}
{script_html}
</body>
</html>
"""


_ADMIN_JS = r"""
// Hide / Undo / Restore behavior for the admin Articles page.
// Storage key is per-browser-session (sessionStorage); the live app
// will replace this with server-side state that auto-purges after 60d.

const HIDDEN_KEY = 'lawtracker.hiddenArticles';
const TOAST_TIMEOUT_MS = 10000;

let toastTimer = null;

function getHidden() {
  try {
    return JSON.parse(sessionStorage.getItem(HIDDEN_KEY)) || [];
  } catch (_) {
    return [];
  }
}

function setHidden(arr) {
  sessionStorage.setItem(HIDDEN_KEY, JSON.stringify(arr));
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function findArticle(dedupKey) {
  return document.querySelector(
    'article.article-card[data-dedup-key="' +
      (window.CSS && CSS.escape ? CSS.escape(dedupKey) : dedupKey) +
      '"]'
  );
}

function getTitleFor(dedupKey) {
  const a = findArticle(dedupKey);
  if (!a) return '(untitled)';
  const h = a.querySelector('h3');
  return (h && h.textContent.trim()) || '(untitled)';
}

function hideArticle(dedupKey, options) {
  const opts = options || {};
  const article = findArticle(dedupKey);
  if (article) article.classList.add('hidden');

  const list = getHidden();
  if (!list.includes(dedupKey)) {
    list.push(dedupKey);
    setHidden(list);
  }

  addToDrawer(dedupKey);
  refreshCounts();

  if (opts.showToast !== false) {
    showToast(dedupKey);
  }
}

function restoreArticle(dedupKey) {
  const article = findArticle(dedupKey);
  if (article) article.classList.remove('hidden');

  setHidden(getHidden().filter(function (k) { return k !== dedupKey; }));
  removeFromDrawer(dedupKey);
  refreshCounts();
}

function addToDrawer(dedupKey) {
  const list = document.getElementById('drawer-list');
  if (!list) return;
  if (list.querySelector('[data-dedup-key="' +
      (window.CSS && CSS.escape ? CSS.escape(dedupKey) : dedupKey) +
      '"]')) {
    return;  // already there
  }
  const title = getTitleFor(dedupKey);
  const li = document.createElement('li');
  li.dataset.dedupKey = dedupKey;
  li.className = 'flex items-center justify-between gap-3 px-4 py-3';
  li.innerHTML =
    '<span class="text-sm text-slate-700 truncate">' + escapeHtml(title) + '</span>' +
    '<button type="button" class="restore-btn text-sm font-medium text-blue-700 hover:text-blue-900 whitespace-nowrap">Restore</button>';
  li.querySelector('.restore-btn').addEventListener('click', function () {
    restoreArticle(dedupKey);
  });
  list.appendChild(li);
}

function removeFromDrawer(dedupKey) {
  const list = document.getElementById('drawer-list');
  if (!list) return;
  const li = list.querySelector(
    '[data-dedup-key="' +
      (window.CSS && CSS.escape ? CSS.escape(dedupKey) : dedupKey) +
      '"]'
  );
  if (li) li.remove();
}

function refreshCounts() {
  const n = getHidden().length;
  const drawer = document.getElementById('hidden-drawer');
  const drawerCount = document.getElementById('drawer-count');
  const hiddenCount = document.getElementById('hidden-count');
  if (drawer) drawer.classList.toggle('hidden', n === 0);
  if (drawerCount) drawerCount.textContent = String(n);
  if (hiddenCount) hiddenCount.textContent = String(n);
}

function showToast(dedupKey) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  const title = getTitleFor(dedupKey);
  const truncated = title.length > 60 ? title.slice(0, 60) + '…' : title;
  toast.innerHTML =
    '<div class="bg-slate-900 text-white rounded-lg shadow-lg px-4 py-3 flex items-center gap-4 max-w-md">' +
    '<span class="text-sm">"<strong>' + escapeHtml(truncated) + '</strong>" hidden</span>' +
    '<button type="button" id="toast-undo" class="text-sm font-semibold text-amber-300 hover:text-amber-200">Undo</button>' +
    '</div>';
  toast.classList.remove('hidden');
  toast.querySelector('#toast-undo').addEventListener('click', function () {
    restoreArticle(dedupKey);
    hideToast();
  });
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, TOAST_TIMEOUT_MS);
}

function hideToast() {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.classList.add('hidden');
  if (toastTimer) {
    clearTimeout(toastTimer);
    toastTimer = null;
  }
}

document.addEventListener('DOMContentLoaded', function () {
  // Restore any session-hidden articles into the hidden state +
  // populate the drawer.
  for (const key of getHidden()) {
    const article = findArticle(key);
    if (article) {
      article.classList.add('hidden');
      addToDrawer(key);
    }
  }
  refreshCounts();

  // Wire up Hide buttons. Each button sits inside an article card
  // with a data-dedup-key attribute.
  document.querySelectorAll('.hide-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const article = btn.closest('article.article-card');
      if (!article) return;
      const key = article.dataset.dedupKey;
      if (!key) return;
      hideArticle(key);
    });
  });
});
"""
