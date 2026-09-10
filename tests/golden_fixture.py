"""The fixed inputs behind the golden output files.

One frame, one rule file, one set of suites, chosen to exercise every column and
every outcome the report can show: a clean row, a value failure, a cascade from a
missing field, a rule-disabled test, and a row whose key is missing. Nothing here
varies between machines or runs -- no clock, no paths, no ordering that depends
on the filesystem -- which is what lets the output be compared byte for byte.

Imported by both ``tests/test_golden_output.py`` and ``scripts/regen_golden.py``,
so the test and the regeneration can never disagree about the input.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

SUITES = ["hard_tests", "soft_tests"]
RULE_FILE = "examples/rules/error_overrides.yaml"


def frame() -> pd.DataFrame:
    """The rows every golden file is produced from."""

    return pd.DataFrame(
        [
            {"id": 101, "age": 34, "email": "alice@example.com", "start_date": "2024-01-01",
             "end_date": "2024-02-01", "source_system": "MODERN", "record_type": "STREAM"},
            {"id": 102, "age": -5, "email": "bob@example", "start_date": "2024-05-01",
             "end_date": "2024-03-01", "source_system": "MODERN", "record_type": "BATCH"},
            {"id": 103, "age": 200, "email": "carol@nodomain", "start_date": "2024-01-01",
             "end_date": "2024-02-01", "source_system": "LEGACY_A", "record_type": "BATCH"},
            {"id": None, "age": None, "email": None, "start_date": None,
             "end_date": None, "source_system": "LEGACY_A", "record_type": "BATCH"},
        ]
    )


def render_all() -> dict[str, str]:
    """Every golden view, keyed by filename, produced through the public API.

    Clears and reloads the registry, since the golden files are defined by the
    example suites and nothing else; callers get an empty registry back.
    """

    import io
    from contextlib import redirect_stdout

    from pandas_row_validation import (
        build_report,
        clear_registry,
        collect_outcomes,
        load_overrides,
        load_suites,
        print_row_explanation,
        print_summary,
        render_report,
    )

    clear_registry()
    load_suites(SUITES, package="example_suites")
    overrides = load_overrides(str(ROOT / RULE_FILE))
    df = frame()
    outcomes = collect_outcomes(df, overrides=overrides)
    report = build_report(outcomes, df=df, key_column="id")
    with_skipped = build_report(outcomes, df=df, key_column="id", include_skipped=True)
    with_data = build_report(outcomes, df=df, key_column="id",
                             data_columns=["source_system", "record_type", "age"])

    explanation = io.StringIO()
    with redirect_stdout(explanation):
        print_row_explanation(outcomes[3])

    summary = io.StringIO()
    with redirect_stdout(summary):
        print_summary(outcomes)

    return {
        "report_table.txt": render_report(report) + "\n",
        "report.csv": render_report(report, fmt="csv"),
        "report_with_skipped.txt": render_report(with_skipped) + "\n",
        "report_with_data_columns.txt": render_report(with_data) + "\n",
        "row_explanation.txt": explanation.getvalue(),
        "summary.txt": summary.getvalue(),
    }


def read_golden(name: str) -> str:
    return (GOLDEN_DIR / name).read_text(encoding="utf-8")


def write_golden(name: str, text: str) -> None:
    (GOLDEN_DIR / name).write_text(text, encoding="utf-8", newline="")
