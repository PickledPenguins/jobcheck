"""Unit checks: rule parsing, every load-time rejection, matching, precedence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import PROJECT_ROOT, enabled_only, make_check
from jobcheck import registry as reg
from jobcheck import rules
from jobcheck import engine
from jobcheck import views

from jobcheck.results import Outcome
from jobcheck.rules import _MatchCriterion

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
    rule = reg.load_rules([path])[0]
    assert (rule.name, rule.action, rule.codes, rule.message) == ("n", "enable", ["A_CODE"], "d")
    assert (rule.criteria[0].column, rule.criteria[0].pattern) == ("email", "x$")
    assert rule.match_all is False


def test_match_all_sets_the_flag_and_leaves_criteria_empty(one_code: None, tmp_path: Path) -> None:
    rule = reg.load_rules([write(tmp_path, "r.yaml", GLOBAL_DISABLE)])[0]
    assert rule.match_all is True
    assert rule.criteria == []


def test_source_file_records_the_file_the_rule_came_from(one_code: None, tmp_path: Path) -> None:
    path = write(tmp_path, "rules.yaml", GLOBAL_DISABLE)
    assert reg.load_rules([path])[0].source_file == path


def test_a_rule_without_a_message_is_refused(one_code: None, tmp_path: Path) -> None:
    """A rule nobody can justify is a rule nobody dares delete, so say why."""

    body = '- name: "silent"\n  action: disable\n  codes: [A_CODE]\n  match: all\n'
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([write(tmp_path, "r.yaml", body)])
    assert "'message' must be the text saying why the rule exists" in str(excinfo.value)


def test_an_unknown_key_is_rejected_rather_than_silently_ignored(
    one_code: None, tmp_path: Path
) -> None:
    """A misspelled key in a hand-edited file is a setting that does nothing."""

    path = write(tmp_path, "r.yaml", GLOBAL_DISABLE + "  bogus_key: 1\n")
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([path])
    assert "unknown key(s) 'bogus_key'" in str(excinfo.value)
    assert "Allowed: 'action', 'codes', 'match', 'message', 'name'." in str(excinfo.value)

    # Two typos are listed together, sorted, so one run reports both.
    path = write(tmp_path, "r2.yaml", GLOBAL_DISABLE + "  zzz: 1\n  bogus_key: 1\n")
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([path])
    assert "unknown key(s) 'bogus_key', 'zzz'." in str(excinfo.value)


def test_a_key_yaml_reads_as_a_bool_is_named_rather_than_crashing(
    one_code: None, tmp_path: Path
) -> None:
    """YAML 1.1 reads `on:` as True and `2:` as an int. Joining them raised a bare
    TypeError once; now each shows as Python writes it, so the unquoted `True`
    says YAML read a bool where the file said `on`."""

    path = write(tmp_path, "r.yaml", GLOBAL_DISABLE + "  on: 1\n  2: x\n")
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([path])
    assert str(excinfo.value) == (
        f"rule 'kill_it' in {path}: unknown key(s) 2, True. "
        "Allowed: 'action', 'codes', 'match', 'message', 'name'.")


def test_every_documented_key_is_accepted(one_code: None, tmp_path: Path) -> None:
    path = write(
        tmp_path, "r.yaml",
        '- name: "full"\n  message: "d"\n  action: disable\n  codes: [A_CODE]\n'
        "  match: all\n",
    )
    assert reg.load_rules([path])[0].message == "d"


def test_empty_file_contributes_no_rules(one_code: None, tmp_path: Path) -> None:
    assert reg.load_rules([write(tmp_path, "empty.yaml", "")]) == []


def test_base_dir_anchors_a_relative_rule_path(one_code: None, tmp_path: Path,
                                               monkeypatch: Any) -> None:
    write(tmp_path, "rules.yaml", GLOBAL_DISABLE)
    started_in = tmp_path / "started-in"
    started_in.mkdir()
    monkeypatch.chdir(started_in)
    assert [rule.name for rule in reg.load_rules(["rules.yaml"], base_dir=tmp_path)] == ["kill_it"]


def test_a_rule_records_the_path_the_caller_wrote(one_code: None, tmp_path: Path) -> None:
    """source_file is printed beside the rule, so it stays the caller's own
    text: an absolute path resolved out of base_dir would be this machine's."""

    write(tmp_path, "rules.yaml", GLOBAL_DISABLE)
    rule = reg.load_rules(["rules.yaml"], base_dir=tmp_path)[0]
    assert rule.source_file == "rules.yaml"


def test_missing_file_is_refused_the_way_a_missing_check_file_is(one_code: None,
                                                                 tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No rule file at"):
        reg.load_rules([str(tmp_path / "absent.yaml")])


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
            '    - column: email\n      pattern: "x"\n      negate: true\n      flags: i\n',
            "'match' entry {'column': 'email', 'pattern': 'x', 'negate': True, 'flags': 'i'} "
            "has unknown key(s) 'flags', 'negate'. A criterion holds only 'column' and "
            "'pattern'.",
            id="criterion-unknown-key",
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
            "'codes' must be a non-empty list of code strings, got [].",
            id="empty-codes",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: A_CODE\n  match: all\n',
            "'codes' must be a non-empty list of code strings, got 'A_CODE'.",
            id="codes-not-a-list",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [7]\n  match: all\n',
            "'codes' must be a non-empty list of code strings, got [7].",
            id="codes-not-strings",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [ON]\n  match: all\n',
            "'codes' must be a non-empty list of code strings, got [True].",
            id="codes-an-unquoted-yaml-boolean",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [NO_SUCH_CODE]\n  match: all\n',
            "unknown code 'NO_SUCH_CODE'. Load the check file that defines it before "
            "loading rules, or fix the code.",
            id="unknown-code",
        ),
        pytest.param(
            '- name: ""\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
            "rule 1: every rule needs a non-empty string 'name', got ''.",
            id="empty-name",
        ),
        pytest.param(
            "- action: disable\n  codes: [A_CODE]\n  match: all\n",
            "rule 1: every rule needs a non-empty string 'name', got None.",
            id="missing-name",
        ),
        pytest.param(
            '- name: ok\n  message: m\n  action: disable\n  codes: [A_CODE]\n  match: all\n'
            '- name: off\n  message: m\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
            "rule 2: every rule needs a non-empty string 'name', got False.",
            id="name-an-unquoted-yaml-boolean-in-the-second-rule",
        ),
        pytest.param(
            '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n  message: 7\n',
            "'message' must be the text saying why the rule exists, got 7.",
            id="message-not-a-string",
        ),
        pytest.param(
            '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n  message: yes\n',
            "'message' must be the text saying why the rule exists, got True.",
            id="message-an-unquoted-yaml-boolean",
        ),
        pytest.param(
            "- just_a_string\n",
            "each rule must be a mapping, got str.",
            id="rule-not-a-mapping",
        ),
        pytest.param(
            "rules:\n  - name: r\n",
            "rule files must contain a flat top-level list of rules (no 'rules:' key), got dict.",
            id="nested-under-a-key",
        ),
    ],
)
def test_malformed_rule_is_rejected_at_load_time(
    one_code: None, tmp_path: Path, body: str, expected: str
) -> None:
    path = write(tmp_path, "bad.yaml", body)
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([path])
    assert expected in str(excinfo.value)
    assert path in str(excinfo.value)
    # A rule that got as far as having a name is named in the message, so the
    # reader can find it in a file of many.
    if 'name: "r"' in body:
        assert str(excinfo.value).startswith(f"rule 'r' in {path}: ")


def test_a_key_given_twice_in_one_rule_is_refused_rather_than_the_last_winning(
    fresh_registry: None, tmp_path: Path
) -> None:
    """PyYAML keeps the second `codes:` and says nothing, so a rule written for A
    with `codes: [B]` appended later would load as a rule about B alone."""

    make_check("A_CODE")
    make_check("B_CODE")
    path = write(tmp_path, "r.yaml",
                 '- name: "r"\n  message: "m"\n  action: disable\n'
                 "  codes: [A_CODE]\n  codes: [B_CODE]\n  match: all\n")
    with pytest.raises(ValueError) as raised:
        reg.load_rules([path])
    assert str(raised.value) == (
        f"{path}: key 'codes' appears twice in one mapping, on lines 4 and 5. "
        "YAML would keep only the last; remove one.")


def test_a_key_repeated_on_one_line_is_refused_too(one_code: None, tmp_path: Path) -> None:
    """A flow mapping puts both on one line, so the line number cannot be what
    tells the first from the second."""

    path = write(tmp_path, "r.yaml",
                 '- {name: "r", name: "s", message: "m", action: disable, '
                 "codes: [A_CODE], match: all}\n")
    with pytest.raises(ValueError, match="key 'name' appears twice in one mapping, "
                                         "on lines 1 and 1"):
        reg.load_rules([path])


def test_a_merge_key_may_restate_a_key_it_merges(one_code: None, tmp_path: Path) -> None:
    """`<<: *base` then `name:` overrides the merged name, which is what YAML
    merge keys are for rather than a repeated key."""

    loaded = reg.load_rules([write(tmp_path, "r.yaml", """
- &base
  name: "first"
  message: "m"
  action: disable
  codes: [A_CODE]
  match: all
- <<: *base
  name: "second"
""")])
    assert [rule.name for rule in loaded] == ["first", "second"]


def test_duplicate_rule_name_within_one_file_is_rejected(one_code: None, tmp_path: Path) -> None:
    path = write(tmp_path, "dup.yaml", GLOBAL_DISABLE + GLOBAL_DISABLE)
    with pytest.raises(ValueError, match=r"Duplicate rule name 'kill_it'"):
        reg.load_rules([path])


def test_duplicate_rule_name_across_files_names_both_files(one_code: None, tmp_path: Path) -> None:
    first = write(tmp_path, "a.yaml", GLOBAL_DISABLE)
    second = write(tmp_path, "b.yaml", GLOBAL_DISABLE)
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([first, second])
    message = str(excinfo.value)
    assert f"defined in {first} and again in {second}" in message


def test_loading_no_files_returns_nothing(one_code: None) -> None:
    assert reg.load_rules([]) == []


def test_load_rules_keeps_the_given_order_not_alphabetical(
    one_code: None, tmp_path: Path
) -> None:
    first = write(tmp_path, "a.yaml", GLOBAL_DISABLE.replace("kill_it", "alpha"))
    second = write(tmp_path, "z.yaml", GLOBAL_DISABLE.replace("kill_it", "zulu"))
    loaded = reg.load_rules([second, first])
    assert [r.name for r in loaded] == ["zulu", "alpha"]


def test_load_rules_spans_directories(one_code: None, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    a = write(left, "a.yaml", GLOBAL_DISABLE.replace("kill_it", "from_left"))
    b = write(right, "b.yaml", GLOBAL_DISABLE.replace("kill_it", "from_right"))
    assert [r.name for r in reg.load_rules([a, b])] == ["from_left", "from_right"]


def test_the_codes_column_lists_every_code_a_rule_touches(one_code: None, tmp_path: Path) -> None:
    """The detail behind code_count, as a column rather than a lookup function."""

    make_check("B_CODE")
    path = write(
        tmp_path, "r.yaml", '- name: "two"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE, B_CODE]\n  match: all\n'
    )
    table = views.rules_table(reg.load_rules([path]))
    assert table.loc[0, "codes"] == "A_CODE, B_CODE"
    assert table.loc[0, "code_count"] == 2


# --- matching and precedence ------------------------------------------------


def rule(name: str, action: str, codes: list[str], criteria: list[tuple[str, str]] | None,
         ) -> reg.Rule:
    """Build a rule directly, bypassing YAML, to isolate matching behavior."""

    import re

    made = [_MatchCriterion(c, p, re.compile(p)) for c, p in (criteria or [])]
    return reg.Rule(name=name, action=action, codes=codes, criteria=made,
                            match_all=criteria is None, message="why the rule exists")


def test_default_state_is_used_when_no_rule_matches(fresh_registry: None) -> None:
    make_check("ON_BY_DEFAULT")
    make_check("OFF_BY_DEFAULT", default_enabled=False)
    state = enabled_only(engine._resolve_enabled_state(pd.Series({"age": 1}), []))
    assert state == {"ON_BY_DEFAULT": True, "OFF_BY_DEFAULT": False}


def test_enable_rule_turns_on_an_off_by_default_code(fresh_registry: None) -> None:
    make_check("OFF_BY_DEFAULT", default_enabled=False)
    state = enabled_only(engine._resolve_enabled_state(
        pd.Series({"age": 1}), [rule("on", "enable", ["OFF_BY_DEFAULT"], None)]
    ))
    assert state["OFF_BY_DEFAULT"] is True


def test_all_criteria_must_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    two = rule("both", "disable", ["A_CODE"], [("source_system", "^LEGACY_"), ("record_type", "^BATCH$")])
    matching = pd.Series({"source_system": "LEGACY_A", "record_type": "BATCH"})
    half = pd.Series({"source_system": "LEGACY_A", "record_type": "STREAM"})
    assert enabled_only(engine._resolve_enabled_state(matching, [two]))["A_CODE"] is False
    assert enabled_only(engine._resolve_enabled_state(half, [two]))["A_CODE"] is True


def test_pattern_is_a_search_not_a_full_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    unanchored = rule("mid", "disable", ["A_CODE"], [("email", "internal")])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"email": "qa@internal.test"}), [unanchored]))["A_CODE"] is False


def test_absent_column_does_not_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    on_email = rule("r", "disable", ["A_CODE"], [("email", ".*")])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"age": 1}), [on_email]))["A_CODE"] is True


def test_null_value_does_not_match(fresh_registry: None) -> None:
    make_check("A_CODE")
    on_email = rule("r", "disable", ["A_CODE"], [("email", ".*")])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"email": None}), [on_email]))["A_CODE"] is True


def test_non_string_values_are_matched_as_text(fresh_registry: None) -> None:
    make_check("A_CODE")
    numeric = rule("r", "disable", ["A_CODE"], [("age", "^41$")])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"age": 41}), [numeric]))["A_CODE"] is False


def test_a_whole_number_is_matched_as_the_report_prints_it(fresh_registry: None) -> None:
    """Two ways pandas turns 41 into 41.0 before a rule sees it: a column with
    one blank is read as float, and `iterrows` upcasts a row to float when every
    column is numeric. The report prints both as `41`, so `^41$` must match.
    Through `validate`, because a hand-built Series never goes through either.
    """

    from io import StringIO

    make_check("A_CODE")
    on_age = rule("r", "disable", ["A_CODE"], [("age", "^41$")])
    blank_in_column = pd.read_csv(StringIO("id,name,age\n1,a,41\n2,b,\n"))
    assert str(blank_in_column.dtypes["age"]) == "float64"
    outcomes = engine.validate(blank_in_column, rules=[on_age])
    assert [row[0].outcome for row in outcomes] == [Outcome.DISABLED, Outcome.PASSED]

    on_id = rule("r", "disable", ["A_CODE"], [("id", "^102$")])
    all_numeric = pd.DataFrame({"id": [101, 102], "age": [1.5, 2.0]})
    outcomes = engine.validate(all_numeric, rules=[on_id])
    assert [row[0].outcome for row in outcomes] == [Outcome.PASSED, Outcome.DISABLED]


def test_a_fraction_keeps_its_decimals(fresh_registry: None) -> None:
    make_check("A_CODE")
    on_age = rule("r", "disable", ["A_CODE"], [("age", "^41$")])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"age": 41.5}), [on_age]))["A_CODE"] is True


def test_matching_is_case_sensitive(fresh_registry: None) -> None:
    make_check("A_CODE")
    lower = rule("r", "disable", ["A_CODE"], [("kind", "^batch$")])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"kind": "BATCH"}), [lower]))["A_CODE"] is True
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"kind": "batch"}), [lower]))["A_CODE"] is False


def test_last_matching_rule_wins(fresh_registry: None) -> None:
    make_check("A_CODE", default_enabled=False)
    loaded = [rule("on", "enable", ["A_CODE"], None), rule("off", "disable", ["A_CODE"], None)]
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"age": 1}), loaded))["A_CODE"] is False
    assert enabled_only(
        engine._resolve_enabled_state(pd.Series({"age": 1}), list(reversed(loaded)))
    )["A_CODE"] is True


def test_a_non_matching_later_rule_does_not_override(fresh_registry: None) -> None:
    make_check("A_CODE", default_enabled=False)
    loaded = [
        rule("on", "enable", ["A_CODE"], None),
        rule("off", "disable", ["A_CODE"], [("email", "@internal")]),
    ]
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"email": "a@b.com"}), loaded))["A_CODE"] is True


def test_one_rule_switches_several_codes(fresh_registry: None) -> None:
    make_check("FIRST")
    make_check("SECOND")
    state = enabled_only(engine._resolve_enabled_state(
        pd.Series({"age": 1}), [rule("both", "disable", ["FIRST", "SECOND"], None)]
    ))
    assert state == {"FIRST": False, "SECOND": False}


def test_codes_that_are_not_registered_are_ignored_by_resolution(fresh_registry: None) -> None:
    make_check("A_CODE")
    state = enabled_only(engine._resolve_enabled_state(
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
    assert rules._cell_text(row, "email") is None
    assert rules._cell_text(row, "age") is None
    assert rules._cell_text(row, "absent") is None
    assert rules._cell_text(row, "name") == "real"


# --- rules a later rule overrules for every row ------------------------------


def _rules(tmp_path: Path, text: str) -> list[Any]:
    return reg.load_rules([write(tmp_path, "rules.yaml", text)])


def test_a_rule_a_later_unconditional_rule_overrules_is_reported(
    one_code: None, tmp_path: Path
) -> None:
    """Positional precedence means a `match: all` rule later in the file is the
    last match on every row, so anything before it touching the same code can
    never decide. Nothing else says so: the registry table lists both loaded and
    answers "depends on row", which is right in general and wrong here."""

    loaded = _rules(tmp_path, """
- name: "narrow_enable"
  message: "only legacy rows"
  action: enable
  codes: [A_CODE]
  match:
    - column: source
      pattern: "^LEGACY"
""" + GLOBAL_DISABLE)

    assert rules.warn_shadowed_rules(loaded) == [
        "rule 'narrow_enable' is overruled for A_CODE by the later rule 'kill_it', "
        "which matches every row: it can never apply to A_CODE"
    ]


def test_a_rule_after_the_unconditional_one_is_not_reported(
    one_code: None, tmp_path: Path
) -> None:
    """The same two loaded the other way round is the pattern that works: off for
    every row, back on for the rows that match."""

    loaded = _rules(tmp_path, GLOBAL_DISABLE + """
- name: "narrow_enable"
  message: "only legacy rows"
  action: enable
  codes: [A_CODE]
  match:
    - column: source
      pattern: "^LEGACY"
""")

    assert rules.warn_shadowed_rules(loaded) == []


def test_two_conditional_rules_are_not_reported(one_code: None, tmp_path: Path) -> None:
    """Deliberately out of scope: whether two patterns overlap needs them
    compared rather than read, and a wrong answer is worse than none."""

    loaded = _rules(tmp_path, """
- name: "first"
  message: "m"
  action: enable
  codes: [A_CODE]
  match:
    - column: source
      pattern: "."
- name: "second"
  message: "m"
  action: disable
  codes: [A_CODE]
  match:
    - column: source
      pattern: "^LEGACY"
""")

    assert rules.warn_shadowed_rules(loaded) == []


def test_a_rule_is_judged_per_code_not_per_rule(fresh_registry: None, tmp_path: Path) -> None:
    """A rule carrying two codes can be overruled for one and decisive for the
    other, so the warning names the code rather than condemning the rule."""

    make_check("A_CODE")
    make_check("B_CODE")
    loaded = _rules(tmp_path, """
- name: "both"
  message: "m"
  action: enable
  codes: [A_CODE, B_CODE]
  match: all
- name: "kills_a_only"
  message: "m"
  action: disable
  codes: [A_CODE]
  match: all
""")

    assert rules.warn_shadowed_rules(loaded) == [
        "rule 'both' is overruled for A_CODE by the later rule 'kills_a_only', "
        "which matches every row: it can never apply to A_CODE"
    ]


def test_the_shipped_example_reports_its_deliberate_shadowed_rule(
    example_checks: None,
) -> None:
    """`examples/rules/error_rules.yaml` shadows a rule on purpose -- it is the
    precedence demonstration `docs/configuration.md` describes -- so the shipped
    file is also the worked example of this warning."""

    loaded = reg.load_rules([str(Path(PROJECT_ROOT) / "examples/rules/error_rules.yaml")])
    assert rules.warn_shadowed_rules(loaded) == [
        "rule 'enable_legacy_integer_check' is overruled for AGE_NOT_INTEGER by the later "
        "rule 'disable_age_integer_check_globally', which matches every row: it can never "
        "apply to AGE_NOT_INTEGER"
    ]


def test_a_code_with_no_unconditional_rule_does_not_end_the_search(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The first code has only a conditional rule; the second is shadowed. A loop
    that stopped at the first code would lose the second's warning."""

    make_check("A_CODE")
    make_check("B_CODE")
    loaded = _rules(tmp_path, """
- name: "a_for_legacy"
  message: "m"
  action: disable
  codes: [A_CODE]
  match:
    - column: source
      pattern: "^LEGACY"
- name: "b_for_legacy"
  message: "m"
  action: enable
  codes: [B_CODE]
  match:
    - column: source
      pattern: "^LEGACY"
- name: "b_everywhere"
  message: "m"
  action: disable
  codes: [B_CODE]
  match: all
""")
    assert rules.warn_shadowed_rules(loaded) == [
        "rule 'b_for_legacy' is overruled for B_CODE by the later rule 'b_everywhere', "
        "which matches every row: it can never apply to B_CODE"
    ]


def test_the_rule_warnings_take_a_generator(one_code: None, tmp_path: Path) -> None:
    """A generator is read more than once inside; read as it came, the second
    pass found it empty and the warning went missing."""

    loaded = _rules(tmp_path, """
- name: "narrow"
  message: "m"
  action: enable
  codes: [A_CODE]
  match:
    - column: source
      pattern: "^LEGACY"
""" + GLOBAL_DISABLE)
    assert len(rules.warn_shadowed_rules(rule for rule in loaded)) == 1  # type: ignore[arg-type]
    frame = pd.DataFrame({"other": [1]})
    assert len(rules.warn_missing_rule_columns(
        frame, (rule for rule in loaded))) == 1  # type: ignore[arg-type]


def test_no_rules_and_no_unconditional_rule_report_nothing(one_code: None, tmp_path: Path) -> None:
    assert rules.warn_shadowed_rules([]) == []
    loaded = _rules(tmp_path, """
- name: "narrow"
  message: "m"
  action: disable
  codes: [A_CODE]
  match:
    - column: source
      pattern: "^LEGACY"
""")
    assert rules.warn_shadowed_rules(loaded) == []


# --- disable rules that silence the checks below them ------------------------


@pytest.fixture
def age_chain(fresh_registry: None) -> None:
    """AGE_PRESENT <- AGE_NUMBER <- AGE_NEGATIVE, with EMAIL_PRESENT beside them."""

    make_check("AGE_PRESENT")
    make_check("AGE_NUMBER", depends_on=["AGE_PRESENT"])
    make_check("AGE_NEGATIVE", depends_on=["AGE_NUMBER"])
    make_check("EMAIL_PRESENT")


def disabling(*codes: str, name: str = "excuse", action: str = "disable") -> reg.Rule:
    return rule(name, action, list(codes), [("source", "^LEGACY_B$")])


def test_a_disable_rule_on_a_prerequisite_names_every_check_it_silences(
    age_chain: None,
) -> None:
    """The rule says AGE_PRESENT; on its rows AGE_NUMBER and AGE_NEGATIVE never
    run either, and report nothing -- the dependents, deepest last."""

    assert reg.warn_blocking_rules([disabling("AGE_PRESENT")]) == [
        "rule 'excuse' disables AGE_PRESENT, which also stops AGE_NUMBER, AGE_NEGATIVE "
        "on the rows it matches: a check whose prerequisite is off is skipped, and "
        "reports nothing"
    ]


def test_naming_the_dependents_in_the_rule_says_the_silence_is_meant(
    age_chain: None,
) -> None:
    whole_chain = disabling("AGE_PRESENT", "AGE_NUMBER", "AGE_NEGATIVE")
    assert reg.warn_blocking_rules([whole_chain]) == []


def test_a_chain_partly_named_is_reported_once_from_its_top(age_chain: None) -> None:
    """AGE_NUMBER is below AGE_PRESENT, so its own warning would repeat the one
    for AGE_PRESENT."""

    # The lower code listed first: skipping it must not end the rule's other codes.
    assert reg.warn_blocking_rules(
        [disabling("AGE_NUMBER", "AGE_PRESENT")]) == [
        "rule 'excuse' disables AGE_PRESENT, which also stops AGE_NEGATIVE on the rows "
        "it matches: a check whose prerequisite is off is skipped, and reports nothing"
    ]


def test_enable_rules_and_leaf_checks_block_nothing(age_chain: None) -> None:
    assert reg.warn_blocking_rules([
        disabling("AGE_PRESENT", action="enable"),
        disabling("AGE_NEGATIVE", "EMAIL_PRESENT", name="leaves"),
    ]) == []


def test_an_enable_rule_first_does_not_end_the_search(age_chain: None) -> None:
    assert len(reg.warn_blocking_rules([
        disabling("AGE_PRESENT", action="enable", name="first"),
        disabling("AGE_NUMBER", name="second"),
    ])) == 1


def test_a_rule_naming_a_code_no_longer_registered_warns_about_nothing(
    age_chain: None,
) -> None:
    """Rules loaded, then the registry cleared and a different set loaded."""

    assert reg.warn_blocking_rules([disabling("GONE_CODE")]) == []


def test_the_blocking_warning_takes_a_generator(age_chain: None) -> None:
    rules_given = [disabling("AGE_NUMBER")]
    assert len(reg.warn_blocking_rules(
        rule for rule in rules_given)) == 1  # type: ignore[arg-type]


def test_the_shipped_rules_silence_nothing_they_do_not_name(example_checks: None) -> None:
    """`error_rules.yaml` disables EMAIL_MISSING_AT and, in the same rule, the
    check depending on it -- the way to say a chain's silence is meant."""

    loaded = reg.load_rules([str(Path(PROJECT_ROOT) / "examples/rules/error_rules.yaml")])
    assert reg.warn_blocking_rules(loaded) == []


def test_a_check_reached_by_two_paths_is_named_once(fresh_registry: None) -> None:
    """A diamond: TOTAL depends on QTY and PRICE, which both depend on LINE."""

    make_check("LINE")
    make_check("QTY", depends_on=["LINE"])
    make_check("PRICE", depends_on=["LINE"])
    make_check("TOTAL", depends_on=["QTY", "PRICE"])
    assert reg.warn_blocking_rules([disabling("LINE")]) == [
        "rule 'excuse' disables LINE, which also stops PRICE, QTY, TOTAL on the rows it "
        "matches: a check whose prerequisite is off is skipped, and reports nothing"
    ]
