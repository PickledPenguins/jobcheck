"""Pathological input: malformed, hostile, empty, boundary. Cheap cases only."""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from conftest import enabled_only, failures, make_check
from jobcheck import registry as reg
from jobcheck import engine
from jobcheck.results import Status
from jobcheck.rules import _MatchCriterion

pytestmark = pytest.mark.fast


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.fixture
def one_code(fresh_registry: None) -> None:
    make_check("A_CODE")


# --- malformed rule files ---------------------------------------------------


def test_invalid_yaml_raises_a_yaml_error(one_code: None, tmp_path: Path) -> None:
    path = write(tmp_path, "bad.yaml", "- name: [unclosed\n  message: \"why the rule exists\"\n")
    with pytest.raises(yaml.YAMLError):
        reg.load_rules([path])


def test_yaml_that_is_only_a_comment_yields_no_rules(one_code: None, tmp_path: Path) -> None:
    assert reg.load_rules([write(tmp_path, "c.yaml", "# nothing here\n")]) == []


def test_yaml_null_document_yields_no_rules(one_code: None, tmp_path: Path) -> None:
    assert reg.load_rules([write(tmp_path, "n.yaml", "null\n")]) == []


def test_a_list_of_nulls_is_rejected_as_a_non_mapping_rule(one_code: None, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="each rule must be a mapping, got NoneType."):
        reg.load_rules([write(tmp_path, "n.yaml", "- \n- \n")])


def test_directory_passed_where_a_file_is_expected(one_code: None, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="is a directory, so name the file in it"):
        reg.load_rules([str(tmp_path)])


def test_utf8_content_survives_the_round_trip(one_code: None, tmp_path: Path) -> None:
    path = write(
        tmp_path, "u.yaml",
        '- name: "règle_été"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
    )
    assert reg.load_rules([path])[0].name == "règle_été"


def test_a_pattern_matching_a_unicode_value(fresh_registry: None, tmp_path: Path) -> None:
    make_check("A_CODE")
    path = write(
        tmp_path, "u.yaml",
        '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n'
        '  match:\n    - column: city\n      pattern: "^München$"\n',
    )
    rules = reg.load_rules([path])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"city": "München"}), rules))["A_CODE"] is False


def test_a_thousand_rules_load_and_the_last_wins(fresh_registry: None, tmp_path: Path) -> None:
    make_check("A_CODE")
    body = "".join(
        f'- name: "rule_{i:04d}"\n  message: \"why the rule exists\"\n  action: {"enable" if i % 2 == 0 else "disable"}\n'
        f"  codes: [A_CODE]\n  match: all\n"
        for i in range(1000)
    )
    rules = reg.load_rules([write(tmp_path, "many.yaml", body)])
    assert len(rules) == 1000
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"age": 1}), rules))["A_CODE"] is False


# --- hostile rows -----------------------------------------------------------


def test_empty_row_reports_the_presence_checks_and_nothing_below_them(
    example_checks: None,
) -> None:
    assert [r.code for r in failures(pd.Series(dtype=object))] == [
        "ROW_ALL_NULL", "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"
    ]


def test_row_with_unexpected_columns_only_reports_what_is_missing(
    example_checks: None,
) -> None:
    row = pd.Series({"totally": "unrelated"})
    assert [r.code for r in failures(row)] == [
        "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"
    ]


def test_duplicate_column_labels_are_rejected_not_silently_passed(fresh_registry: None) -> None:
    """A duplicate label hands the check a Series, which every value helper turns
    into None -- so the check would silently pass on data it never read."""

    make_check("A_CODE")
    row = pd.Series([1, 2], index=["age", "age"])
    with pytest.raises(ValueError) as excinfo:
        failures(row)
    assert "duplicate column labels ['age']" in str(excinfo.value)


def test_duplicate_labels_are_rejected_before_any_check_runs(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("A_CODE", calls=calls)
    with pytest.raises(ValueError):
        failures(pd.Series([1, 2], index=["age", "age"]))
    assert calls == []


def test_a_very_long_string_value_is_matched_not_truncated(fresh_registry: None) -> None:
    import re

    make_check("A_CODE")
    rule = reg.Rule(
        name="r", action="disable", codes=["A_CODE"],
        criteria=[_MatchCriterion("email", "end$", re.compile("end$"))], match_all=False, message="why the rule exists")
    row = pd.Series({"email": "x" * 100_000 + "end"})
    assert enabled_only(engine._resolve_enabled_state(row, [rule]))["A_CODE"] is False


def test_a_check_that_raises_is_recorded_as_an_error_not_a_pass(fresh_registry: None) -> None:
    """A broken check must never be mistaken for a happy one."""

    @reg.register_check(code="EXPLODES", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        raise RuntimeError("check is broken")

    outcome = failures(pd.Series({"age": 1}))[0]
    assert outcome.outcome == "errored"
    assert outcome.status == Status.ERROR
    line = check.__code__.co_firstlineno + 2  # the decorator, the def, then the raise
    assert outcome.detail == f"RuntimeError: check is broken (test_pathological.py:{line})"


def test_an_errored_detail_names_the_checks_line_through_a_helper(
        fresh_registry: None, tmp_path: Path) -> None:
    """Raised inside a helper in another file, the line shown is the check's call
    to it: the innermost line in the file the check was written in."""

    (tmp_path / "helpers.py").write_text("def parse(value):\n    return value.upper()\n",
                                         encoding="utf-8")
    (tmp_path / "check_x.py").write_text(
        "from jobcheck import OK, register_check\n"
        "from helpers import parse\n"
        "\n"
        "@register_check('PARSES', 'm')\n"
        "def parses(row):\n"
        "    parse(len(row))\n"
        "    return OK\n", encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        reg.load_checks([str(tmp_path / "check_x.py")])
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("helpers", None)
    outcome = failures(pd.Series({"value": "x"}))[0]
    assert outcome.detail == (
        "AttributeError: 'int' object has no attribute 'upper' (check_x.py:6)")


@pytest.mark.parametrize("make", [
    lambda fn: fn,
    lambda fn: functools.partial(fn),
])
def test_an_errored_detail_with_no_message_drops_its_colon(
        fresh_registry: None, make: Any) -> None:
    """`raise ValueError()` has no text: the type and the place, no dangling `: `.
    A `functools.partial` is located in the function it wraps."""

    def check(row: "pd.Series[Any]", context: Any) -> bool:
        raise ValueError()

    reg.register_check(code="SILENT", message="m")(make(check))
    outcome = failures(pd.Series({"age": 1}))[0]
    line = check.__code__.co_firstlineno + 1
    assert outcome.detail == f"ValueError (test_pathological.py:{line})"





def test_a_check_reading_a_column_that_is_absent_errors_naming_it(fresh_registry: None) -> None:
    """Checks read the row themselves, so a typo surfaces as a KeyError outcome."""

    @reg.register_check(code="TYPO", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        return row["agee"] > 0

    outcome = failures(pd.Series({"age": 1}))[0]
    assert outcome.outcome == "errored"
    assert "agee" in outcome.detail





def test_a_check_returning_nothing_raises_even_when_errors_are_recorded(
    fresh_registry: None,
) -> None:
    """A bad return is an authoring bug, not a data problem, so it is never recorded.
    The only test of that path through the engine, so the message names the check."""

    @reg.register_check(code="FORGOT", message="m")
    def check(row: "pd.Series[Any]") -> Any:
        pass

    with pytest.raises(TypeError, match=r"Check 'FORGOT' returned None"):
        failures(pd.Series({"age": 1}))


def test_a_deep_dependency_chain_evaluates_in_order(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("LINK_000", passes=True, calls=calls)
    for i in range(1, 200):
        make_check(f"LINK_{i:03d}", passes=True, depends_on=[f"LINK_{i - 1:03d}"], calls=calls)
    assert failures(pd.Series({"age": 1})) == []
    assert calls == [f"LINK_{i:03d}" for i in range(200)]


def test_a_deep_chain_skips_everything_below_a_failure(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("LINK_000", passes=False, calls=calls)
    for i in range(1, 200):
        make_check(f"LINK_{i:03d}", passes=True, depends_on=[f"LINK_{i - 1:03d}"], calls=calls)
    assert [r.code for r in failures(pd.Series({"age": 1}))] == ["LINK_000"]
    assert calls == ["LINK_000"]


def test_wide_row_with_many_columns(fresh_registry: None) -> None:
    make_check("A_CODE")
    row = pd.Series({f"col_{i:04d}": i for i in range(1000)})
    assert failures(row) == []


# --- hostile values reaching the report ------------------------------------


def test_a_hundred_comment_keys_render_in_the_order_written(fresh_registry: None) -> None:
    from jobcheck.views import _render_comments

    comments = {f"key_{index:03d}": index for index in reversed(range(100))}
    rendered = _render_comments(comments)
    assert rendered.startswith("key_099=99; key_098=98")
    assert rendered.count(";") == 99





def test_an_empty_frame_produces_an_empty_report(fresh_registry: None) -> None:
    from jobcheck import build_report, validate, summarize_outcomes

    make_check("CODE")
    frame = pd.DataFrame(columns=["age"])
    outcomes = validate(frame)
    assert outcomes == []
    assert build_report(outcomes, df=frame).empty
    assert summarize_outcomes(outcomes).empty
