"""Demonstration entry point: load tests, validate a frame, print a report.

The library does the work; this script only chooses what to load and where the
output goes, so the flags are thin pass-throughs to
:mod:`pandas_row_validation.report`. It is also what the end-to-end tests drive.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import sys

import pandas as pd

from pandas_row_validation import (
    OverrideRule,
    build_report,
    check_rule_columns,
    collect_outcomes,
    load_overrides_from_files,
    load_suites,
    loaded_suites,
    print_report,
    print_override_rules,
    print_registry,
    print_registry_with_overrides,
    print_row_explanation,
    print_summary,
    write_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the CLI.

    ``-e`` and ``-o`` are both ``nargs="+"`` *and* ``action="append"``, so they
    accept several values per occurrence and several occurrences, which argparse
    then hands back as a list of lists; the flattening below preserves the order
    the user typed, so ``-e a b -o x.yaml -e c`` yields ``["a", "b", "c"]``.
    """

    parser = argparse.ArgumentParser(description="Validate rows of a DataFrame with pluggable tests.")
    parser.add_argument("-e", "--suites", nargs="+", action="append", default=None,
                        help="Suites of tests to load (repeatable, several values allowed).")
    parser.add_argument("-o", "--overrides", nargs="+", action="append", default=None,
                        help="Override YAML files (repeatable, need not share a directory).")
    parser.add_argument("--report", choices=("table", "csv"), default="table",
                        help="Report format (default table).")
    parser.add_argument("--report-file", metavar="PATH",
                        help="Write the report here instead of printing it.")
    parser.add_argument("--data-columns", nargs="+", action="append", default=None,
                        metavar="COLUMN",
                        help="Columns from the frame to show next to the row key (repeatable).")
    parser.add_argument("--include-skipped", action="store_true",
                        help="Include the tests a failure blocked, each naming its prerequisite.")
    parser.add_argument("--explain", type=int, metavar="ROW",
                        help="Print what every test did on one row, by position, and exit.")
    parser.add_argument("--summary", action="store_true",
                        help="Print per-test counts and the root cause of each failing row.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="-v adds cross-reference columns, -vv adds source files and the by-rule table.")
    args = parser.parse_args(argv)

    suite_groups: list[list[str]] | None = args.suites
    override_groups: list[list[str]] | None = args.overrides
    args.suites = [s for group in (suite_groups or [["hard_tests", "soft_tests"]]) for s in group]
    args.overrides = [p for group in (override_groups or [["examples/rules/error_overrides.yaml"]]) for p in group]
    data_groups: list[list[str]] | None = args.data_columns
    args.data_columns = [c for group in (data_groups or []) for c in group]
    return args


def demo_frame() -> pd.DataFrame:
    """A small DataFrame exercising every example test."""

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

    args = parse_args(argv)

    load_suites(args.suites, package="example_suites")
    print(f"Loaded suites: {sorted(loaded_suites())}\n")

    overrides: list[OverrideRule] = load_overrides_from_files(args.overrides)
    print(f"Loaded {len(overrides)} override rule(s) from {len(args.overrides)} file(s)\n")

    df = demo_frame()
    for warning in check_rule_columns(df, overrides):
        print(f"warning: {warning}", file=sys.stderr)

    outcomes = collect_outcomes(df, overrides=overrides)

    if args.explain is not None:
        if not 0 <= args.explain < len(df):
            print(f"error: --explain {args.explain} is outside the frame's {len(df)} row(s)",
                  file=sys.stderr)
            raise SystemExit(2)
        print(f"== Row {args.explain} ==")
        print_row_explanation(outcomes[args.explain])
        return

    print("== Registry ==")
    print_registry(overrides=overrides, debug=args.verbose)

    print("\n== Registry vs overrides ==")
    print_registry_with_overrides(overrides, debug=args.verbose)

    if args.verbose >= 2:
        print("\n== Override rules (by rule) ==")
        print_override_rules(overrides, debug=args.verbose)

    report = build_report(outcomes, df=df, key_column="id", data_columns=args.data_columns,
                          include_skipped=args.include_skipped)
    if args.report_file:
        write_report(report, args.report_file, fmt=args.report)
        print(f"\nwrote {args.report_file}")
    else:
        print("\n== Failures ==")
        print_report(report, fmt=args.report)

    if args.summary:
        print("\n== Summary ==")
        print_summary(outcomes)


if __name__ == "__main__":
    main()
