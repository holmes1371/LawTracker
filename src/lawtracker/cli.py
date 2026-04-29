import argparse
import os
from pathlib import Path

from lawtracker import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lawtracker", description="Track law updates.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    scout_parser = subparsers.add_parser(
        "scout", help="Run the data scout: dump every adapter's output to data/scout/."
    )
    scout_parser.add_argument("--source", help="Only run the named adapter (source_id)")
    scout_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/scout"),
        help="Where to write events.xlsx, events.jsonl, summary.txt "
        "(default: data/scout/). Run `lawtracker analyze` separately to produce "
        "analysis.md from these outputs.",
    )
    scout_parser.add_argument(
        "--llm-mode",
        choices=("stub", "anthropic", "off"),
        default=None,
        help="LLM behavior for adapter-side calls (per-event summary, "
        "LLM-extracted adapters). `stub` (default) returns canned placeholders. "
        "`anthropic` calls the real Claude API (needs the anthropic SDK + "
        "ANTHROPIC_API_KEY env var). `off` skips the LLM entirely.",
    )

    render_parser = subparsers.add_parser(
        "render",
        help="Render static HTML mockups (analysis.html, sources.html) from a scout run.",
        description=(
            "Generates two self-contained static HTML pages from "
            "events.jsonl + analysis.md: analysis.html (country-by-country, "
            "blog-style, US first then alpha) and sources.html (events grouped "
            "by country with US first then alpha, reverse-chronological inside "
            "each country). Tailwind via CDN — no build step. Open by "
            "double-click in Explorer."
        ),
    )
    render_parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/scout"),
        help="Directory containing events.jsonl and analysis.md (default: data/scout/).",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Generate analysis.md from a previous scout run's events.jsonl.",
        description=(
            "Two-step pipeline: scout collects raw events; analyze sends them to "
            "the LLM for narrative analysis. Re-run after editing the prompt to "
            "iterate without re-polling adapters."
        ),
    )
    analyze_parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/scout"),
        help="Directory containing events.jsonl from a prior scout (default: "
        "data/scout/).",
    )
    analyze_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the analysis markdown (default: <input-dir>/analysis.md).",
    )
    analyze_parser.add_argument(
        "--llm-mode",
        choices=("stub", "anthropic", "off"),
        default=None,
        help="LLM behavior. `stub` (default) returns the canned analysis stub "
        "(no API spend). `anthropic` calls Claude. `off` writes the analysis.md "
        "with empty narrative (deterministic stats only).",
    )

    args = parser.parse_args(argv)

    if args.command == "scout":
        if args.llm_mode is not None:
            os.environ["LAWTRACKER_LLM_MODE"] = args.llm_mode

        from lawtracker.scout import PILOT_ADAPTERS, run

        try:
            report = run(PILOT_ADAPTERS, args.output_dir, source_filter=args.source)
        except RuntimeError as exc:
            print(f"Error: {exc}", flush=True)
            return 1
        print(
            f"\nScout complete: {report['events_collected']} events written to "
            f"{report['output_dir']}. Run `lawtracker analyze` to produce "
            f"analysis.md.",
            flush=True,
        )
        return 0

    if args.command == "analyze":
        if args.llm_mode is not None:
            os.environ["LAWTRACKER_LLM_MODE"] = args.llm_mode

        from lawtracker.analysis import analyze_from_jsonl

        jsonl_path = args.input_dir / "events.jsonl"
        if not jsonl_path.exists():
            print(
                f"No events.jsonl at {jsonl_path}. Run `lawtracker scout` first.",
                flush=True,
            )
            return 1
        output_path = args.output if args.output is not None else args.input_dir / "analysis.md"
        try:
            n = analyze_from_jsonl(jsonl_path, output_path)
        except RuntimeError as exc:
            print(f"Error: {exc}", flush=True)
            return 1
        print(f"Analyzed {n} events; wrote {output_path}.", flush=True)
        return 0

    if args.command == "render":
        from lawtracker.preview import render_pages

        try:
            paths = render_pages(args.input_dir)
        except RuntimeError as exc:
            print(f"Error: {exc}", flush=True)
            return 1
        for p in paths:
            print(f"Wrote {p}", flush=True)
        return 0

    print("LawTracker — scaffolding in place. Implement tracking logic next.")
    return 0
