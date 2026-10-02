"""Second demonstration entry point: one bundle file loads the check files.

`examples/main.py` names its four check files itself. This one names a single
path -- a bundle -- and the four arrive behind it. What it prints is the registry
with each check's source file, which shows the member files the bundle pulled in.

An argument names a different bundle, which is how the catalog drives it; with
none it loads the shipped `examples/checks/all_checks.py`.
"""

from __future__ import annotations

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from jobcheck import load_checks, registry_table  # noqa: E402
from main import table_text  # noqa: E402

#: The bundle loaded when the command line names none.
DEFAULT_BUNDLE = os.path.join(PROJECT_ROOT, "examples/checks/all_checks.py")


def build_parser() -> argparse.ArgumentParser:
    """One positional argument and nothing else.

    `argparse` for four lines rather than reading `sys.argv` directly, because
    the two things it buys are the two things a reader tries first: `--help`
    answers instead of being taken for a path, and a second argument is an
    error rather than silently dropped. `examples/main.py` is where the flags
    are; this entry point stays one path wide on purpose.
    """

    parser = argparse.ArgumentParser(
        description="Load one bundle -- a check file that loads check files -- "
                    "and print the registry, with the file each check came from.")
    parser.add_argument("bundle", nargs="?", default=DEFAULT_BUNDLE, metavar="PATH",
                        help="the bundle to load (default: the shipped all_checks.py).")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Load one bundle and show what came of it."""

    args = build_parser().parse_args(argv)

    # Exit 2 with one line, as the other entry points do for a file they cannot load.
    try:
        load_checks([args.bundle])
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    print(table_text(registry_table()))


if __name__ == "__main__":
    main()
