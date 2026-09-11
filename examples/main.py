"""Demonstration entry point: load checks, validate a frame, print a report.

The library does the work; this script only chooses what to load and where the
output goes. It is also what the end-to-end checks drive.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import pandas as pd

from jobcheck import (
    build_report,
    check_override_columns,
    load_checks,
    load_overrides,
    print_registry,
    print_report,
    print_row_explanation,
    print_summary,
    validate,
)

#: The check files this entry point runs. Named one by one, rather than
#: discovered, so a second entry point in the same tree can run a different set.
CHECK_FILES = [
    "examples/checks/check_row_shape.py",
    "examples/checks/check_age.py",
    "examples/checks/check_dates.py",
    "examples/checks/check_email.py",
]

DEFAULT_RULES = ["examples/rules/error_overrides.yaml"]

#: The column that identifies a row in the report. Every demo data file has it.
KEY_COLUMN = "id"


def build_parser() -> argparse.ArgumentParser:
    """The command line, built separately so the documentation check can read it.

    Every option here has a section in ``docs/cli.md``, and a check compares the
    two lists both ways: an undocumented flag and a documented flag that no
    longer exists are both failures.
    """

    parser = argparse.ArgumentParser(description="Validate rows of a DataFrame with pluggable checks.")
    parser.add_argument("--data", metavar="PATH",
                        help="CSV file to validate (default: the built-in demo frame).")
    # nargs="*" rather than "+": `--rules` with nothing after it means no
    # overrides at all, which is the baseline every rule file is a deviation
    # from and the first thing somebody adopting this wants to see.
    parser.add_argument("--rules", nargs="*", default=DEFAULT_RULES, metavar="PATH",
                        help="Override YAML files, in precedence order (last match wins). "
                             "Pass --rules with no paths to apply none.")
    parser.add_argument("--report", choices=("table", "csv"), default="table",
                        help="Report format (default table).")
    parser.add_argument("--explain", type=int, metavar="ROW",
                        help="Print what every check did on one row, by position, and exit.")
    parser.add_argument("--summary", action="store_true",
                        help="Print per-check counts and the root cause of each failing row.")
    return parser


def load_frame(path: str | None) -> pd.DataFrame:
    """The frame to validate: a CSV if one was named, else the demo frame.

    Every column is read as text, because a check that judges whether a value is
    a number has to see what the file actually said -- pandas inferring ``age``
    to float would silently repair ``"41.5"`` and hide the rows this tool exists
    to find. Empty cells stay empty rather than becoming ``NaN`` strings.
    """

    if path is None:
        return demo_frame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=True, na_values=[""])
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


def demo_frame() -> pd.DataFrame:
    """A small DataFrame exercising every example check."""

    return pd.DataFrame(
        [
            {"id": 1, "age": 34, "email": "a@example.com", "start_date": "2024-01-01",
             "end_date": "2024-02-01", "source_system": "MODERN", "record_type": "STREAM"},
            {"id": 2, "age": -5, "email": "broken-email", "start_date": "2024-05-01",
             "end_date": "2024-03-01", "source_system": "MODERN", "record_type": "STREAM"},
            {"id": 3, "age": 200, "email": "user@nodotdomain", "start_date": "2024-01-01",
             "end_date": "2024-01-02", "source_system": "MODERN", "record_type": "STREAM"},
            {"id": 4, "age": 41.5, "email": "qa@internal.test", "start_date": "2024-01-01",
             "end_date": "2024-01-02", "source_system": "LEGACY_A", "record_type": "BATCH"},
            {"id": 5, "age": None, "email": None, "start_date": None,
             "end_date": None, "source_system": None, "record_type": None},
            {"id": None, "age": None, "email": None, "start_date": None,
             "end_date": None, "source_system": None, "record_type": None},
        ]
    )


def main(argv: list[str] | None = None) -> None:
    """Run the whole flow: load, report on the registry, validate, report on the rows."""

    args = build_parser().parse_args(argv)

    load_checks(CHECK_FILES)
    overrides = load_overrides(args.rules)
    print(f"Loaded {len(overrides)} override rule(s) from {len(args.rules)} file(s)\n")

    df = load_frame(args.data)
    for warning in check_override_columns(df, overrides):
        print(f"warning: {warning}", file=sys.stderr)

    outcomes = validate(df, overrides=overrides)

    if args.explain is not None:
        if not 0 <= args.explain < len(df):
            print(f"error: --explain {args.explain} is outside the frame's {len(df)} row(s)",
                  file=sys.stderr)
            raise SystemExit(2)
        print(f"== Row {args.explain} ==")
        print_row_explanation(outcomes[args.explain])
        return

    print("== Registry ==")
    # could_be_overridden_by is the only use print_registry makes of the rules:
    # without it the argument is inert and the demo never shows which rule
    # touches which code.
    print_registry(overrides=overrides, extra_columns=["could_be_overridden_by"])

    print("\n== Failures ==")
    print_report(build_report(outcomes, df=df, key_column=KEY_COLUMN), fmt=args.report)

    if args.summary:
        print("\n== Summary ==")
        print_summary(outcomes)


if __name__ == "__main__":
    main()
