"""Safety: no code execution from data, no path escapes, no secret leakage."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import make_test, one_row_report
from pandas_row_validation import registry as reg

pytestmark = pytest.mark.fast


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.fixture
def one_code(fresh_registry: None) -> None:
    make_test("A_CODE")


def test_yaml_cannot_construct_arbitrary_python_objects(one_code: None, tmp_path: Path) -> None:
    """safe_load, not load: a !!python/object tag must be refused, not executed."""

    path = write(tmp_path, "evil.yaml", "- !!python/object/apply:os.system ['echo pwned']\n")
    with pytest.raises(Exception) as excinfo:
        reg.load_overrides(path)
    assert "python/object" in str(excinfo.value)


def test_a_rule_pattern_is_never_evaluated_as_code(one_code: None, tmp_path: Path) -> None:
    path = write(
        tmp_path, "r.yaml",
        '- name: "r"\n  action: disable\n  codes: [A_CODE]\n'
        "  match:\n    - column: email\n      pattern: \"__import__('os').system('x')\"\n",
    )
    rules = reg.load_overrides(path)
    assert rules[0].criteria[0].pattern == "__import__('os').system('x')"
    assert reg.resolve_enabled_state(pd.Series({"email": "harmless"}), rules)["A_CODE"] is True


def test_loading_rules_writes_nothing_to_disk(one_code: None, tmp_path: Path) -> None:
    write(tmp_path, "r.yaml", '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n')
    before = sorted(p.name for p in tmp_path.iterdir())
    reg.load_overrides_from_dir(str(tmp_path))
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_validation_never_mutates_the_dataframe_it_reads(example_suites: None) -> None:
    df = pd.DataFrame([{"age": -1, "email": "a@b.com"}])
    snapshot = df.copy(deep=True)
    df.apply(lambda row: reg.validate_row(row), axis=1)
    assert df.equals(snapshot)


def test_a_suite_name_cannot_escape_the_package_via_dots(fresh_registry: None) -> None:
    """A dotted name is not resolved as a path; it fails as an unknown suite,
    before anything is imported."""

    with pytest.raises(ValueError, match="Unknown suite"):
        reg.load_suites(["..os"], package="example_suites")
    assert reg.TESTS == []


def test_a_suite_name_cannot_import_an_unrelated_top_level_module(fresh_registry: None) -> None:
    """'os' is resolved against the given package, never as a top-level import,
    and the failure leaves the registry untouched."""

    with pytest.raises(ValueError, match="Unknown suite 'os'"):
        reg.load_suites(["os"], package="example_suites")
    assert reg.loaded_suites() == set()
    assert reg.TESTS == []


def test_load_overrides_from_dir_does_not_recurse_into_subdirectories(
    one_code: None, tmp_path: Path
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    write(nested, "hidden.yaml", '- name: "n"\n  action: disable\n  codes: [A_CODE]\n  match: all\n')
    assert reg.load_overrides_from_dir(str(tmp_path)) == []


def test_a_catastrophic_regex_is_bounded_by_the_value_length(one_code: None, tmp_path: Path) -> None:
    """A nested-quantifier pattern on a short value must not hang the run.

    The framework does not sandbox regexes -- the guard is that criteria run
    against single cell values, so the assertion is a wall-clock ceiling.
    """

    rule = reg.OverrideRule(
        name="redos", action="disable", codes=["A_CODE"],
        criteria=[reg.MatchCriterion("email", "(a+)+$", re.compile("(a+)+$"))], match_all=False,
    )
    row = pd.Series({"email": "a" * 22 + "!"})
    start = time.monotonic()
    reg.resolve_enabled_state(row, [rule])
    assert time.monotonic() - start < 5.0


def test_an_ndarray_cell_does_not_break_rule_matching(one_code: None) -> None:
    """Regression: pd.isna on an ndarray returns an array, and the bool() of that
    raised "truth value of an array is ambiguous" instead of matching."""

    import numpy

    rule = reg.OverrideRule(
        name="r", action="disable", codes=["A_CODE"],
        criteria=[reg.MatchCriterion("data", "x", re.compile("x"))], match_all=False,
    )
    row = pd.Series({"data": numpy.array([1, 2])})
    assert reg.resolve_enabled_state(row, [rule])["A_CODE"] is True


# --- reports opened in a spreadsheet ---------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        pytest.param("=cmd|' /c calc'!A1", id="equals"),
        pytest.param("+1+1", id="plus"),
        pytest.param("@SUM(A1)", id="at"),
        pytest.param("-cmd", id="minus-not-a-number"),
        pytest.param("\tstarts-with-tab", id="tab"),
    ],
)
def test_a_formula_cell_is_neutralised_in_csv(fresh_registry: None, message: str) -> None:
    """A report is meant to be opened in a spreadsheet, and comments carry values
    that came from the data, so a formula in a cell would execute on open."""

    from pandas_row_validation import render_report

    csv = render_report(one_row_report({}, message=message), fmt="csv")
    assert f",'{message}," in csv or f",'{message}\n" in csv or f"'{message}" in csv
    assert f",{message}," not in csv


def test_a_negative_number_keeps_its_minus_sign(fresh_registry: None) -> None:
    from pandas_row_validation import escape_for_spreadsheet

    assert escape_for_spreadsheet("-5") == "-5"
    assert escape_for_spreadsheet("-5.25") == "-5.25"
    assert escape_for_spreadsheet("-cmd") == "'-cmd"


def test_a_formula_inside_a_comment_value_cannot_start_the_cell(
    fresh_registry: None,
) -> None:
    """Comments always render as ``key=value``, so a formula taken from the data
    lands mid-cell, where a spreadsheet reads it as text. The cell is left as it
    is rather than being escaped for a danger it does not have."""

    from pandas_row_validation import render_report

    csv = render_report(one_row_report({"value": "=1+1"}), fmt="csv")
    assert ",value==1+1," in csv


def test_a_formula_in_the_row_key_is_neutralised(fresh_registry: None) -> None:
    from pandas_row_validation import build_report, collect_outcomes, render_report
    from pandas_row_validation.results import Status, TestResult

    @reg.register_test(code="CELL", message="m")
    def check(row: "pd.Series[Any]") -> TestResult:
        return TestResult(Status.INVALID)

    frame = pd.DataFrame([{"id": "=DANGER()"}])
    report = build_report(collect_outcomes(frame), df=frame, key_column="id")
    assert render_report(report, fmt="csv").splitlines()[1].startswith("'=DANGER()")


def test_the_table_view_is_left_alone(fresh_registry: None) -> None:
    """Text output cannot execute, so the value is shown as the test saw it."""

    from pandas_row_validation import render_report

    text = render_report(one_row_report({}, message="=1+1"))
    assert "=1+1" in text
    assert "'=1+1" not in text


def test_escaping_can_be_switched_off_for_a_machine_reader(fresh_registry: None) -> None:
    from pandas_row_validation import render_report

    csv = render_report(one_row_report({}, message="=1+1"), fmt="csv", escape_formulas=False)
    assert ",=1+1," in csv


def test_a_written_report_is_escaped_too(fresh_registry: None, tmp_path: Path) -> None:
    from pandas_row_validation import write_report

    path = tmp_path / "report.csv"
    write_report(one_row_report({}, message="=1+1"), str(path))
    assert "'=1+1" in path.read_text(encoding="utf-8")


def test_comments_are_never_evaluated(fresh_registry: None) -> None:
    """Comments are data all the way through: nothing formats or evals them."""

    from pandas_row_validation import render_comments

    rendered = render_comments({"expr": "__import__('os').system('x')"})
    assert rendered == "expr=__import__('os').system('x')"


def test_error_messages_quote_the_offending_value_not_the_whole_file(
    one_code: None, tmp_path: Path
) -> None:
    """A rule file may sit beside sensitive data; errors must stay local."""

    path = write(
        tmp_path, "r.yaml",
        '- name: "r"\n  action: disable\n  codes: [NOT_A_CODE]\n  match: all\n'
        '- name: "other"\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
    )
    with pytest.raises(ValueError) as excinfo:
        reg.load_overrides(path)
    message = str(excinfo.value)
    assert "NOT_A_CODE" in message
    assert "other" not in message
