"""Unit checks: rule parsing, every load-time rejection, matching, precedence."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import numpy
import pandas as pd
import pytest
import yaml

from conftest import enabled_only, make_check
from jobcheck import paths
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


def test_a_rule_file_is_read_as_utf8_under_an_ascii_locale(
    one_code: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # In a C locale with Python's UTF-8 mode off, open() without an encoding
    # reads ASCII, and a rule message in any other script would not decode.
    # The locale is fixed at start-up, so the test stands in an open() with that
    # default; a subprocess would not see mutmut's mutants.
    def ascii_by_default(file: Path, encoding: str | None = None) -> Any:
        return builtins.open(file, encoding=encoding or "ascii")

    monkeypatch.setattr(paths, "open", ascii_by_default, raising=False)
    path = write(tmp_path, "rules.yaml", GLOBAL_DISABLE.replace("why the rule exists", "café"))
    assert reg.load_rules([path])[0].message == "café"


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

    match_all = reg.load_rules([write(tmp_path, "all.yaml", GLOBAL_DISABLE)])[0]
    assert match_all.match_all is True
    assert match_all.criteria == []


def test_a_key_yaml_reads_as_a_bool_is_named_rather_than_crashing(
    one_code: None, tmp_path: Path
) -> None:
    """A misspelled key in a hand-edited file is a setting that does nothing.

    YAML 1.1 reads `on:` as True and `2:` as an int. Joining them raised a bare
    TypeError once; now each shows as Python writes it, so the unquoted `True`
    says YAML read a bool where the file said `on`."""
    path = write(tmp_path, "r.yaml", GLOBAL_DISABLE + "  on: 1\n  2: x\n")
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([path])
    assert str(excinfo.value) == (
        f"rule 'kill_it' in {path}: unknown key(s) 2, True. "
        "Allowed: 'action', 'codes', 'match', 'message', 'name'.")


def test_an_empty_file_and_no_files_contribute_no_rules(one_code: None, tmp_path: Path) -> None:
    for text in ("", "# nothing here\n", "null\n"):
        assert reg.load_rules([write(tmp_path, "empty.yaml", text)]) == []
    assert reg.load_rules([]) == []


def test_base_dir_anchors_a_relative_rule_path_and_the_rule_records_it_as_written(
    one_code: None, tmp_path: Path, monkeypatch: Any
) -> None:
    """source_file is printed beside the rule, so it stays the caller's own
    text: an absolute path resolved out of base_dir would be this machine's."""
    write(tmp_path, "rules.yaml", GLOBAL_DISABLE)
    started_in = tmp_path / "started-in"
    started_in.mkdir()
    monkeypatch.chdir(started_in)
    rule = reg.load_rules(["rules.yaml"], base_dir=tmp_path)[0]
    assert (rule.name, rule.source_file) == ("kill_it", "rules.yaml")


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
            "'action' must be 'enable' or 'disable', got 'turn_on'.",
            id="bad-action",
        ),
        pytest.param(
            '- name: "r"\n  message: \"why the rule exists\"\n  codes: [A_CODE]\n  match: all\n',
            "'action' must be 'enable' or 'disable', got None.",
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
            '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
            "'message' must be a non-empty string",
            id="missing-message",
        ),
        pytest.param(
            '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n  message: 7\n',
            "'message' must be a non-empty string, got 7.",
            id="message-not-a-string",
        ),
        pytest.param(
            '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n  message: yes\n',
            "'message' must be a non-empty string, got True.",
            id="message-an-unquoted-yaml-boolean",
        ),
        pytest.param(
            '- name: "r"\n  action: disable\n  codes: [A_CODE]\n  match: all\n  message: ""\n',
            "'message' must be a non-empty string, got ''.",
            id="message-empty",
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
    with pytest.raises(yaml.YAMLError, match="^a key appears twice in this mapping"):
        reg.load_rules([path])


def test_a_key_repeated_in_a_flow_mapping_is_refused_too(one_code: None, tmp_path: Path) -> None:
    """Both on one line, written `{...}` rather than as a block."""
    path = write(tmp_path, "r.yaml",
                 '- {name: "r", name: "s", message: "m", action: disable, '
                 "codes: [A_CODE], match: all}\n")
    with pytest.raises(yaml.YAMLError, match="^a key appears twice in this mapping"):
        reg.load_rules([path])


def test_a_rule_file_that_is_not_utf8_names_itself(one_code: None, tmp_path: Path) -> None:
    """Regression: a Latin-1 file let the codec's own error through, which says
    where in the bytes but not which file -- the one thing every other load
    error says first. Found by the text fuzz in `test_fuzz.py`."""
    path = tmp_path / "r.yaml"
    path.write_bytes(b"- name: caf\xe9\n")
    with pytest.raises(ValueError) as raised:
        reg.load_rules([str(path)])
    assert str(raised.value) == (
        f"{path}: not UTF-8 text: 'utf-8' codec can't decode byte 0xe9 in position 11: "
        "invalid continuation byte. Save the file as UTF-8.")


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


def test_load_rules_keeps_the_given_order_not_alphabetical(
    one_code: None, tmp_path: Path
) -> None:
    first = write(tmp_path, "a.yaml", GLOBAL_DISABLE.replace("kill_it", "alpha"))
    second = write(tmp_path, "z.yaml", GLOBAL_DISABLE.replace("kill_it", "zulu"))
    loaded = reg.load_rules([second, first])
    assert [r.name for r in loaded] == ["zulu", "alpha"]


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


def test_numbers_are_matched_as_text_and_a_fraction_keeps_its_decimals(
        fresh_registry: None) -> None:
    make_check("A_CODE")
    numeric = rule("r", "disable", ["A_CODE"], [("age", "^41$")])
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"age": 41}), [numeric]))["A_CODE"] is False
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"age": 41.5}), [numeric]))["A_CODE"] is True


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


def test_every_outcome_names_the_last_rule_that_switched_its_check(fresh_registry: None) -> None:
    make_check("REENABLED", passes=False)
    make_check("OFF_BY_DEFAULT", default_enabled=False, raises=RuntimeError("boom"))
    make_check("BLOCKED", depends_on=["REENABLED"])
    make_check("SWITCHED_OFF")
    make_check("UNTOUCHED")
    loaded = [
        rule("off", "disable", ["REENABLED", "SWITCHED_OFF"], None),
        rule("back_on", "enable", ["REENABLED", "OFF_BY_DEFAULT", "BLOCKED"], None),
    ]
    row = engine.validate(pd.DataFrame({"age": [1]}), rules=loaded)[0]
    assert {o.code: (o.outcome, o.rule) for o in row} == {
        "REENABLED": (Outcome.FAILED, "back_on"),
        "OFF_BY_DEFAULT": (Outcome.ERRORED, "back_on"),
        "BLOCKED": (Outcome.SKIPPED, "back_on"),
        "SWITCHED_OFF": (Outcome.DISABLED, "off"),
        "UNTOUCHED": (Outcome.PASSED, ""),
    }
    # detail keeps saying why a check never ran; the rule column is a separate fact.
    assert {o.code: o.detail for o in row}["SWITCHED_OFF"] == "disabled by rule 'off'"
    # The report carries the deciding rule, and a blank where the default decided.
    frame = pd.DataFrame({"age": [1]})
    report = views.build_report(engine.validate(frame, rules=loaded), frame,
                                include="all").reset_index()
    assert dict(zip(report["code"], report["rule"]))["REENABLED"] == "back_on"
    assert dict(zip(report["code"], report["rule"]))["UNTOUCHED"] == ""


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
    row = pd.Series({"email": None, "age": float("nan"), "name": "real"})
    assert rules._cell_text(row, "email") is None
    assert rules._cell_text(row, "age") is None
    assert rules._cell_text(row, "absent") is None
    assert rules._cell_text(row, "name") == "real"
    # Regression: pd.isna on an ndarray returns an array, and the bool() of that
    # raised "truth value of an array is ambiguous" instead of matching.
    assert rules._cell_text(pd.Series({"data": numpy.array([1, 2])}), "data") == "[1 2]"

    # Through resolution: a blank or absent column leaves the check as it was.
    make_check("A_CODE")
    for column in ("email", "absent"):
        on_column = rule("r", "disable", ["A_CODE"], [(column, ".*")])
        assert enabled_only(engine._resolve_enabled_state(row, [on_column]))["A_CODE"] is True


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

    assert rules.warn_shadowed_rules([]) == []

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

    make_check("B_CODE", depends_on=["A_CODE"])

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
    blocking = [disabling("A_CODE")]
    assert len(reg.warn_blocking_rules(
        rule for rule in blocking)) == 1  # type: ignore[arg-type]


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
