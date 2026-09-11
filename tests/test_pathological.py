"""Pathological input: malformed, hostile, empty, boundary. Cheap cases only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from conftest import make_check, one_row_report
from jobcheck import registry as reg
from jobcheck import tables
from jobcheck import engine
from jobcheck.results import Status

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
    path = write(tmp_path, "bad.yaml", "- name: [unclosed\n")
    with pytest.raises(yaml.YAMLError):
        reg.load_overrides(path)


def test_yaml_that_is_only_a_comment_yields_no_rules(one_code: None, tmp_path: Path) -> None:
    assert reg.load_overrides(write(tmp_path, "c.yaml", "# nothing here\n")) == []


def test_yaml_null_document_yields_no_rules(one_code: None, tmp_path: Path) -> None:
    assert reg.load_overrides(write(tmp_path, "n.yaml", "null\n")) == []


def test_a_list_of_nulls_is_rejected_as_a_non_mapping_rule(one_code: None, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="each rule must be a mapping, got NoneType."):
        reg.load_overrides(write(tmp_path, "n.yaml", "- \n- \n"))


def test_directory_passed_where_a_file_is_expected(one_code: None, tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        reg.load_overrides(str(tmp_path))


def test_utf8_content_survives_the_round_trip(one_code: None, tmp_path: Path) -> None:
    path = write(
        tmp_path, "u.yaml",
        '- name: "rÃ¨gle_Ã©tÃ©"\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
    )
    assert reg.load_overrides(path)[0].name == "rÃ¨gle_Ã©tÃ©"


def test_a_pattern_matching_a_unicode_value(fresh_registry: None, tmp_path: Path) -> None:
    make_check("A_CODE")
    path = write(
        tmp_path, "u.yaml",
        '- name: "r"\n  action: disable\n  codes: [A_CODE]\n'
        '  match:\n    - column: city\n      pattern: "^MÃ¼nchen$"\n',
    )
    rules = reg.load_overrides(path)
    assert engine.resolve_enabled_state(pd.Series({"city": "MÃ¼nchen"}), rules)["A_CODE"] is False


def test_a_thousand_rules_load_and_the_last_wins(fresh_registry: None, tmp_path: Path) -> None:
    make_check("A_CODE")
    body = "".join(
        f'- name: "rule_{i:04d}"\n  action: {"enable" if i % 2 == 0 else "disable"}\n'
        f"  codes: [A_CODE]\n  match: all\n"
        for i in range(1000)
    )
    rules = reg.load_overrides(write(tmp_path, "many.yaml", body))
    assert len(rules) == 1000
    assert engine.resolve_enabled_state(pd.Series({"age": 1}), rules)["A_CODE"] is False


# --- hostile rows -----------------------------------------------------------


def test_empty_row_reports_the_presence_tests_and_nothing_below_them(
    example_checks: None,
) -> None:
    assert [r.code for r in engine.validate_row(pd.Series(dtype=object))] == [
        "ROW_ALL_NULL", "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"
    ]


def test_row_with_unexpected_columns_only_reports_what_is_missing(
    example_checks: None,
) -> None:
    row = pd.Series({"totally": "unrelated"})
    assert [r.code for r in engine.validate_row(row)] == [
        "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"
    ]


def test_duplicate_column_labels_are_rejected_not_silently_passed(fresh_registry: None) -> None:
    """A duplicate label hands the check a Series, which every value helper turns
    into None -- so the check would silently pass on data it never read."""

    make_check("A_CODE")
    row = pd.Series([1, 2], index=["age", "age"])
    with pytest.raises(ValueError) as excinfo:
        engine.validate_row(row)
    assert "duplicate column labels ['age']" in str(excinfo.value)


def test_duplicate_labels_are_rejected_before_any_check_runs(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("A_CODE", calls=calls)
    with pytest.raises(ValueError):
        engine.validate_row(pd.Series([1, 2], index=["age", "age"]))
    assert calls == []


def test_a_very_long_string_value_is_matched_not_truncated(fresh_registry: None) -> None:
    import re

    make_check("A_CODE")
    rule = reg.OverrideRule(
        name="r", action="disable", codes=["A_CODE"],
        criteria=[reg.MatchCriterion("email", "end$", re.compile("end$"))], match_all=False,
    )
    row = pd.Series({"email": "x" * 100_000 + "end"})
    assert engine.resolve_enabled_state(row, [rule])["A_CODE"] is False


def test_a_test_that_raises_is_recorded_as_an_error_not_a_pass(fresh_registry: None) -> None:
    """A broken check must never be mistaken for a happy one."""

    @reg.register_check(code="EXPLODES", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        raise RuntimeError("check is broken")

    outcome = engine.validate_row(pd.Series({"age": 1}))[0]
    assert outcome.outcome == "errored"
    assert outcome.status == Status.ERROR
    assert outcome.detail == "RuntimeError: check is broken"


def test_a_raising_test_can_be_made_fatal(fresh_registry: None) -> None:
    @reg.register_check(code="EXPLODES", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        raise RuntimeError("check is broken")

    with pytest.raises(RuntimeError, match="check is broken"):
        engine.validate_row(pd.Series({"age": 1}), on_error="raise")


def test_a_test_reading_a_column_that_is_absent_errors_naming_it(fresh_registry: None) -> None:
    """Checks read the row themselves, so a typo surfaces as a KeyError outcome."""

    @reg.register_check(code="TYPO", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        return row["agee"] > 0

    outcome = engine.validate_row(pd.Series({"age": 1}))[0]
    assert outcome.outcome == "errored"
    assert "agee" in outcome.detail


def test_a_test_returning_nothing_raises_even_when_errors_are_recorded(
    fresh_registry: None,
) -> None:
    """A bad return is an authoring bug, not a data problem, so it is never recorded."""

    @reg.register_check(code="FORGOT", message="m")
    def check(row: "pd.Series[Any]") -> Any:
        pass

    with pytest.raises(TypeError, match=r"Check 'FORGOT' returned None"):
        engine.validate_row(pd.Series({"age": 1}))


def test_a_deep_dependency_chain_evaluates_in_order(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("LINK_000", passes=True, calls=calls)
    for i in range(1, 200):
        make_check(f"LINK_{i:03d}", passes=True, depends_on=[f"LINK_{i - 1:03d}"], calls=calls)
    assert engine.validate_row(pd.Series({"age": 1})) == []
    assert calls == [f"LINK_{i:03d}" for i in range(200)]


def test_a_deep_chain_skips_everything_below_a_failure(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("LINK_000", passes=False, calls=calls)
    for i in range(1, 200):
        make_check(f"LINK_{i:03d}", passes=True, depends_on=[f"LINK_{i - 1:03d}"], calls=calls)
    assert [r.code for r in engine.validate_row(pd.Series({"age": 1}))] == ["LINK_000"]
    assert calls == ["LINK_000"]


def test_wide_row_with_many_columns(fresh_registry: None) -> None:
    make_check("A_CODE")
    row = pd.Series({f"col_{i:04d}": i for i in range(1000)})
    assert engine.validate_row(row) == []


def test_table_rendering_of_a_cell_containing_a_pipe(fresh_registry: None) -> None:
    """The renderer does not escape, so a pipe in data is shown literally."""

    df = pd.DataFrame([{"code": "A|B"}])
    assert tables.format_table(df).splitlines()[2] == "A|B "


# --- hostile values reaching the report ------------------------------------


def test_a_newline_in_a_message_does_not_break_the_table(fresh_registry: None) -> None:
    """textwrap collapses it, so every rendered line stays the same width."""

    from jobcheck import render_report

    lines = render_report(one_row_report({}, message="line one\nline two")).splitlines()
    assert len({len(line) for line in lines}) == 1
    assert "line one line two" in lines[2]


def test_a_newline_in_a_comment_value_does_not_break_the_table(fresh_registry: None) -> None:
    from jobcheck import render_report

    lines = render_report(one_row_report({"note": "a\nb"})).splitlines()
    assert len({len(line) for line in lines}) == 1


def test_a_very_long_comment_value_overflows_rather_than_being_mangled(
    fresh_registry: None,
) -> None:
    """Wrapping never breaks inside a word, so a long identifier stays greppable
    at the cost of a wide table."""

    from jobcheck import render_report

    value = "x" * 200
    text = render_report(one_row_report({"big": value}))
    assert value in text


def test_unicode_survives_both_formats(fresh_registry: None) -> None:
    from jobcheck import render_report

    report = one_row_report({"ville": "MÃ¼nchen"}, message="Ã©chec de la rÃ¨gle")
    for fmt in ("table", "csv"):
        text = render_report(report, fmt=fmt)
        assert "MÃ¼nchen" in text and "Ã©chec" in text


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="none"),
        pytest.param(float("nan"), id="nan"),
        pytest.param([1, 2], id="list"),
        pytest.param({"nested": 1}, id="dict"),
        pytest.param(pd.Timestamp("2024-01-01"), id="timestamp"),
    ],
)
def test_a_non_string_comment_value_renders(fresh_registry: None, value: Any) -> None:
    from jobcheck import render_report

    text = render_report(one_row_report({"v": value}), fmt="csv")
    assert "CELL" in text


def test_a_hundred_comment_keys_render_in_sorted_order(fresh_registry: None) -> None:
    from jobcheck import render_comments

    comments = {f"key_{index:03d}": index for index in range(100)}
    rendered = render_comments(comments)
    assert rendered.startswith("key_000=0; key_001=1")
    assert rendered.count(";") == 99


def test_a_key_column_value_containing_the_separator_is_refused(
    fresh_registry: None,
) -> None:
    """Composite keys join with '|', so a value containing one is ambiguous:
    ("A|B", 1) and ("A", "B|1") would render the same label. The report refuses
    rather than producing two rows nobody can tell apart."""

    from jobcheck import build_report, validate

    make_check("FAILS", passes=False)
    frame = pd.DataFrame([{"batch": "A|B", "id": 1}])
    with pytest.raises(ValueError, match="joins a multi-column key"):
        build_report(validate(frame), df=frame, key_column=["batch", "id"])


def test_a_frame_with_duplicate_column_labels_fails_on_the_first_row(
    fresh_registry: None,
) -> None:
    from jobcheck import validate

    make_check("CODE")
    frame = pd.DataFrame([[1, 2]], columns=["age", "age"])
    with pytest.raises(ValueError, match="duplicate column labels"):
        validate(frame)


def test_an_empty_frame_produces_an_empty_report(fresh_registry: None) -> None:
    from jobcheck import build_report, validate, summarise_outcomes

    make_check("CODE")
    frame = pd.DataFrame(columns=["age"])
    outcomes = validate(frame)
    assert outcomes == []
    assert build_report(outcomes, df=frame).empty
    assert summarise_outcomes(outcomes).empty
