"""Integration: the shipped rule files driving a real DataFrame, and the views agreeing.

CSV export and its round trip are pinned byte for byte in `test_golden_output.py`;
loading files written at runtime is in `test_load_files_unit.py` and
`test_rules_unit.py`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import failures

from jobcheck import (
    RowContext,
    build_report,
    validate,
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


def test_file_order_decides_precedence_across_directories(example_checks: None) -> None:
    """The split files alone leave the legacy enable in force; a later global
    rule from another directory overrides it, and reversing the order undoes that."""

    assert codes(validated(load_rules(SPLIT_BY_TOPIC)))[1] == ["AGE_NOT_INTEGER"]
    paths = [
        "examples/rules/split_by_topic/01_age_rules.yaml",
        "examples/rules/split_by_topic/02_email_rules.yaml",
        "examples/rules/from_another_directory/global_age_rule.yaml",
    ]
    assert codes(validated(load_rules(paths)))[1] == []
    assert codes(validated(load_rules(list(reversed(paths)))))[1] == [
        "AGE_NOT_INTEGER"
    ]


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
