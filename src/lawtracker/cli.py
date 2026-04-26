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
        help="Where to write events.xlsx, events.jsonl, summary.txt, analysis.md "
        "(default: data/scout/).",
    )
    scout_parser.add_argument(
        "--llm-mode",
        choices=("stub", "anthropic", "off"),
        default=None,
        help="LLM behavior. `stub` (default) returns canned placeholders for the "
        "analysis + LLM-extracted adapters (no API spend). `anthropic` calls the "
        "real Claude API (needs the anthropic SDK + ANTHROPIC_API_KEY env var). "
        "`off` skips the LLM entirely.",
    )

    args = parser.parse_args(argv)

    if args.command == "scout":
        if args.llm_mode is not None:
            os.environ["LAWTRACKER_LLM_MODE"] = args.llm_mode

        from lawtracker.scout import PILOT_ADAPTERS, run

        report = run(PILOT_ADAPTERS, args.output_dir, source_filter=args.source)
        print(
            f"\nScout complete: {report['events_collected']} events written to "
            f"{report['output_dir']}",
            flush=True,
        )
        return 0

    print("LawTracker — scaffolding in place. Implement tracking logic next.")
    return 0
