"""Golden files: the exact text the library produces, compared byte for byte.

The catalog already pins what `examples/main.py` prints, but that output carries the
registry tables and the demo preamble around it, so a change to the report shows
up as a diff in a 9 KB file. These are tight: one view per file, produced through
the public API from the fixed inputs in `tests/golden_fixture.py`, so a diff
points straight at what moved.

Regenerate with `python3 scripts/regen_golden.py` after an intended change, then
read the diff.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from golden_fixture import CHECK_FILES, GOLDEN_DIR, ROOT, frame, read_golden, render_all
from jobcheck import (
    build_report,
    validate,
    load_checks,
    load_overrides,
    write_report,
)

pytestmark = pytest.mark.fast

GOLDEN_FILES = ["report_table.txt", "report.csv", "report_with_skipped.txt",
                "report_with_data_columns.txt", "row_explanation.txt", "summary.txt"]


@pytest.mark.parametrize("name", GOLDEN_FILES)
def test_output_matches_its_golden_file(fresh_registry: None, name: str) -> None:
    assert render_all()[name] == read_golden(name)


def test_every_golden_file_is_accounted_for() -> None:
    """A golden nobody compares is a file that rots quietly. README.md is the
    directory's own documentation, not an output."""

    on_disk = sorted(
        path.name for path in GOLDEN_DIR.iterdir()
        if path.is_file() and path.name != "README.md"
    )
    assert on_disk == sorted(GOLDEN_FILES)


def test_the_golden_report_shows_every_outcome_the_report_can_carry(
    fresh_registry: None,
) -> None:
    """The fixture earns its place only if it exercises the whole shape."""

    text = read_golden("report_with_skipped.txt")
    for fragment in ("failed", "skipped", "disabled", "MISSING (1)", "MALFORMED (2)",
                     "INVALID (3)", "<no key>", "True", "False"):
        assert fragment in text, f"the golden frame no longer produces {fragment}"


def test_the_data_columns_golden_shows_them_next_to_the_row_key() -> None:
    header = read_golden("report_with_data_columns.txt").splitlines()[0]
    assert [part.strip() for part in header.split(" | ")[:5]] == [
        "row", "source_system", "record_type", "age", "code"
    ]


def test_a_written_file_is_byte_for_byte_the_golden_csv(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Pins the file on disk, not just the string: encoding, line endings, and the
    trailing newline all come from write_report rather than the caller."""

    load_checks([str(ROOT / path) for path in CHECK_FILES])
    overrides = load_overrides("examples/rules/error_overrides.yaml")
    df = frame()
    report = build_report(validate(df, overrides=overrides), df=df, key_column="id")

    path = tmp_path / "report.csv"
    write_report(report, str(path))
    written = path.read_bytes()

    assert written.decode("utf-8") == read_golden("report.csv")
    assert b"\r\n" not in written, "csv.writer's \\r\\n must not survive write_report"


def test_the_golden_csv_parses_back_into_the_same_frame(fresh_registry: None) -> None:
    import pandas as pd

    load_checks([str(ROOT / path) for path in CHECK_FILES])
    overrides = load_overrides("examples/rules/error_overrides.yaml")
    df = frame()
    report = build_report(validate(df, overrides=overrides), df=df, key_column="id")

    reparsed = pd.read_csv(pd.io.common.StringIO(read_golden("report.csv")), dtype=str)
    assert list(reparsed.columns) == list(report.columns)
    assert list(reparsed["code"]) == list(report["code"])
    assert list(reparsed["comments"].fillna("")) == list(report["comments"])
