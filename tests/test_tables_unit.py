"""Unit checks: table rendering and the registry/override report tables."""

from __future__ import annotations

import numpy
import pandas as pd
import pytest

from conftest import make_check
from jobcheck import registry as reg
from jobcheck import registry_tables
from jobcheck import tables

pytestmark = pytest.mark.fast


def a_rule(name: str = "r", action: str = "disable", codes: list[str] | None = None,
           source_file: str = "rules.yaml") -> reg.OverrideRule:
    return reg.OverrideRule(name=name, action=action, codes=codes or ["A_CODE"],
                            criteria=[], match_all=True, source_file=source_file)


# --- format_table -----------------------------------------------------------


def test_format_table_renders_headers_divider_and_rows() -> None:
    df = pd.DataFrame([{"code": "A", "state": "ON"}, {"code": "BB", "state": "OFF"}])
    assert tables.format_table(df) == (
        "code | state\n"
        "-----+------\n"
        "A    | ON   \n"
        "BB   | OFF  "
    )


def test_format_table_sizes_a_column_to_its_widest_cell() -> None:
    df = pd.DataFrame([{"c": "x"}, {"c": "much longer"}])
    assert tables.format_table(df).splitlines()[1] == "-----------"


def test_format_table_returns_empty_marker_for_an_empty_frame() -> None:
    assert tables.format_table(pd.DataFrame()) == "(empty)"


def test_format_table_returns_empty_marker_for_a_frame_with_columns_but_no_rows() -> None:
    assert tables.format_table(pd.DataFrame([], columns=["code"])) == "(empty)"


def test_format_table_wraps_a_column_onto_extra_lines() -> None:
    df = pd.DataFrame([{"code": "A", "text": "one two three four"}])
    assert tables.format_table(df, wrap_columns={"text": 8}) == (
        "code | text   \n"
        "-----+--------\n"
        "A    | one two\n"
        "     | three  \n"
        "     | four   "
    )


def test_wrapping_never_breaks_inside_a_word() -> None:
    df = pd.DataFrame([{"text": "SUPERCALIFRAGILISTIC_CODE"}])
    assert "SUPERCALIFRAGILISTIC_CODE" in tables.format_table(df, wrap_columns={"text": 8})


def test_wrapping_an_empty_cell_produces_one_blank_line() -> None:
    df = pd.DataFrame([{"code": "A", "text": ""}])
    assert tables.format_table(df, wrap_columns={"text": 8}) == (
        "code | text\n"
        "-----+-----\n"
        "A    |     "
    )


def test_null_cells_render_blank_not_nan() -> None:
    """Regression: pandas turns a None in an object column into NaN, which was
    rendered as the literal text "nan"."""

    df = pd.DataFrame([{"code": "A", "text": None}])
    assert tables.format_table(df).splitlines()[2] == "A    |     "


def test_missing_values_in_a_mixed_column_render_blank() -> None:
    df = pd.DataFrame([{"code": "A", "text": "here"}, {"code": "B", "text": None}])
    assert tables.format_table(df).splitlines()[3] == "B    |     "


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(["a", "b"], id="list"),
        pytest.param({"k": 1}, id="dict"),
        pytest.param({"a"}, id="set"),
        pytest.param(("a",), id="tuple"),
        pytest.param(pd.Series([1]), id="series"),
        pytest.param(numpy.array([1, 2]), id="ndarray"),
    ],
)
def test_list_like_cells_are_not_treated_as_null(value: object) -> None:
    """pd.isna on a container returns an array, so containers short-circuit to
    "not null" and render as their repr.

    Regression for the ndarray case, which the old isinstance list did not cover:
    bool() on that array raised "truth value of an array is ambiguous"."""

    assert tables.is_null(value) is False


def test_non_string_cells_are_stringified() -> None:
    df = pd.DataFrame([{"count": 7}])
    assert tables.format_table(df).splitlines()[2] == "7    "


# --- get_registry_table -----------------------------------------------------


def test_registry_table_has_the_base_columns(example_suites: None) -> None:
    assert list(registry_tables.get_registry_table().columns) == [
        "code", "layer", "suite", "default_state", "description", "depends_on",
    ]


def test_registry_table_adds_source_file_at_debug_two(example_suites: None) -> None:
    assert "source_file" in registry_tables.get_registry_table(debug=2).columns
    assert "source_file" not in registry_tables.get_registry_table(debug=1).columns


def test_registry_table_is_sorted_by_suite_then_layer_then_code(example_suites: None) -> None:
    table = registry_tables.get_registry_table()
    assert list(table["code"]) == [
        "ROW_ALL_NULL",
        "AGE_PRESENT", "DATES_PRESENT", "AGE_NOT_A_NUMBER", "DATES_OUT_OF_ORDER",
        "AGE_NEGATIVE", "AGE_NOT_INTEGER", "AGE_TOO_HIGH",
        "EMAIL_PRESENT", "EMAIL_MISSING_AT", "EMAIL_DOMAIN_INVALID",
    ]
    assert list(table["layer"]) == [0, 0, 0, 1, 1, 2, 2, 2, 0, 1, 2]


def test_registry_table_renders_default_state_as_on_or_off(example_suites: None) -> None:
    table = registry_tables.get_registry_table().set_index("code")
    assert table.loc["AGE_NEGATIVE", "default_state"] == "ON"
    assert table.loc["AGE_NOT_INTEGER", "default_state"] == "OFF"


def test_registry_table_joins_dependencies_and_dashes_when_there_are_none(
    fresh_registry: None,
) -> None:
    make_check("ROOT")
    make_check("OTHER")
    make_check("LEAF", depends_on=["ROOT", "OTHER"])
    table = registry_tables.get_registry_table().set_index("code")
    assert table.loc["LEAF", "depends_on"] == "ROOT; OTHER"
    assert table.loc["ROOT", "depends_on"] == "-"


def test_registry_table_of_an_empty_registry_has_columns_and_no_rows(fresh_registry: None) -> None:
    table = registry_tables.get_registry_table()
    assert table.empty
    assert list(table.columns) == [
        "code", "layer", "suite", "default_state", "description", "depends_on",
    ]


# --- print_registry ---------------------------------------------------------


def test_print_registry_prints_the_table_and_returns_it(
    example_suites: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = registry_tables.print_registry()
    out = capsys.readouterr().out
    assert "AGE_NEGATIVE" in out
    assert "code" in out.splitlines()[0]
    assert list(table["code"])[0] == "ROW_ALL_NULL"


def test_print_registry_on_an_empty_registry_says_so(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = registry_tables.print_registry()
    assert capsys.readouterr().out == "No checks registered.\n"
    assert table.empty


def test_could_be_overridden_by_appears_only_from_debug_one(fresh_registry: None) -> None:
    make_check("A_CODE")
    assert "could_be_overridden_by" not in registry_tables.print_registry([a_rule()], debug=0).columns
    assert "could_be_overridden_by" in registry_tables.print_registry([a_rule()], debug=1).columns


def test_could_be_overridden_by_lists_referencing_rules_in_load_order(fresh_registry: None) -> None:
    make_check("A_CODE")
    rules = [a_rule("first"), a_rule("second")]
    table = registry_tables.print_registry(rules, debug=1).set_index("code")
    assert table.loc["A_CODE", "could_be_overridden_by"] == "first; second"


def test_could_be_overridden_by_is_a_dash_for_an_unreferenced_code(fresh_registry: None) -> None:
    make_check("A_CODE")
    make_check("UNTOUCHED")
    table = registry_tables.print_registry([a_rule()], debug=1).set_index("code")
    assert table.loc["UNTOUCHED", "could_be_overridden_by"] == "-"


def test_print_registry_without_overrides_still_renders_at_debug_one(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.print_registry(debug=1).set_index("code")
    assert table.loc["A_CODE", "could_be_overridden_by"] == "-"


# --- print_registry_with_overrides -----------------------------------------


def test_registry_with_overrides_has_its_columns(fresh_registry: None) -> None:
    make_check("A_CODE")
    assert list(registry_tables.print_registry_with_overrides([]).columns) == [
        "code", "layer", "suite", "default_state", "override_rules", "effective_state",
    ]


def test_effective_state_states_the_default_when_no_rule_references_the_code(
    fresh_registry: None,
) -> None:
    make_check("ON_CODE")
    make_check("OFF_CODE", default_enabled=False)
    table = registry_tables.print_registry_with_overrides([]).set_index("code")
    assert table.loc["ON_CODE", "effective_state"] == "DEFAULT (ON)"
    assert table.loc["OFF_CODE", "effective_state"] == "DEFAULT (OFF)"
    assert table.loc["ON_CODE", "override_rules"] == "-"


def test_effective_state_refuses_to_guess_when_a_rule_references_the_code(
    fresh_registry: None,
) -> None:
    make_check("A_CODE", default_enabled=False)
    table = registry_tables.print_registry_with_overrides([a_rule()]).set_index("code")
    assert table.loc["A_CODE", "effective_state"] == (
        "depends on row (default OFF unless a rule above matches)"
    )


def test_override_rules_column_names_each_rule_with_its_action(fresh_registry: None) -> None:
    make_check("A_CODE")
    rules = [a_rule("on", action="enable"), a_rule("off", action="disable")]
    table = registry_tables.print_registry_with_overrides(rules).set_index("code")
    assert table.loc["A_CODE", "override_rules"] == "on (enable); off (disable)"


def test_registry_with_overrides_adds_source_file_at_debug_two(example_suites: None) -> None:
    table = registry_tables.print_registry_with_overrides([], debug=2).set_index("code")
    assert table.loc["AGE_NEGATIVE", "source_file"].endswith("check_age.py")


def test_registry_with_overrides_on_an_empty_registry_says_so(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = registry_tables.print_registry_with_overrides([])
    assert capsys.readouterr().out == "No checks registered.\n"
    assert table.empty


# --- print_override_rules ---------------------------------------------------


def test_override_rules_table_is_one_row_per_rule(fresh_registry: None) -> None:
    make_check("A_CODE")
    make_check("B_CODE")
    table = registry_tables.print_override_rules([a_rule("one", codes=["A_CODE", "B_CODE"]), a_rule("two")])
    assert list(table["name"]) == ["one", "two"]
    assert list(table["codes_hit_count"]) == [2, 1]


def test_match_all_renders_as_all(fresh_registry: None) -> None:
    make_check("A_CODE")
    assert registry_tables.print_override_rules([a_rule()])["match"][0] == "all"


def test_criteria_render_compactly(fresh_registry: None) -> None:
    import re as _re

    make_check("A_CODE")
    rule = reg.OverrideRule(
        name="r", action="disable", codes=["A_CODE"],
        criteria=[reg.MatchCriterion("source_system", "^LEGACY_", _re.compile("^LEGACY_")),
                  reg.MatchCriterion("record_type", "^BATCH$", _re.compile("^BATCH$"))],
        match_all=False,
    )
    assert registry_tables.print_override_rules([rule])["match"][0] == (
        "source_system~=/^LEGACY_/; record_type~=/^BATCH$/"
    )


def test_override_rules_table_adds_source_file_at_debug_two(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.print_override_rules([a_rule(source_file="here.yaml")], debug=2)
    assert list(table["source_file"]) == ["here.yaml"]


def test_no_rules_loaded_prints_a_message(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = registry_tables.print_override_rules([])
    assert capsys.readouterr().out == "No override rules loaded.\n"
    assert table.empty


# --- what wrapping must not do ----------------------------------------------
#
# Written against surviving mutants: textwrap's break_long_words and
# break_on_hyphens were flipped and nothing noticed, though both decide whether
# a code or a rule name comes back readable.


def test_a_word_longer_than_the_width_overflows_rather_than_being_split() -> None:
    """A code or rule name split across lines cannot be searched for or pasted."""

    frame = pd.DataFrame([{"code": "AGE_NOT_A_NUMBER_IN_A_VERY_LONG_CODE"}])
    rendered = tables.format_table(frame, wrap_columns={"code": 10})
    assert "AGE_NOT_A_NUMBER_IN_A_VERY_LONG_CODE" in rendered
    assert len(rendered.splitlines()) == 3  # header, divider, one row


def test_a_hyphenated_phrase_is_not_broken_at_its_hyphens() -> None:
    frame = pd.DataFrame([{"note": "cross-reference-column overflow"}])
    rendered = tables.format_table(frame, wrap_columns={"note": 12})
    assert "cross-reference-column" in rendered


def test_wrapping_still_breaks_between_words() -> None:
    """The counterpart: it is wrapping, not merely widening."""

    frame = pd.DataFrame([{"note": "one two three four five six seven"}])
    rendered = tables.format_table(frame, wrap_columns={"note": 12})
    body = rendered.splitlines()[2:]
    assert len(body) > 1
    assert all(len(line.rstrip()) <= 14 for line in body)


def test_an_empty_cell_wraps_to_one_blank_line() -> None:
    """textwrap.wrap("") is [], and a row with no lines would lose the row."""

    frame = pd.DataFrame([{"note": "", "code": "KEPT"}])
    rendered = tables.format_table(frame, wrap_columns={"note": 10})
    assert "KEPT" in rendered
    assert len(rendered.splitlines()) == 3
