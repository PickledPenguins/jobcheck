"""Integration: real files on disk, a real DataFrame, both loaders end to end."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from pandas_row_validation import (
    build_context,
    build_report,
    collect_outcomes,
    load_overrides,
    load_overrides_from_dir,
    load_overrides_from_files,
    load_suites,
    render_report,
    root_cause,
    validate_row,
    write_report,
)
from pandas_row_validation import registry as reg

pytestmark = pytest.mark.long

DEMO = pd.DataFrame(
    [
        {"id": 1, "age": 34, "email": "a@example.com", "start_date": "2024-01-01",
         "end_date": "2024-02-01", "source_system": "MODERN", "record_type": "STREAM"},
        {"id": 2, "age": 41.5, "email": "qa@internal.test", "start_date": "2024-01-01",
         "end_date": "2024-01-02", "source_system": "LEGACY_A", "record_type": "BATCH"},
        {"id": 3, "age": -1, "email": "nope", "start_date": "2024-05-01",
         "end_date": "2024-03-01", "source_system": "MODERN", "record_type": "STREAM"},
    ]
)


def codes(df: pd.DataFrame) -> list[list[str]]:
    return [[r.code for r in results] for results in df["errors"]]


def validated(overrides: list[reg.OverrideRule]) -> pd.DataFrame:
    df = DEMO.copy()
    df["errors"] = df.apply(
        lambda row: validate_row(row, ctx=build_context(row), overrides=overrides), axis=1
    )
    return df


def test_shipped_root_rule_file_drives_a_whole_frame(example_suites: None) -> None:
    df = validated(load_overrides("examples/rules/error_overrides.yaml"))
    assert codes(df) == [
        [],
        [],  # internal.test suppresses the email tests; the global rule keeps
             # AGE_NOT_INTEGER off despite the legacy enable listed before it
        ["AGE_NEGATIVE", "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"],
    ]


def test_directory_loading_produces_the_same_first_two_rules(example_suites: None) -> None:
    """One directory of files says what one file says -- rule for rule, not name for name.

    The names deliberately differ: the split files end "_by_topic" so the two
    sets can be loaded together, which a shared name makes impossible. What has
    to match is what the rules *do*.
    """

    from_dir = load_overrides_from_dir("examples/rules/split_by_topic")
    from_file = load_overrides("examples/rules/error_overrides.yaml")
    assert [r.action for r in from_dir] == [r.action for r in from_file[:2]]
    assert [r.codes for r in from_dir] == [r.codes for r in from_file[:2]]
    assert [[(c.column, c.pattern) for c in r.criteria] for r in from_dir] == \
        [[(c.column, c.pattern) for c in r.criteria] for r in from_file[:2]]
    assert [r.name for r in from_dir] == [f"{r.name}_by_topic" for r in from_file[:2]]


def test_directory_loading_leaves_the_legacy_enable_in_force(example_suites: None) -> None:
    df = validated(load_overrides_from_dir("examples/rules/split_by_topic"))
    assert codes(df)[1] == ["AGE_NOT_INTEGER"]


def test_file_order_decides_precedence_across_directories(example_suites: None) -> None:
    paths = [
        "examples/rules/split_by_topic/01_age_rules.yaml",
        "examples/rules/split_by_topic/02_email_rules.yaml",
        "examples/rules/from_another_directory/global_age_rule.yaml",
    ]
    assert codes(validated(load_overrides_from_files(paths)))[1] == []
    assert codes(validated(load_overrides_from_files(list(reversed(paths)))))[1] == [
        "AGE_NOT_INTEGER"
    ]


def test_errors_column_projects_to_text_for_export(example_suites: None, tmp_path: Path) -> None:
    df = validated([])
    df["error_codes"] = df["errors"].apply(lambda rs: ";".join(r.code for r in rs))
    df["root_cause"] = df["errors"].apply(lambda rs: root_cause(rs) or "")
    out = tmp_path / "out.csv"
    df.drop(columns=["errors"]).to_csv(out, index=False)
    written = pd.read_csv(out)
    assert list(written["error_codes"].fillna("")) == [
        "", "", "AGE_NEGATIVE;DATES_OUT_OF_ORDER;EMAIL_MISSING_AT"
    ]
    # The shallowest failure of that row: DATES_OUT_OF_ORDER sits at layer 1,
    # AGE_NEGATIVE at layer 2.
    assert list(written["root_cause"].fillna("")) == ["", "", "DATES_OUT_OF_ORDER"]


def test_a_written_report_reads_back_as_a_frame(example_suites: None, tmp_path: Path) -> None:
    outcomes = collect_outcomes(DEMO, overrides=load_overrides("examples/rules/error_overrides.yaml"))
    report = build_report(outcomes, df=DEMO, key_column="id")
    path = tmp_path / "report.csv"
    write_report(report, str(path))
    written = pd.read_csv(path)
    assert list(written.columns) == list(report.columns)
    assert list(written["row"]) == [3, 3, 3]
    assert list(written["code"]) == ["AGE_NEGATIVE", "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"]
    # Rows keep evaluation order; the flag marks the shallowest failure, which is
    # DATES_OUT_OF_ORDER at layer 1 rather than AGE_NEGATIVE at layer 2.
    assert list(written["is_root_cause"]) == [False, True, False]


def test_a_table_report_renders_the_comments_a_reader_needs(example_suites: None) -> None:
    report = build_report(collect_outcomes(DEMO), df=DEMO, key_column="id")
    text = render_report(report)
    assert "maximum=130" not in text
    assert "at_signs=0" in text
    assert "end_date=2024-03-01; start_date=2024-05-01" in text


def test_a_rule_file_written_at_runtime_is_picked_up(example_suites: None, tmp_path: Path) -> None:
    path = tmp_path / "runtime.yaml"
    path.write_text(
        '- name: "off_everywhere"\n  action: disable\n  codes: [AGE_NEGATIVE]\n  match: all\n',
        encoding="utf-8",
    )
    assert codes(validated(load_overrides(str(path))))[2] == [
        "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"
    ]


def test_loading_leaves_no_stray_files_behind(example_suites: None, tmp_path: Path) -> None:
    (tmp_path / "r.yaml").write_text(
        '- name: "r"\n  action: disable\n  codes: [AGE_NEGATIVE]\n  match: all\n', encoding="utf-8"
    )
    load_overrides_from_dir(str(tmp_path))
    assert [p.name for p in tmp_path.iterdir()] == ["r.yaml"]


def test_a_new_suite_added_at_runtime_is_discovered(fresh_registry: None, tmp_path: Path) -> None:
    """The discovery contract: a subpackage with an __init__.py and a test_*.py."""

    import sys

    package = tmp_path / "runtime_validation"
    suite = package / "extra_tests"
    suite.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (suite / "__init__.py").write_text("", encoding="utf-8")
    (suite / "test_added.py").write_text(
        "from pandas_row_validation.registry import register_test\n\n\n"
        '@register_test(code="ADDED_AT_RUNTIME", message="added")\n'
        "def check(row):\n"
        "    return row['age'] != 99\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        load_suites(["extra_tests"], package="runtime_validation")
        results = validate_row(pd.Series({"age": 99}))
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.startswith("runtime_validation")]:
            del sys.modules[name]

    assert [r.code for r in results] == ["ADDED_AT_RUNTIME"]
    assert next(t for t in reg.TESTS if t.code == "ADDED_AT_RUNTIME").suite == "extra_tests"


def test_source_file_of_a_shipped_check_exists_on_disk(example_suites: None) -> None:
    for test in reg.TESTS:
        assert os.path.isfile(test.source_file), test.code


def test_a_written_report_round_trips_through_a_spreadsheet_reader(
    example_suites: None, tmp_path: Path
) -> None:
    """What a person actually does: write the CSV, open it, read the failures."""

    outcomes = collect_outcomes(DEMO)
    report = build_report(outcomes, df=DEMO, key_column="id")
    path = tmp_path / "report.csv"
    write_report(report, str(path))

    reopened = pd.read_csv(path, dtype=str)
    assert list(reopened.columns) == list(report.columns)
    assert list(reopened["code"]) == list(report["code"])
    assert list(reopened["comments"]) == list(report["comments"])
    assert set(reopened["is_root_cause"]) <= {"True", "False"}


def test_the_table_and_csv_forms_carry_the_same_failures(example_suites: None) -> None:
    report = build_report(collect_outcomes(DEMO), df=DEMO, key_column="id")
    text = render_report(report)
    csv = render_report(report, fmt="csv")
    for code in report["code"]:
        assert code in text and code in csv


def test_explaining_a_row_agrees_with_the_report(example_suites: None) -> None:
    """The two views are the same data: the report's first line for a row is the
    row's root cause, and the explanation says the same."""

    from pandas_row_validation import explain_row, root_cause

    outcomes = collect_outcomes(DEMO)
    report = build_report(outcomes, df=DEMO, key_column="id")
    for position, row_outcomes in enumerate(outcomes):
        cause = root_cause(row_outcomes)
        if cause is None:
            continue
        lines = report[report["row"] == str(DEMO.iloc[position]["id"])]
        flagged = lines[lines["is_root_cause"]]
        assert list(flagged["code"]) == [cause]
        assert root_cause(explain_row(DEMO.iloc[position])) is not None


def test_a_rule_file_and_a_suite_change_the_same_report(example_suites: None) -> None:
    """The two knobs a user has, exercised against one frame."""

    unrestricted = build_report(collect_outcomes(DEMO), df=DEMO, key_column="id")
    suppressed = build_report(
        collect_outcomes(DEMO, overrides=load_overrides("examples/rules/error_overrides.yaml")),
        df=DEMO, key_column="id",
    )
    assert len(suppressed) <= len(unrestricted)
    assert "AGE_NOT_INTEGER" not in list(suppressed["code"])
