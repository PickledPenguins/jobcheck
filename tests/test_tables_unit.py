"""Unit checks: table rendering and the registry and rule tables."""

from __future__ import annotations

from typing import Any

import numpy
import pandas as pd
import pytest

from conftest import make_check
from jobcheck import registry as reg
from jobcheck import registry_tables
from jobcheck import tables

pytestmark = pytest.mark.fast


def a_rule(name: str = "r", action: str = "disable", codes: list[str] | None = None,
           source_file: str = "rules.yaml") -> reg.Rule:
    return reg.Rule(name=name, action=action, codes=codes or ["A_CODE"],
                            criteria=[], match_all=True, source_file=source_file, message="why the rule exists")


# --- format_table -----------------------------------------------------------


def test_format_table_renders_headers_divider_and_rows() -> None:
    df = pd.DataFrame([{"code": "A", "state": "ON"}, {"code": "BB", "state": "OFF"}])
    assert tables.format_table(df) == (
        "code | state\n"
        "-----+------\n"
        "A    | ON   \n"
        "BB   | OFF  "
    )


def test_a_wrap_width_of_zero_is_refused_by_name(fresh_registry: None) -> None:
    """Regression: textwrap's own "invalid width 0 (must be > 0)" names neither
    the column nor this function. render_report guards its own width; the public
    function underneath it did not."""

    df = pd.DataFrame([{"a": "hi"}])
    for widths in ({"a": 0}, {"a": -5}):
        with pytest.raises(ValueError) as raised:
            tables.format_table(df, wrap_columns=widths)
        assert str(raised.value) == (
            "wrap_columns width for ['a'] must be greater than 0. Leave a column "
            "out of wrap_columns rather than asking for a width of zero."
        )


def test_a_bad_wrap_width_is_refused_for_an_empty_frame_too() -> None:
    """The argument is wrong whether or not there is anything to wrap, so it is
    checked before the empty frame is answered with `(empty)`."""

    with pytest.raises(ValueError, match=r"wrap_columns width for \['a'\]"):
        tables.format_table(pd.DataFrame(), wrap_columns={"a": 0})


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


def test_registry_table_has_the_base_columns(example_checks: None) -> None:
    assert list(registry_tables.get_registry_table().columns) == [
        "code", "layer", "default", "message", "depends_on",
    ]


def test_registry_table_adds_source_file_when_asked_for(example_checks: None) -> None:
    assert "source_file" in registry_tables.get_registry_table(add_columns=["source_file"]).columns
    assert "source_file" not in registry_tables.get_registry_table().columns


def test_registry_table_is_sorted_by_layer_then_code(example_checks: None) -> None:
    table = registry_tables.get_registry_table()
    assert list(table["code"]) == [
        "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT", "ROW_ALL_NULL",
        "AGE_NOT_A_NUMBER", "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT",
        "AGE_NEGATIVE", "AGE_NOT_INTEGER", "AGE_TOO_HIGH", "EMAIL_DOMAIN_INVALID",
    ]
    assert list(table["layer"]) == [0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 2]


def test_registry_table_renders_the_default_as_on_or_off(example_checks: None) -> None:
    table = registry_tables.get_registry_table().set_index("code")
    assert table.loc["AGE_NEGATIVE", "default"] == "ON"
    assert table.loc["AGE_NOT_INTEGER", "default"] == "OFF"


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
        "code", "layer", "default", "message", "depends_on",
    ]


# --- print_registry ---------------------------------------------------------


def test_print_registry_prints_the_table_and_returns_it(
    example_checks: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = registry_tables.print_registry(title=False)
    out = capsys.readouterr().out
    assert "AGE_NEGATIVE" in out
    assert "code" in out.splitlines()[0]
    assert list(table["code"])[0] == "AGE_PRESENT"


def test_print_registry_on_an_empty_registry_says_so(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = registry_tables.print_registry(title=False)
    assert capsys.readouterr().out == "No checks registered.\n"
    assert table.empty


def test_could_be_overridden_by_appears_only_when_asked_for(fresh_registry: None) -> None:
    make_check("A_CODE")
    assert "could_be_overridden_by" not in registry_tables.print_registry([a_rule()]).columns
    assert "could_be_overridden_by" in registry_tables.print_registry([a_rule()], add_columns=["could_be_overridden_by"]).columns


def test_could_be_overridden_by_names_each_rule_with_its_action_in_load_order(
    fresh_registry: None,
) -> None:
    make_check("A_CODE")
    rules = [a_rule("first", action="enable"), a_rule("second", action="disable")]
    table = registry_tables.print_registry(rules, add_columns=["could_be_overridden_by"]).set_index("code")
    assert table.loc["A_CODE", "could_be_overridden_by"] == "first (enable); second (disable)"


def test_could_be_overridden_by_is_a_dash_for_an_unreferenced_code(fresh_registry: None) -> None:
    make_check("A_CODE")
    make_check("UNTOUCHED")
    table = registry_tables.print_registry([a_rule()], add_columns=["could_be_overridden_by"]).set_index("code")
    assert table.loc["UNTOUCHED", "could_be_overridden_by"] == "-"


def test_print_registry_without_rules_still_renders_that_column(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.print_registry(add_columns=["could_be_overridden_by"]).set_index("code")
    assert table.loc["A_CODE", "could_be_overridden_by"] == "-"


# --- print_registry, the columns that read the rules ------------------------


def test_effective_state_states_the_default_when_no_rule_references_the_code(
    fresh_registry: None,
) -> None:
    make_check("ON_CODE")
    make_check("OFF_CODE", default_enabled=False)
    table = registry_tables.print_registry(
        [], add_columns=["effective_state"]).set_index("code")
    assert table.loc["ON_CODE", "effective_state"] == "DEFAULT (ON)"
    assert table.loc["OFF_CODE", "effective_state"] == "DEFAULT (OFF)"


def test_effective_state_refuses_to_guess_when_a_rule_references_the_code(
    fresh_registry: None,
) -> None:
    make_check("A_CODE", default_enabled=False)
    table = registry_tables.print_registry(
        [a_rule()], add_columns=["effective_state"]).set_index("code")
    assert table.loc["A_CODE", "effective_state"] == (
        "depends on row (default OFF unless a rule above matches)"
    )


def test_effective_state_appears_only_when_asked_for(fresh_registry: None) -> None:
    make_check("A_CODE")
    assert "effective_state" not in registry_tables.print_registry([a_rule()]).columns


def test_both_rule_columns_can_be_asked_for_at_once(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.print_registry(
        [a_rule()], add_columns=["could_be_overridden_by", "effective_state"])
    assert list(table.columns) == [
        "code", "layer", "default", "message", "depends_on",
        "could_be_overridden_by", "effective_state",
    ]


# --- print_rules ---------------------------------------------------


def test_rules_table_is_one_row_per_rule(fresh_registry: None) -> None:
    make_check("A_CODE")
    make_check("B_CODE")
    table = registry_tables.print_rules([a_rule("one", codes=["A_CODE", "B_CODE"]), a_rule("two")])
    assert list(table["name"]) == ["one", "two"]
    assert list(table["codes_hit_count"]) == [2, 1]


def test_match_all_renders_as_all(fresh_registry: None) -> None:
    make_check("A_CODE")
    assert registry_tables.print_rules([a_rule()])["match"][0] == "all"


def test_criteria_render_compactly(fresh_registry: None) -> None:
    import re as _re

    make_check("A_CODE")
    rule = reg.Rule(
        name="r", action="disable", codes=["A_CODE"],
        criteria=[reg.MatchCriterion("source_system", "^LEGACY_", _re.compile("^LEGACY_")),
                  reg.MatchCriterion("record_type", "^BATCH$", _re.compile("^BATCH$"))],
        match_all=False, message="why the rule exists",
    )
    assert registry_tables.print_rules([rule])["match"][0] == (
        "source_system~=/^LEGACY_/; record_type~=/^BATCH$/"
    )


def test_rules_table_adds_source_file_when_asked_for(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.print_rules([a_rule(source_file="here.yaml")], add_columns=["source_file"])
    assert list(table["source_file"]) == ["here.yaml"]


def test_no_rules_loaded_prints_a_message(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = registry_tables.print_rules([], title=False)
    assert capsys.readouterr().out == "No rules loaded.\n"
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


def test_a_cell_holding_a_newline_renders_tall_instead_of_breaking_the_row() -> None:
    """A quoted multi-line CSV field reaches an unwrapped column -- the row key
    and every extra_column -- and the renderer pads with len(), so a cell that
    emits its own newline slides every column after it."""

    frame = pd.DataFrame([{"id": "a\nb", "note": "one"}, {"id": "c", "note": "two"}])
    lines = tables.format_table(frame).splitlines()
    widths = {len(line.split(" | ")) for line in lines[2:]}
    assert widths == {2}
    assert [line.split(" | ")[0].rstrip() for line in lines[2:]] == ["a", "b", "c"]


def test_the_same_cell_renders_tall_in_a_wrapped_column() -> None:
    """Wrapped and unwrapped columns agree on what a line is; textwrap on its
    own collapses the newline to a space."""

    frame = pd.DataFrame([{"note": "a\nb"}])
    body = tables.format_table(frame, wrap_columns={"note": 10}).splitlines()[2:]
    assert [line.rstrip() for line in body] == ["a", "b"]


def test_a_carriage_return_is_a_line_break_and_a_tab_is_expanded() -> None:
    """Neither is a newline, and both corrupt a row: a terminal draws \\r over
    the line it is on and a tab eight columns wide where len() counted one."""

    frame = pd.DataFrame([{"x": "a\tb", "y": "p\rq"}])
    lines = tables.format_table(frame).splitlines()
    assert [line.split(" | ")[1].rstrip() for line in lines[2:]] == ["p", "q"]
    assert lines[2].startswith("a       b")


def test_a_character_that_draws_as_nothing_does_not_split_a_cell() -> None:
    """str.splitlines would split on \\u2028 and \\x1c; the cell would go tall
    for a character the reader cannot see."""

    frame = pd.DataFrame([{"x": "a b\x1cc"}])
    # Counted with "\n", not splitlines(), which splits on both of them itself.
    assert tables.format_table(frame).count("\n") == 2


# --- add_columns, the one argument every table takes ----------------------


def test_the_registry_table_carries_the_source_file_it_was_asked_for(
    example_checks: None,
) -> None:
    table = registry_tables.print_registry(add_columns=["source_file"]).set_index("code")
    assert table.loc["AGE_NEGATIVE", "source_file"].endswith("check_age.py")


def test_the_registry_table_carries_the_source_file_beside_the_rule_columns(
    example_checks: None,
) -> None:
    table = registry_tables.print_registry(
        [], add_columns=["source_file", "effective_state"]
    ).set_index("code")
    assert table.loc["AGE_NEGATIVE", "source_file"].endswith("check_age.py")
    assert table.loc["AGE_NEGATIVE", "effective_state"] == "DEFAULT (ON)"


def test_the_rules_table_carries_the_source_file_it_was_asked_for(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.print_rules(
        [a_rule(source_file="here.yaml")], add_columns=["source_file"]
    )
    assert list(table["source_file"]) == ["here.yaml"]


def test_the_rules_table_prints_the_message_that_says_why_a_rule_exists(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A rule nobody can justify is a rule nobody dares delete."""

    make_check("A_CODE")
    table = registry_tables.print_rules([a_rule()])
    assert list(table["message"]) == ["why the rule exists"]
    assert "why the rule exists" in capsys.readouterr().out


@pytest.mark.parametrize(
    "call, subject",
    [
        pytest.param(lambda: registry_tables.get_registry_table(add_columns=["nope"]),
                     "the registry table", id="registry-table"),
        pytest.param(lambda: registry_tables.print_registry(add_columns=["nope"]),
                     "the registry table", id="print-registry"),
        pytest.param(lambda: registry_tables.print_rules([], add_columns=["nope"]),
                     "the rules table", id="rules-table"),
    ],
)
def test_an_unknown_extra_column_names_the_table_and_what_is_on_offer(
    example_checks: None, call: object, subject: str
) -> None:
    with pytest.raises(ValueError) as raised:
        call()  # type: ignore[operator]
    assert f"cannot be used for {subject}" in str(raised.value)
    assert "source_file" in str(raised.value)


def test_a_column_asked_for_twice_is_refused(example_checks: None) -> None:
    with pytest.raises(ValueError, match=r"add_columns \['source_file'\] cannot be used"):
        registry_tables.get_registry_table(add_columns=["source_file", "source_file"])


def test_could_be_overridden_by_is_not_on_offer_where_there_are_no_rules_to_read(
    example_checks: None,
) -> None:
    """Only the tables handed the rules can answer that, so only they offer it."""

    with pytest.raises(ValueError, match="cannot be used for the registry table"):
        registry_tables.get_registry_table(add_columns=["could_be_overridden_by"])


# --- table titles -----------------------------------------------------------


def test_the_registry_title_counts_the_checks_and_the_rules(
    example_checks: None, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    """Every print_ writes its own heading, so an entry point printing three
    tables does not label them itself -- and the heading carries what the call was
    given, because "which table is this" and "what did I ask for" are one question
    once two are on screen."""

    path = tmp_path / "r.yaml"
    path.write_text(
        "- name: off_everywhere\n  message: \"m\"\n  action: disable\n"
        "  codes: [AGE_NOT_INTEGER]\n  match: all\n",
        encoding="utf-8",
    )
    registry_tables.print_registry(rules=reg.load_rules([str(path)]))
    assert capsys.readouterr().out.splitlines()[0] == (
        "== Registry: 11 check(s), 1 rule(s) considered ==")


def test_the_registry_title_omits_rules_it_was_not_given(
    example_checks: None, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_tables.print_registry()
    assert capsys.readouterr().out.splitlines()[0] == "== Registry: 11 check(s) =="


def test_a_title_is_written_even_when_there_is_nothing_to_show(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """The heading comes first: "nothing here" is only an answer if the reader
    knows which question it answers."""

    registry_tables.print_registry()
    assert capsys.readouterr().out == "== Registry: 0 check(s) ==\nNo checks registered.\n"


def test_the_rules_title_counts_what_was_loaded(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_tables.print_rules([])
    assert capsys.readouterr().out.splitlines()[0] == "== Rules: 0 loaded =="


# --- dropping columns from the check tables ---------------------------------


def test_the_registry_table_drops_what_it_is_asked_to(example_checks: None) -> None:
    table = registry_tables.get_registry_table(drop_columns=["message", "default"])
    assert list(table.columns) == ["code", "layer", "depends_on"]


def test_dropping_a_registry_column_leaves_the_added_ones_working(
    example_checks: None, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    """`could_be_overridden_by` is computed from this table's own `code`, so the
    drop happens after it is built rather than before."""

    path = tmp_path / "r.yaml"
    path.write_text(
        "- name: off_everywhere\n  message: \"m\"\n  action: disable\n"
        "  codes: [AGE_NOT_INTEGER]\n  match: all\n",
        encoding="utf-8",
    )
    table = registry_tables.print_registry(
        rules=reg.load_rules([str(path)]),
        add_columns=["could_be_overridden_by"],
        drop_columns=["code", "message"],
    )
    assert list(table.columns) == ["layer", "default", "depends_on",
                                   "could_be_overridden_by"]
    assert "off_everywhere (disable)" in capsys.readouterr().out


def test_dropping_a_column_the_table_is_sorted_by_still_works(
    example_checks: None,
) -> None:
    """Regression: the frame was built with only the kept columns and then sorted
    by `layer` and `code`, so dropping either raised a bare KeyError -- against a
    docstring that says a base column can still be dropped."""

    assert list(registry_tables.get_registry_table(drop_columns=["code"]).columns) == [
        "layer", "default", "message", "depends_on"]
    assert list(registry_tables.get_registry_table(drop_columns=["layer"]).columns) == [
        "code", "default", "message", "depends_on"]


def test_dropping_the_sort_column_leaves_the_rows_in_sorted_order(
    example_checks: None,
) -> None:
    """The sort still happens; only the column it read is gone from the output."""

    with_code = registry_tables.get_registry_table()
    without = registry_tables.get_registry_table(drop_columns=["code"])
    assert list(without["layer"]) == list(with_code["layer"])
    assert list(without["message"]) == list(with_code["message"])


def test_an_unknown_registry_drop_name_is_refused(example_checks: None) -> None:
    with pytest.raises(ValueError) as raised:
        registry_tables.get_registry_table(drop_columns=["messages"])
    assert str(raised.value) == (
        "drop_columns ['messages'] cannot be used for the registry table. Each name "
        "must be asked for once and be one of: code, layer, default, message, depends_on."
    )


def test_the_rules_table_is_available_without_printing(
    fresh_registry: None, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    """Every other table has a builder beside its printer; this one did not."""

    make_check("A_CODE")
    path = tmp_path / "r.yaml"
    path.write_text(
        "- name: off_everywhere\n  message: \"m\"\n  action: disable\n"
        "  codes: [A_CODE]\n  match: all\n",
        encoding="utf-8",
    )
    table = registry_tables.get_rules_table(reg.load_rules([str(path)]))
    assert capsys.readouterr().out == ""
    assert list(table["name"]) == ["off_everywhere"]
    assert list(table.columns) == ["name", "action", "codes_hit_count", "match", "message"]


def test_the_rules_table_drops_and_adds_columns(fresh_registry: None, tmp_path: Any) -> None:
    make_check("A_CODE")
    path = tmp_path / "r.yaml"
    path.write_text(
        "- name: off_everywhere\n  message: \"m\"\n  action: disable\n"
        "  codes: [A_CODE]\n  match: all\n",
        encoding="utf-8",
    )
    table = registry_tables.get_rules_table(
        reg.load_rules([str(path)]), add_columns=["source_file"],
        drop_columns=["match", "message"])
    assert list(table.columns) == ["name", "action", "codes_hit_count", "source_file"]


def test_a_duplicated_column_label_renders_each_column_s_own_value() -> None:
    """Regression: cells were read by label, so a duplicated label handed back a
    Series and every cell printed its repr -- `a 1 / a 2 / Name: 0, dtype: int64`."""

    frame = pd.DataFrame([[1, 2], [3, 4]], columns=["a", "a"])
    assert tables.format_table(frame).splitlines() == [
        "a | a",
        "--+--",
        "1 | 2",
        "3 | 4",
    ]


def test_a_duplicated_label_in_wrap_columns_wraps_both_columns() -> None:
    frame = pd.DataFrame([["one two", "three four"]], columns=["a", "a"])
    lines = tables.format_table(frame, wrap_columns={"a": 5}).splitlines()
    assert lines[2:] == ["one | three", "two | four "]


def test_integers_stay_integers_in_an_all_numeric_frame() -> None:
    """Regression: rows came from iterrows, which upcasts a whole row to float
    when every column is numeric, so the integer column printed `1.0`."""

    frame = pd.DataFrame({"n": [1, 2], "x": [2.5, 3.0]})
    assert tables.format_table(frame).splitlines()[2:] == ["1 | 2.5", "2 | 3.0"]
