"""Unit checks: rule parsing, every load-time rejection, matching, precedence."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from conftest import enabled_only, make_check
from jobcheck import registry as reg
from jobcheck import engine
from jobcheck import registry_tables

pytestmark = pytest.mark.fast

GLOBAL_DISABLE = """
- name: "kill_it"
  message: "why the rule exists"
  action: disable
  codes: [A_CODE]
  match: all
"""


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.fixture
def one_code(fresh_registry: None) -> None:
    make_check("A_CODE")


def test_rule_fields_are_parsed(one_code: None, tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "r.yaml",
        '- name: "n"\n  message: "d"\n  action: enable\n  codes: [A_CODE]\n'
        '  match:\n    - column: email\n      pattern: "x$"\n',
    )
    rule = reg.load_overrides([path])[0]
    assert (rule.name, rule.action, rule.codes, rule.message) == ("n", "enable", ["A_CODE"], "d")
    assert (rule.criteria[0].column, rule.criteria[0].pattern) == ("email", "x$")
    assert rule.match_all is False


def test_match_all_sets_the_flag_and_leaves_criteria_empty(one_code: None, tmp_path: Path) -> None:
    rule = reg.load_overrides([write(tmp_path, "r.yaml", GLOBAL_DISABLE)])[0]
    assert rule.match_all is True
    assert rule.criteria == []


def test_source_file_records_the_file_the_rule_came_from(one_code: None, tmp_path: Path) -> None:
    path = write(tmp_path, "rules.yaml", GLOBAL_DISABLE)
    assert reg.load_overrides([path])[0].source_file == path


def test_a_rule_without_a_message_is_refused(one_code: None, tmp_path: Path) -> None:
    """A rule nobody can justify is a rule nobody dares delete, so say why."""

    body = '- name: "silent"\n  action: disable\n  codes: [A_CODE]\n  match: all\n'
    with pytest.raises(ValueError) as excinfo:
        reg.load_overrides([write(tmp_path, "r.yaml", body)])
    assert "'message' must be the text saying why the rule exists" in str(excinfo.value)


def test_an_unknown_key_is_rejected_rather_than_silently_ignored(
    one_code: None, tmp_path: Path
) -> None:
    """A misspelled key in a hand-edited file is a setting that does nothing."""

    path = write(tmp_path, "r.yaml", GLOBAL_DISABLE + "  bogus_key: 1\n")
    with pytest.raises(ValueError) as excinfo:
        reg.load_overrides([path])
    assert "unknown key(s) bogus_key" in str(excinfo.value)
    assert "Allowed: action, codes, match, message, name." in str(excinfo.value)


def test_every_documented_key_is_accepted(one_code: None, tmp_path: Path) -> None:
    path = write(
        tmp_path, "r.yaml",
        '- name: "full"\n  message: "d"\n  action: disable\n  codes: [A_CODE]\n'
        "  match: all\n",
    )
    assert reg.load_overrides([path])[0].message == "d"


def test_empty_file_contributes_no_rules(one_code: None, tmp_path: Path) -> None:
    assert reg.load_overrides([write(tmp_path, "empty.yaml", "")]) == []


def test_missing_file_raises_file_not_found(one_code: None, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        reg.load_overrides([str(tmp_path / "absent.yaml")])


@pytest.mark.parametrize(
    "body, expected",
    [
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: []\n',
            "'match' is an empty list. Use 'match: all' if you really mean every row.",
            id="empty-match-list",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n',
            "missing 'match'. Use 'match: all' to apply the rule to every row.",
            id="missing-match",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: al\n',
            "'match' must be a list of criteria or the literal 'all', got 'al'.",
            id="match-typo",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: 7\n',
            "'match' must be a list of criteria or the literal 'all', got int.",
            id="match-wrong-type",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: ["oops"]\n',
            "each 'match' entry must be a mapping with 'column' and 'pattern'.",
            id="criterion-not-a-mapping",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match:\n    - column: email\n',
            "'match' entry {'column': 'email'} needs both 'column' and 'pattern'.",
            id="criterion-missing-pattern",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match:\n'
            "    - column: 7\n      pattern: \"x\"\n",
            "'column' and 'pattern' must both be strings in {'column': 7, 'pattern': 'x'}.",
            id="criterion-wrong-types",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match:\n'
            '    - column: email\n      pattern: "([unclosed"\n',
            "invalid regex '([unclosed' for column 'email': unterminated character set at position 1",
            id="invalid-regex",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: turn_on\n  codes: [A_CODE]\n  match: all\n',
            "'action' must be exactly 'enable' or 'disable', got 'turn_on'.",
            id="bad-action",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  codes: [A_CODE]\n  match: all\n',
            "'action' must be exactly 'enable' or 'disable', got None.",
            id="missing-action",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: []\n  match: all\n',
            "'codes' must be a non-empty list of code strings.",
            id="empty-codes",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: A_CODE\n  match: all\n',
            "'codes' must be a non-empty list of code strings.",
            id="codes-not-a-list",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [7]\n  match: all\n',
            "'codes' must be a non-empty list of code strings.",
            id="codes-not-strings",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [NO_SUCH_CODE]\n  match: all\n',
            "unknown code 'NO_SUCH_CODE'. Load the check file that defines it before "
            "loading overrides, or fix the code.",
            id="unknown-code",
        ),
        pytest.param(
            '- name: ""\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
            "every rule needs a non-empty string 'name'.",
            id="empty-name",
        ),
        pytest.param(
            "- action: disable\n  codes: [A_CODE]\n  match: all\n",
            "every rule needs a non-empty string 'name'.",
            id="missing-name",
        ),
        pytest.param(
            '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n  message: 7\n',
            "'message' must be the text saying why the rule exists",
            id="message-not-a-string",
        ),
        pytest.param(
            "- just_a_string\n",
            "each rule must be a mapping, got str.",
            id="rule-not-a-mapping",
        ),
        pytest.param(
            "rules:\n  - name: r\n",
            "override files must contain a flat top-level list of rules (no 'rules:' key), got dict.",
            id="nested-under-a-key",
        ),
    ],
)
def test_malformed_rule_is_rejected_at_load_time(
    one_code: None, tmp_path: Path, body: str, expected: str
) -> None:
    path = write(tmp_path, "bad.yaml", body)
    with pytest.raises(ValueError) as excinfo:
        reg.load_overrides([path])
    assert expected in str(excinfo.value)
    assert path in str(excinfo.value)


def test_duplicate_rule_name_within_one_file_is_rejected(one_code: None, tmp_path: Path) -> None:
    path = write(tmp_path, "dup.yaml", GLOBAL_DISABLE + GLOBAL_DISABLE)
    with pytest.raises(ValueError, match=r"Duplicate override rule name 'kill_it'"):
        reg.load_overrides([path])


def test_duplicate_rule_name_across_files_names_both_files(one_code: None, tmp_path: Path) -> None:
    first = write(tmp_path, "a.yaml", GLOBAL_DISABLE)
    second = write(tmp_path, "b.yaml", GLOBAL_DISABLE)
    with pytest.raises(ValueError) as excinfo:
        reg.load_overrides([first, second])
    message = str(excinfo.value)
    assert f"defined in {first} and again in {second}" in message


def test_a_sorted_list_of_files_loads_in_that_order(one_code: None, tmp_path: Path) -> None:
    """Alphabetical order is the caller's to choose: the loader takes the list as given."""

    second = write(tmp_path, "02_second.yaml", GLOBAL_DISABLE.replace("kill_it", "second"))
    first = write(tmp_path, "01_first.yaml", GLOBAL_DISABLE.replace("kill_it", "first"))
    assert [r.name for r in reg.load_overrides(sorted([second, first]))] == ["first", "second"]


def test_loading_no_files_returns_nothing(one_code: None) -> None:
    assert reg.load_overrides([]) == []


def test_load_overrides_keeps_the_given_order_not_alphabetical(
    one_code: None, tmp_path: Path
) -> None:
    first = write(tmp_path, "a.yaml", GLOBAL_DISABLE.replace("kill_it", "alpha"))
    second = write(tmp_path, "z.yaml", GLOBAL_DISABLE.replace("kill_it", "zulu"))
    rules = reg.load_overrides([second, first])
    assert [r.name for r in rules] == ["zulu", "alpha"]


def test_load_overrides_spans_directories(one_code: None, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    a = write(left, "a.yaml", GLOBAL_DISABLE.replace("kill_it", "from_left"))
    b = write(right, "b.yaml", GLOBAL_DISABLE.replace("kill_it", "from_right"))
    assert [r.name for r in reg.load_overrides([a, b])] == ["from_left", "from_right"]


def test_list_rule_codes_returns_the_exact_codes(one_code: None, tmp_path: Path) -> None:
    make_check("B_CODE")
    path = write(
        tmp_path, "r.yaml", '- name: "two"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE, B_CODE]\n  match: all\n'
    )
    rules = reg.load_overrides([path])
    assert registry_tables.list_rule_codes("two", rules) == ["A_CODE", "B_CODE"]


def test_list_rule_codes_prints_the_rule(one_code: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rules = reg.load_overrides([write(tmp_path, "r.yaml", GLOBAL_DISABLE)])
    registry_tables.list_rule_codes("kill_it", rules)
    assert capsys.readouterr().out == "kill_it (disable) -> A_CODE\n"


def test_list_rule_codes_unknown_name_lists_what_is_loaded(one_code: None, tmp_path: Path) -> None:
    rules = reg.load_overrides([write(tmp_path, "r.yaml", GLOBAL_DISABLE)])
    with pytest.raises(ValueError) as excinfo:
        registry_tables.list_rule_codes("nope", rules)
    assert str(excinfo.value) == "No override rule named 'nope'. Loaded rules: kill_it"


def test_list_rule_codes_with_no_rules_loaded_says_so(one_code: None) -> None:
    with pytest.raises(ValueError, match=r"Loaded rules: \(none loaded\)"):
        registry_tables.list_rule_codes("nope", [])


# --- matching and precedence ------------------------------------------------


def rule(name: str, action: str, codes: list[str], criteria: list[tuple[str, str]] | None,
         ) -> reg.OverrideRule:
    """Build a rule directly, bypassing YAML, to isolate matching behavior."""

    import re

    made = [reg.MatchCriterion(c, p, re.compile(p)) for c, p in (criteria or [])]
    return reg.OverrideRule(name=name, action=action, codes=codes, criteria=made,
                            match_all=criteria is None, message="why the rule exists")


def test_default_state_is_used_when_no_rule_matches(fresh_registry: None) -> None:
    make_check("ON_BY_DEFAULT")
    make_check("OFF_BY_DEFAULT", default_enabled=False)
    state = enabled_only(engine.resolve_enabled_state(pd.Series({"age": 1}), []))
    assert state == {"ON_BY_DEFAULT": True, "OFF_BY_DEFAULT": False}


def test_enable_rule_turns_on_an_off_by_default_code(fresh_registry: None) -> None:
    make_check("OFF_BY_DEFAULT", default_enabled=False)
    state = enabled_only(engine.resolve_enabled_state(
        pd.Series({"age": 1}), [rule("on", "enable", ["OFF_BY_DEFAULT"], None)]
    ))
    assert state["OFF_BY_DEFAULT"] is True


def test_all_criteria_must_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    two = rule("both", "disable", ["A_CODE"], [("source_system", "^LEGACY_"), ("record_type", "^BATCH$")])
    matching = pd.Series({"source_system": "LEGACY_A", "record_type": "BATCH"})
    half = pd.Series({"source_system": "LEGACY_A", "record_type": "STREAM"})
    assert enabled_only(engine.resolve_enabled_state(matching, [two]))["A_CODE"] is False
    assert enabled_only(engine.resolve_enabled_state(half, [two]))["A_CODE"] is True


def test_pattern_is_a_search_not_a_full_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    unanchored = rule("mid", "disable", ["A_CODE"], [("email", "internal")])
    assert enabled_only(engine.resolve_enabled_state(pd.Series({"email": "qa@internal.test"}), [unanchored]))["A_CODE"] is False


def test_absent_column_does_not_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    on_email = rule("r", "disable", ["A_CODE"], [("email", ".*")])
    assert enabled_only(engine.resolve_enabled_state(pd.Series({"age": 1}), [on_email]))["A_CODE"] is True


def test_null_value_does_not_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    on_email = rule("r", "disable", ["A_CODE"], [("email", ".*")])
    assert enabled_only(engine.resolve_enabled_state(pd.Series({"email": None}), [on_email]))["A_CODE"] is True


def test_non_string_values_are_matched_as_text(fresh_registry: None) -> None:
    make_check("A_CODE")
    numeric = rule("r", "disable", ["A_CODE"], [("age", "^41$")])
    assert enabled_only(engine.resolve_enabled_state(pd.Series({"age": 41}), [numeric]))["A_CODE"] is False


def test_last_matching_rule_wins(fresh_registry: None) -> None:
    make_check("A_CODE", default_enabled=False)
    rules = [rule("on", "enable", ["A_CODE"], None), rule("off", "disable", ["A_CODE"], None)]
    assert enabled_only(engine.resolve_enabled_state(pd.Series({"age": 1}), rules))["A_CODE"] is False
    assert enabled_only(
        engine.resolve_enabled_state(pd.Series({"age": 1}), list(reversed(rules)))
    )["A_CODE"] is True


def test_a_non_matching_later_rule_does_not_override(fresh_registry: None) -> None:
    make_check("A_CODE", default_enabled=False)
    rules = [
        rule("on", "enable", ["A_CODE"], None),
        rule("off", "disable", ["A_CODE"], [("email", "@internal")]),
    ]
    assert enabled_only(engine.resolve_enabled_state(pd.Series({"email": "a@b.com"}), rules))["A_CODE"] is True


def test_one_rule_switches_several_codes(fresh_registry: None) -> None:
    make_check("FIRST")
    make_check("SECOND")
    state = enabled_only(engine.resolve_enabled_state(
        pd.Series({"age": 1}), [rule("both", "disable", ["FIRST", "SECOND"], None)]
    ))
    assert state == {"FIRST": False, "SECOND": False}


def test_codes_that_are_not_registered_are_ignored_by_resolution(fresh_registry: None) -> None:
    make_check("A_CODE")
    state = enabled_only(engine.resolve_enabled_state(
        pd.Series({"age": 1}), [rule("stale", "disable", ["GONE_CODE"], None)]
    ))
    assert state == {"A_CODE": True}


def test_a_null_cell_never_matches_a_rule(fresh_registry: None) -> None:
    """A blank cell is not the empty string, and a rule matching on it would fire
    on every row whose column happens to be missing.

    Written against a surviving mutant: ``value is None or is_null(value)``
    became ``and``, which makes a NaN cell render as the text "nan" and match a
    pattern meant for real values.
    """

    import pandas as pd

    from jobcheck import rules

    row = pd.Series({"email": None, "age": float("nan"), "name": "real"})
    assert rules.cell_text(row, "email") is None
    assert rules.cell_text(row, "age") is None
    assert rules.cell_text(row, "absent") is None
    assert rules.cell_text(row, "name") == "real"
