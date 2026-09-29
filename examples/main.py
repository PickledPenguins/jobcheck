"""Demonstration entry point: load checks, validate a frame, print a report.

The library does the work; this script only chooses what to load and where the
output goes. It is also what the end-to-end checks drive.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

#: The clone this script lives in. Its own files are named relative to it, so a
#: run does not depend on the directory it was started from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import pandas as pd

from jobcheck import (
    build_report,
    warn_blocking_rules,
    warn_missing_rule_columns,
    warn_shadowed_rules,
    load_checks,
    load_rules,
    registry_table,
    root_causes,
    row_explanation,
    rules_table,
    summarize_outcomes,
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

#: The rule files a run applies when --rules names none. Absolute, because it
#: is this script's own file rather than something the user typed: a path on
#: the command line still means what it means from where the user is standing.
DEFAULT_RULES = [os.path.join(PROJECT_ROOT, "examples/rules/error_rules.yaml")]

#: The column that identifies a row in the report. Every demo data file has it;
#: a --data file without it is refused before anything is validated.
KEY_COLUMN = "id"


def build_parser() -> argparse.ArgumentParser:
    """The command line, built separately so the documentation check can read it.

    Every option here has a section in ``docs/cli.md``, and a check compares the
    two lists both ways: an undocumented flag and a documented flag that no
    longer exists are both failures.
    """

    parser = argparse.ArgumentParser(
        description="Validate rows of a DataFrame with pluggable checks.")
    parser.add_argument("--data", metavar="PATH",
                        help="CSV file to validate (default: the built-in demo frame).")
    # nargs="*" rather than "+": `--rules` with nothing after it means no
    # rules at all, which is the baseline every rule file is a deviation
    # from and the first thing somebody adopting this wants to see.
    parser.add_argument("--rules", nargs="*", default=DEFAULT_RULES, metavar="PATH",
                        help="Rule YAML files, in precedence order (last match wins). "
                             "Pass --rules with no paths to apply none.")
    parser.add_argument("--report", choices=("table", "csv"), default="table",
                        help="Report format (default table).")
    parser.add_argument("--explain", type=int, metavar="ROW",
                        help="Print what every check did on one row, by position, and exit.")
    parser.add_argument("--summary", action="store_true",
                        help="Print per-check counts, including the rows each check "
                             "was the root cause of.")
    parser.add_argument("--rules-table", action="store_true",
                        help="Print one row per loaded rule before the registry.")
    parser.add_argument("--write", metavar="PATH",
                        help="Also write the report to this file, in the --report format.")
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
    # UnicodeDecodeError: a file that is not UTF-8 is as unreadable as one that is not CSV.
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError,
            pd.errors.ParserError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


def table_text(table: pd.DataFrame, fmt: str = "table") -> str:
    """*table* as this script prints it: pandas' own layout under the table's title,
    or plain CSV.

    `to_string`, never `str(table)`: printing a frame directly shows only the first
    and last rows of a long one, which would hide most of a report's failures.
    """

    if fmt == "csv":
        return table.to_csv(index=False)
    if fmt == "table":
        return f"== {table.attrs['title']} ==\n{table.to_string(index=False, na_rep='')}"
    # Reached from a run file's `format:`; argparse already limits --report.
    raise ValueError(f"fmt must be 'table' or 'csv', got {fmt!r}.")


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

    # Before any work: validating a large frame and only then finding that the
    # directory does not exist wastes the run and loses the report. The write
    # itself is still guarded below -- a directory can go away, or be read-only
    # in a way this does not see.
    if args.write is not None:
        directory = os.path.dirname(os.path.abspath(args.write))
        if not os.path.isdir(directory):
            print(f"error: cannot write {args.write}: no directory {directory}",
                  file=sys.stderr)
            raise SystemExit(2)

    load_checks(CHECK_FILES, base_dir=PROJECT_ROOT)
    rules = load_rules(args.rules)
    print(f"Loaded {len(rules)} rule(s) from {len(args.rules)} file(s)\n")

    df = load_frame(args.data)
    # Before validating, for the reason --write is checked early: the report labels
    # every row by this column. --explain names a row by position and needs none.
    if args.explain is None and KEY_COLUMN not in df.columns:
        print(f"error: {args.data} has no {KEY_COLUMN!r} column, which labels each row "
              f"of the report (columns: {', '.join(str(name) for name in df.columns)})",
              file=sys.stderr)
        raise SystemExit(2)
    for warning in warn_missing_rule_columns(df, rules):
        print(f"warning: {warning}", file=sys.stderr)

    outcomes = validate(df, rules=rules)

    if args.explain is not None:
        if not 0 <= args.explain < len(df):
            print(f"error: --explain {args.explain} is outside the frame's {len(df)} row(s)",
                  file=sys.stderr)
            raise SystemExit(2)
        print(table_text(row_explanation(outcomes[args.explain])))
        print("root cause:", ", ".join(root_causes(outcomes[args.explain])) or "none")
        return

    if args.rules_table:
        # One row per rule, where the registry table below is one row per code:
        # a rule touching eight codes is one line here and eight there, which is
        # the view that answers "what did this file actually say".
        print(table_text(rules_table(rules)))
        # Beside the rules themselves, because "this rule can never apply" and
        # "this rule silences checks it does not name" are facts about the file
        # rather than about a row. The shipped rule file has a shadowed rule on
        # purpose: it is the precedence demonstration.
        for warning in warn_shadowed_rules(rules) + warn_blocking_rules(rules):
            print(f"warning: {warning}")
        print()

    # could_be_overridden_by is the only use registry_table makes of the rules:
    # without it the argument is inert and the demo never shows which rule
    # touches which code.
    print(table_text(registry_table(rules=rules, add_columns=["could_be_overridden_by"])))

    print()
    report = build_report(outcomes, df=df, key_column=KEY_COLUMN)
    print(table_text(report, fmt=args.report))

    if args.write is not None:
        # The same frame the report above was printed from, so the file and the
        # terminal cannot disagree.
        try:
            Path(args.write).write_text(table_text(report, fmt=args.report),
                                        encoding="utf-8", newline="")
        except OSError as exc:
            print(f"error: cannot write {args.write}: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        print(f"\nWrote {len(report)} report row(s) to {args.write}")

    if args.summary:
        print()
        print(table_text(summarize_outcomes(outcomes)))


if __name__ == "__main__":
    main()
