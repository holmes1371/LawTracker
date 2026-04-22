import argparse

from lawtracker import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lawtracker", description="Track law updates.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    print("LawTracker — scaffolding in place. Implement tracking logic next.")
    return 0
