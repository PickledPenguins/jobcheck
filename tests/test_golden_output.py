"""Golden files: the exact text the library produces, compared byte for byte.

The catalog already pins what `examples/main.py` prints, but that output carries the
registry tables and the demo preamble around it, so a change to the report shows
up as a diff in a 9 KB file. These are tight: one view per file, produced through
the public API from the fixed inputs in `tests/golden_fixture.py` and written as
CSV, so a diff points straight at the value that moved.

Regenerate with `python3 scripts/regen_golden.py` after an intended change, then
read the diff.
"""

from __future__ import annotations

import pytest

from golden_fixture import CHECK_FILES, GOLDEN_DIR, ROOT, frame, read_golden, golden_views
from jobcheck import (
    build_report,
    validate,
    load_checks,
    load_rules,
)

pytestmark = pytest.mark.fast

GOLDEN_FILES = ["report.csv", "report_with_skipped.csv", "report_with_extra_columns.csv",
                "row_explanation.csv", "summary.csv"]


@pytest.mark.parametrize("name", GOLDEN_FILES)
def test_output_matches_its_golden_file(fresh_registry: None, name: str) -> None:
    """The golden files hold `\\n` line endings, so a `\\r\\n` from `csv.writer`
    creeping back into the output fails here."""
    assert golden_views()[name] == read_golden(name)


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

    text = read_golden("report_with_skipped.csv")
    for fragment in ("failed", "skipped", "disabled", "MISSING (1)", "MALFORMED (2)",
                     "INVALID (3)", "<no key>", "True", "False"):
        assert fragment in text, f"the golden frame no longer produces {fragment}"
    header = read_golden("report_with_extra_columns.csv").splitlines()[0]
    assert header.split(",")[:5] == [
        "id", "source_system", "record_type", "age", "code"
    ]


def test_the_golden_csv_parses_back_into_the_same_frame(fresh_registry: None) -> None:
    import pandas as pd

    load_checks([str(ROOT / path) for path in CHECK_FILES])
    rules = load_rules([str(ROOT / "examples/rules/error_rules.yaml")])
    df = frame()
    report = build_report(validate(df, rules=rules), df=df, key_column="id")

    report = report.reset_index()
    reparsed = pd.read_csv(pd.io.common.StringIO(read_golden("report.csv")), dtype=str)
    assert list(reparsed.columns) == list(report.columns)
    assert list(reparsed["code"]) == list(report["code"])
    assert list(reparsed["comments"].fillna("")) == list(report["comments"])
