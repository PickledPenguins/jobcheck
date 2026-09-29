"""Unit checks: the shared table helpers and the registry and rule tables."""

from __future__ import annotations

from typing import Any

import numpy
import pandas as pd
import pytest

from conftest import make_check
from jobcheck import registry as reg
from jobcheck import registry_tables
from jobcheck import tables
from jobcheck.rules import _MatchCriterion

pytestmark = pytest.mark.fast


def a_rule(name: str = "r", action: str = "disable", codes: list[str] | None = None,
           source_file: str = "rules.yaml") -> reg.Rule:
    return reg.Rule(name=name, action=action, codes=codes or ["A_CODE"],
                            criteria=[], match_all=True, source_file=source_file, message="why the rule exists")


# --- is_null ----------------------------------------------------------------


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
    "not null".

    Regression for the ndarray case, which the old isinstance list did not cover:
    bool() on that array raised "truth value of an array is ambiguous"."""

    assert tables.is_null(value) is False


# --- get_registry_table -----------------------------------------------------


def test_registry_table_has_the_base_columns(example_checks: None) -> None:
    assert list(registry_tables.registry_table().columns) == [
        "code", "layer", "default", "message", "depends_on", "source_file",
        "could_be_overridden_by",
    ]


def test_registry_table_is_sorted_by_layer_then_code(example_checks: None) -> None:
    table = registry_tables.registry_table()
    assert list(table["code"]) == [
        "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT", "ROW_ALL_NULL",
        "AGE_NOT_A_NUMBER", "DATES_OUT_OF_ORDER", "EMAIL_MISSING_AT",
        "AGE_NEGATIVE", "AGE_NOT_INTEGER", "AGE_TOO_HIGH", "EMAIL_DOMAIN_INVALID",
    ]
    assert list(table["layer"]) == [0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 2]


def test_registry_table_computes_layers_for_checks_registered_directly(
    fresh_registry: None,
) -> None:
    """Layers are set when the order is computed, which load_checks does and a
    plain @register_check does not; the table showed every such check at 0."""

    make_check("BASE")
    make_check("DEPENDENT", depends_on=["BASE"])
    table = registry_tables.registry_table()
    assert table[["code", "layer"]].values.tolist() == [["BASE", 0], ["DEPENDENT", 1]]


def test_registry_table_renders_the_default_as_on_or_off(example_checks: None) -> None:
    table = registry_tables.registry_table().set_index("code")
    assert table.loc["AGE_NEGATIVE", "default"] == "ON"
    assert table.loc["AGE_NOT_INTEGER", "default"] == "OFF"


def test_registry_table_joins_dependencies_and_dashes_when_there_are_none(
    fresh_registry: None,
) -> None:
    make_check("ROOT")
    make_check("OTHER")
    make_check("LEAF", depends_on=["ROOT", "OTHER"])
    table = registry_tables.registry_table().set_index("code")
    assert table.loc["LEAF", "depends_on"] == "ROOT; OTHER"
    assert table.loc["ROOT", "depends_on"] == "-"


def test_registry_table_of_an_empty_registry_has_columns_and_no_rows(fresh_registry: None) -> None:
    table = registry_tables.registry_table()
    assert table.empty
    assert list(table.columns) == [
        "code", "layer", "default", "message", "depends_on", "source_file",
        "could_be_overridden_by",
    ]


def test_could_be_overridden_by_names_each_rule_with_its_action_in_load_order(
    fresh_registry: None,
) -> None:
    make_check("A_CODE")
    rules = [a_rule("first", action="enable"), a_rule("second", action="disable")]
    table = registry_tables.registry_table(rules).set_index("code")
    assert table.loc["A_CODE", "could_be_overridden_by"] == "first (enable); second (disable)"


def test_could_be_overridden_by_is_a_dash_for_an_unreferenced_code(fresh_registry: None) -> None:
    make_check("A_CODE")
    make_check("UNTOUCHED")
    table = registry_tables.registry_table([a_rule()]).set_index("code")
    assert table.loc["UNTOUCHED", "could_be_overridden_by"] == "-"


def test_the_registry_without_rules_still_renders_that_column(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.registry_table().set_index("code")
    assert table.loc["A_CODE", "could_be_overridden_by"] == "-"


# --- rules_table ---------------------------------------------------


def test_rules_table_is_one_row_per_rule(fresh_registry: None) -> None:
    make_check("A_CODE")
    make_check("B_CODE")
    table = registry_tables.rules_table([a_rule("one", codes=["A_CODE", "B_CODE"]),
                                         a_rule("two", action="enable")])
    assert list(table["name"]) == ["one", "two"]
    assert list(table["action"]) == ["disable", "enable"]
    assert list(table["codes_hit_count"]) == [2, 1]


def test_match_all_renders_as_all(fresh_registry: None) -> None:
    make_check("A_CODE")
    assert registry_tables.rules_table([a_rule()])["match"][0] == "all"


def test_criteria_render_compactly(fresh_registry: None) -> None:
    import re as _re

    make_check("A_CODE")
    rule = reg.Rule(
        name="r", action="disable", codes=["A_CODE"],
        criteria=[_MatchCriterion("source_system", "^LEGACY_", _re.compile("^LEGACY_")),
                  _MatchCriterion("record_type", "^BATCH$", _re.compile("^BATCH$"))],
        match_all=False, message="why the rule exists",
    )
    assert registry_tables.rules_table([rule])["match"][0] == (
        "source_system~=/^LEGACY_/; record_type~=/^BATCH$/"
    )


# --- what the tables carry -------------------------------------------------


def test_the_registry_table_carries_the_source_file_it_was_asked_for(
    example_checks: None,
) -> None:
    table = registry_tables.registry_table().set_index("code")
    assert table.loc["AGE_NEGATIVE", "source_file"].endswith("check_age.py")


def test_the_rules_table_carries_the_source_file_it_was_asked_for(fresh_registry: None) -> None:
    make_check("A_CODE")
    table = registry_tables.rules_table([a_rule(source_file="here.yaml")])
    assert list(table["source_file"]) == ["here.yaml"]


def test_the_rules_table_carries_the_message_that_says_why_a_rule_exists(
    fresh_registry: None,
) -> None:
    """A rule nobody can justify is a rule nobody dares delete."""

    make_check("A_CODE")
    table = registry_tables.rules_table([a_rule()])
    assert list(table["message"]) == ["why the rule exists"]


def test_the_rules_table_is_data_and_prints_nothing(
    fresh_registry: None, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    make_check("A_CODE")
    path = tmp_path / "r.yaml"
    path.write_text(
        "- name: off_everywhere\n  message: \"m\"\n  action: disable\n"
        "  codes: [A_CODE]\n  match: all\n",
        encoding="utf-8",
    )
    table = registry_tables.rules_table(reg.load_rules([str(path)]))
    assert capsys.readouterr().out == ""
    assert list(table["name"]) == ["off_everywhere"]
    assert list(table.columns) == ["name", "action", "codes_hit_count", "codes", "match", "message",
                                   "source_file"]
