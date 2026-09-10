"""Integration: real files on disk, a real DataFrame, both loaders end to end."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from jobcheck import (
    build_context,
    build_report,
    validate,
    load_checks,
    load_overrides,
    render_report,
    root_cause,
    validate_row,
    write_report,
)
from jobcheck import registry as reg

pytestmark = pytest.mark.long

SPLIT_BY_TOPIC = [
    "examples/rules/split_by_topic/01_age_rules.yaml",
    "examples/rules/split_by_topic/02_email_rules.yaml",
]

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


def test_shipped_root_rule_file_drives_a_whole_frame(example_checks: None) -> None:
    df = validated(load_overrides("examples/rules/error_overrides.yaml"))
    assert codes(df) == [
        [],
        [],  # internal.test suppresses the email checks; the global rule keeps
             # AGE_NOT_INTEGER off despite the legacy enable listed before it
        ["AGE_NEGATIVE", "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"],
    ]


def test_split_files_produce_the_same_first_two_rules(example_checks: None) -> None:
    """Two files say what one file says -- rule for rule, not name for name.

    The names deliberately differ: the split files end "_by_topic" so the two
    sets can be loaded together, which a shared name makes impossible. What has
    to match is what the rules *do*.
    """

    from_dir = load_overrides(SPLIT_BY_TOPIC)
    from_file = load_overrides("examples/rules/error_overrides.yaml")
    assert [r.action for r in from_dir] == [r.action for r in from_file[:2]]
    assert [r.codes for r in from_dir] == [r.codes for r in from_file[:2]]
    assert [[(c.column, c.pattern) for c in r.criteria] for r in from_dir] == \
        [[(c.column, c.pattern) for c in r.criteria] for r in from_file[:2]]
    assert [r.name for r in from_dir] == [f"{r.name}_by_topic" for r in from_file[:2]]


def test_split_files_leave_the_legacy_enable_in_force(example_checks: None) -> None:
    df = validated(load_overrides(SPLIT_BY_TOPIC))
    assert codes(df)[1] == ["AGE_NOT_INTEGER"]


def test_file_order_decides_precedence_across_directories(example_checks: None) -> None:
    paths = [
        "examples/rules/split_by_topic/01_age_rules.yaml",
        "examples/rules/split_by_topic/02_email_rules.yaml",
        "examples/rules/from_another_directory/global_age_rule.yaml",
    ]
    assert codes(validated(load_overrides(paths)))[1] == []
    assert codes(validated(load_overrides(list(reversed(paths)))))[1] == [
        "AGE_NOT_INTEGER"
    ]


def test_errors_column_projects_to_text_for_export(example_checks: None, tmp_path: Path) -> None:
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


def test_a_written_report_reads_back_as_a_frame(example_checks: None, tmp_path: Path) -> None:
    outcomes = validate(DEMO, overrides=load_overrides("examples/rules/error_overrides.yaml"))
    report = build_report(outcomes, df=DEMO, key_column="id")
    path = tmp_path / "report.csv"
    write_report(report, str(path))
    written = pd.read_csv(path)
    assert list(written.columns) == list(report.columns)
    assert list(written["row"]) == [3, 3, 3]
    assert list(written["code"]) == ["AGE_NEGATIVE", "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"]
    # Lines keep evaluation order; the flag marks every failure at the shallowest
    # failing layer. Here that is DATES_OUT_OF_ORDER and EMAIL_MISSING_AT, both at
    # layer 1, with AGE_NEGATIVE at layer 2 below them.
    assert list(written["is_root_cause"]) == [False, True, True]


def test_a_table_report_renders_the_comments_a_reader_needs(example_checks: None) -> None:
    report = build_report(validate(DEMO), df=DEMO, key_column="id")
    text = render_report(report)
    assert "maximum=130" not in text
    assert "at_signs=0" in text
    assert "end_date=2024-03-01; start_date=2024-05-01" in text


def test_a_rule_file_written_at_runtime_is_picked_up(example_checks: None, tmp_path: Path) -> None:
    path = tmp_path / "runtime.yaml"
    path.write_text(
        '- name: "off_everywhere"\n  action: disable\n  codes: [AGE_NEGATIVE]\n  match: all\n',
        encoding="utf-8",
    )
    assert codes(validated(load_overrides(str(path))))[2] == [
        "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"
    ]


def test_loading_leaves_no_stray_files_behind(example_checks: None, tmp_path: Path) -> None:
    (tmp_path / "r.yaml").write_text(
        '- name: "r"\n  action: disable\n  codes: [AGE_NEGATIVE]\n  match: all\n', encoding="utf-8"
    )
    load_overrides([str(tmp_path / "r.yaml")])
    assert [p.name for p in tmp_path.iterdir()] == ["r.yaml"]


def test_a_check_file_written_at_runtime_is_loaded_by_path(fresh_registry: None,
                                                           tmp_path: Path) -> None:
    """The loading contract: a .py file anywhere on disk, named explicitly."""

    added = tmp_path / "check_added.py"
    added.write_text(
        "from jobcheck.registry import register_check\n\n\n"
        '@register_check(code="ADDED_AT_RUNTIME", message="added")\n'
        "def check(row):\n"
        "    return row['age'] != 99\n",
        encoding="utf-8",
    )
    load_checks([str(added)])
    results = validate_row(pd.Series({"age": 99}))

    assert [r.code for r in results] == ["ADDED_AT_RUNTIME"]
    assert reg.loaded_files() == [str(added.resolve())]


def test_source_file_of_a_shipped_check_exists_on_disk(example_checks: None) -> None:
    for check in reg.CHECKS:
        assert os.path.isfile(check.source_file), check.code


def test_a_written_report_round_trips_through_a_spreadsheet_reader(
    example_checks: None, tmp_path: Path
) -> None:
    """What a person actually does: write the CSV, open it, read the failures."""

    outcomes = validate(DEMO)
    report = build_report(outcomes, df=DEMO, key_column="id")
    path = tmp_path / "report.csv"
    write_report(report, str(path))

    reopened = pd.read_csv(path, dtype=str)
    assert list(reopened.columns) == list(report.columns)
    assert list(reopened["code"]) == list(report["code"])
    assert list(reopened["comments"]) == list(report["comments"])
    assert set(reopened["is_root_cause"]) <= {"True", "False"}


def test_the_table_and_csv_forms_carry_the_same_failures(example_checks: None) -> None:
    report = build_report(validate(DEMO), df=DEMO, key_column="id")
    text = render_report(report)
    csv = render_report(report, fmt="csv")
    for code in report["code"]:
        assert code in text and code in csv


def test_explaining_a_row_agrees_with_the_report(example_checks: None) -> None:
    """The two views are the same data: the report's first line for a row is the
    row's root cause, and the explanation says the same."""

    from jobcheck import explain_row, root_causes

    outcomes = validate(DEMO)
    report = build_report(outcomes, df=DEMO, key_column="id")
    for position, row_outcomes in enumerate(outcomes):
        causes = root_causes(row_outcomes)
        if not causes:
            continue
        lines = report[report["row"] == str(DEMO.iloc[position]["id"])]
        flagged = lines[lines["is_root_cause"]]
        # Every root cause is flagged, and nothing else is.
        assert sorted(flagged["code"]) == sorted(causes)
        assert root_cause(explain_row(DEMO.iloc[position])) is not None


def test_a_rule_file_changes_the_same_report(example_checks: None) -> None:
    """The knob a user has without editing a check, exercised against one frame."""

    unrestricted = build_report(validate(DEMO), df=DEMO, key_column="id")
    suppressed = build_report(
        validate(DEMO, overrides=load_overrides("examples/rules/error_overrides.yaml")),
        df=DEMO, key_column="id",
    )
    assert len(suppressed) <= len(unrestricted)
    assert "AGE_NOT_INTEGER" not in list(suppressed["code"])
