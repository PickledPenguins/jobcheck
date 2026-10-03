"""Integration: real files on disk, a real DataFrame, both loaders end to end."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from conftest import failures, first_cause

from jobcheck import (
    RowContext,
    build_report,
    validate,
    load_checks,
    load_rules,
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


def validated(rules: list[reg.Rule]) -> pd.DataFrame:
    df = DEMO.copy()
    df["errors"] = df.apply(
        lambda row: failures(row, context=RowContext(), rules=rules), axis=1
    )
    return df


def test_shipped_root_rule_file_drives_a_whole_frame(example_checks: None) -> None:
    df = validated(load_rules(["examples/rules/error_rules.yaml"]))
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

    from_dir = load_rules(SPLIT_BY_TOPIC)
    from_file = load_rules(["examples/rules/error_rules.yaml"])
    assert [r.action for r in from_dir] == [r.action for r in from_file[:2]]
    assert [r.codes for r in from_dir] == [r.codes for r in from_file[:2]]
    assert [[(c.column, c.pattern) for c in r.criteria] for r in from_dir] == \
        [[(c.column, c.pattern) for c in r.criteria] for r in from_file[:2]]
    assert [r.name for r in from_dir] == [f"{r.name}_by_topic" for r in from_file[:2]]


def test_split_files_leave_the_legacy_enable_in_force(example_checks: None) -> None:
    df = validated(load_rules(SPLIT_BY_TOPIC))
    assert codes(df)[1] == ["AGE_NOT_INTEGER"]


def test_file_order_decides_precedence_across_directories(example_checks: None) -> None:
    paths = [
        "examples/rules/split_by_topic/01_age_rules.yaml",
        "examples/rules/split_by_topic/02_email_rules.yaml",
        "examples/rules/from_another_directory/global_age_rule.yaml",
    ]
    assert codes(validated(load_rules(paths)))[1] == []
    assert codes(validated(load_rules(list(reversed(paths)))))[1] == [
        "AGE_NOT_INTEGER"
    ]


def test_errors_column_projects_to_text_for_export(example_checks: None, tmp_path: Path) -> None:
    df = validated([])
    df["error_codes"] = df["errors"].apply(lambda rs: ";".join(r.code for r in rs))
    df["root_cause"] = df["errors"].apply(lambda rs: first_cause(rs) or "")
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
    outcomes = validate(DEMO, rules=load_rules(["examples/rules/error_rules.yaml"]))
    report = build_report(outcomes, df=DEMO, key_column="id")
    path = tmp_path / "report.csv"
    path.write_text(report.to_csv(), encoding="utf-8")
    written = pd.read_csv(path)
    assert list(written.columns) == list(report.reset_index().columns)
    assert list(written["id"]) == [3, 3, 3]
    assert list(written["code"]) == ["AGE_NEGATIVE", "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"]
    # Lines keep evaluation order; the flag marks every failure at the shallowest
    # failing layer. Here that is DATES_OUT_OF_ORDER and EMAIL_MISSING_AT, both at
    # layer 1, with AGE_NEGATIVE at layer 2 below them.
    assert list(written["is_root_cause"]) == [False, True, True]


def test_a_table_report_renders_the_comments_a_reader_needs(example_checks: None) -> None:
    report = build_report(validate(DEMO), df=DEMO, key_column="id")
    text = "\n".join(report["comments"])
    assert "maximum=130" not in text
    assert "at_signs=0" in text
    assert "start_date=2024-05-01; end_date=2024-03-01" in text


def test_a_rule_file_written_at_runtime_is_picked_up(example_checks: None, tmp_path: Path) -> None:
    path = tmp_path / "runtime.yaml"
    path.write_text(
        '- name: "off_everywhere"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [AGE_NEGATIVE]\n  match: all\n',
        encoding="utf-8",
    )
    assert codes(validated(load_rules([str(path)])))[2] == [
        "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT"
    ]


def test_loading_leaves_no_stray_files_behind(example_checks: None, tmp_path: Path) -> None:
    (tmp_path / "r.yaml").write_text(
        '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [AGE_NEGATIVE]\n  match: all\n', encoding="utf-8"
    )
    load_rules([str(tmp_path / "r.yaml")])
    assert [p.name for p in tmp_path.iterdir()] == ["r.yaml"]


def test_a_check_file_written_at_runtime_is_loaded_by_path(fresh_registry: None,
                                                           tmp_path: Path) -> None:
    """The loading contract: a .py file anywhere on disk, named explicitly."""

    added = tmp_path / "check_added.py"
    added.write_text(
        "from jobcheck.registry import register_check\n"
        "from jobcheck.results import Verdict\n\n\n"
        '@register_check(code="ADDED_AT_RUNTIME", message="added")\n'
        "def check(row):\n"
        "    return Verdict(row['age'] != 99)\n",
        encoding="utf-8",
    )
    load_checks([str(added)])
    results = failures(pd.Series({"age": 99}))

    assert [r.code for r in results] == ["ADDED_AT_RUNTIME"]
    assert reg._LOADED_FILES == [str(added.resolve())]


def test_source_file_of_a_shipped_check_exists_on_disk(example_checks: None) -> None:
    for check in reg._CHECKS:
        assert os.path.isfile(check.source_file), check.code


def test_a_written_report_round_trips_through_a_spreadsheet_reader(
    example_checks: None, tmp_path: Path
) -> None:
    """What a person actually does: write the CSV, open it, read the failures."""

    outcomes = validate(DEMO)
    report = build_report(outcomes, df=DEMO, key_column="id")
    path = tmp_path / "report.csv"
    path.write_text(report.to_csv(), encoding="utf-8")
    report = report.reset_index()

    reopened = pd.read_csv(path, dtype=str)
    assert list(reopened.columns) == list(report.columns)
    assert list(reopened["code"]) == list(report["code"])
    assert list(reopened["comments"]) == list(report["comments"])
    assert set(reopened["is_root_cause"]) <= {"True", "False"}


def test_the_root_cause_views_agree(example_checks: None) -> None:
    """The views are the same data: the report's `is_root_cause` flags, its
    `root_causes` level and a row's explanation name the same checks."""

    from jobcheck import explain_row

    outcomes = validate(DEMO)
    report = build_report(outcomes, df=DEMO)
    roots = build_report(outcomes, df=DEMO, include="root_causes")
    assert list(roots.index) == list(report[report["is_root_cause"]].index)
    for position, row_outcomes in enumerate(outcomes):
        causes = [code for row, code in roots.index if row == str(DEMO.index[position])]
        explanation = explain_row(outcomes, position)
        assert list(explanation.loc[explanation["is_root_cause"], "code"]) == causes
        assert (first_cause(row_outcomes) is None) == (causes == [])


def test_a_row_explanation_is_that_rows_lines_of_the_full_report(
        example_checks: None) -> None:
    """The explanation's columns mean what the report's do: every value on every
    line matches the row's lines of `build_report(include="all")`."""

    from jobcheck import explain_row

    outcomes = validate(DEMO)
    report = build_report(outcomes, df=DEMO, include="all").reset_index()
    for position in range(len(DEMO)):
        lines = report[report["row"] == str(DEMO.index[position])].drop(columns="row")
        pd.testing.assert_frame_equal(explain_row(outcomes, position),
                                      lines.reset_index(drop=True), check_names=False)


def test_a_rule_file_changes_the_same_report(example_checks: None) -> None:
    """The knob a user has without editing a check, exercised against one frame."""

    unrestricted = build_report(validate(DEMO), df=DEMO, key_column="id")
    suppressed = build_report(
        validate(DEMO, rules=load_rules(["examples/rules/error_rules.yaml"])),
        df=DEMO, key_column="id",
    )
    assert len(suppressed) <= len(unrestricted)
    assert "AGE_NOT_INTEGER" not in suppressed.index.get_level_values("code")
