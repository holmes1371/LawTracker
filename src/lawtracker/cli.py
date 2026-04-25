import argparse
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
        help="Where to write events.xlsx, events.jsonl, summary.txt (default: data/scout/).",
    )

    args = parser.parse_args(argv)

    if args.command == "scout":
        from lawtracker.scout import PILOT_ADAPTERS, _print_report, run

        report = run(PILOT_ADAPTERS, args.output_dir, source_filter=args.source)
        _print_report(report)
        return 0

    print("LawTracker — scaffolding in place. Implement tracking logic next.")
    return 0
