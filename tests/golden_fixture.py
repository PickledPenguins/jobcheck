"""The fixed inputs behind the golden output files.

One frame, one rule file, one set of check files, chosen to exercise every column and
every outcome the report can show: a clean row, a value failure, a cascade from a
missing field, a rule-disabled check, and a row whose key is missing. Nothing here
varies between machines or runs -- no clock, no paths, no ordering that depends
on the filesystem -- which is what lets the output be compared byte for byte.

Imported by both ``tests/test_golden_output.py`` and ``scripts/regen_golden.py``,
so the check and the regeneration can never disagree about the input.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

CHECK_FILES = [
    "examples/checks/check_row_shape.py",
    "examples/checks/check_age.py",
    "examples/checks/check_dates.py",
    "examples/checks/check_email.py",
]
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
    example check files and nothing else; callers get an empty registry back.
    """

    import io
    from contextlib import redirect_stdout

    from jobcheck import (
        build_report,
        clear_registry,
        validate,
        load_checks,
        load_overrides,
        print_row_explanation,
        print_summary,
        render_report,
    )

    clear_registry()
    load_checks([str(ROOT / path) for path in CHECK_FILES])
    overrides = load_overrides([str(ROOT / RULE_FILE)])
    df = frame()
    outcomes = validate(df, overrides=overrides)
    report = build_report(outcomes, df=df, key_column="id")
    with_skipped = build_report(outcomes, df=df, key_column="id", include="blocked")
    with_data = build_report(outcomes, df=df, key_column="id",
                             extra_columns=["source_system", "record_type", "age"])

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
        "report_with_extra_columns.txt": render_report(with_data) + "\n",
        "row_explanation.txt": explanation.getvalue(),
        "summary.txt": summary.getvalue(),
    }


def read_golden(name: str) -> str:
    return (GOLDEN_DIR / name).read_text(encoding="utf-8")


def write_golden(name: str, text: str) -> None:
    (GOLDEN_DIR / name).write_text(text, encoding="utf-8", newline="")
