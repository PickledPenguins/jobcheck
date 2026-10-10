"""Safety: no code execution from data, no path escapes, no secret leakage."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import pytest

from conftest import enabled_only, make_check
from jobcheck import registry as reg
from jobcheck import engine
from jobcheck.rules import _MatchCriterion

pytestmark = pytest.mark.fast


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.fixture
def one_code(fresh_registry: None) -> None:
    make_check("A_CODE")


def test_yaml_cannot_construct_arbitrary_python_objects(one_code: None, tmp_path: Path) -> None:
    """A SafeLoader, not load: a !!python/object tag must be refused, not executed."""
    path = write(tmp_path, "evil.yaml", "- !!python/object/apply:os.system ['echo pwned']\n")
    with pytest.raises(Exception) as excinfo:
        reg.load_rules([path])
    assert "python/object" in str(excinfo.value)


def test_a_rule_pattern_is_never_evaluated_as_code(one_code: None, tmp_path: Path) -> None:
    path = write(
        tmp_path, "r.yaml",
        '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n'
        "  match:\n    - column: email\n      pattern: \"__import__('os').system('x')\"\n",
    )
    rules = reg.load_rules([path])
    assert rules[0].criteria[0].pattern == "__import__('os').system('x')"
    assert enabled_only(engine._resolve_enabled_state(pd.Series({"email": "harmless"}), rules))["A_CODE"] is True


def test_loading_rules_writes_nothing_to_disk(one_code: None, tmp_path: Path) -> None:
    write(tmp_path, "r.yaml", '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: all\n')
    before = sorted(p.name for p in tmp_path.iterdir())
    reg.load_rules([str(tmp_path / "r.yaml")])
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_a_catastrophic_regex_on_a_short_value_finishes_in_seconds(one_code: None, tmp_path: Path) -> None:
    """A nested-quantifier pattern on a 23-character value returns in under a
    second here. Nothing bounds it: the framework does not sandbox regexes, and
    the same pattern on 28 characters takes 42s -- the cost doubles with each
    character, and `configuration.md` says why nothing refuses or interrupts
    such a pattern. This pins that a cell-sized value is survivable, not that
    the matcher is safe.
    """
    rule = reg.Rule(
        name="redos", action="disable", codes=["A_CODE"],
        criteria=[_MatchCriterion("email", "(a+)+$", re.compile("(a+)+$"))], match_all=False,
        message="why the rule exists",
    )
    row = pd.Series({"email": "a" * 22 + "!"})
    start = time.monotonic()
    enabled_only(engine._resolve_enabled_state(row, [rule]))
    assert time.monotonic() - start < 5.0


# --- comments -----------------------------------------------------------------


def test_comments_are_never_evaluated(fresh_registry: None) -> None:
    """Comments are data all the way through: nothing formats or evals them."""
    from jobcheck.views import _render_comments

    rendered = _render_comments({"expr": "__import__('os').system('x')"})
    assert rendered == "expr=__import__('os').system('x')"


def test_error_messages_quote_the_offending_value_not_the_whole_file(
    one_code: None, tmp_path: Path
) -> None:
    """A rule file may sit beside sensitive data; errors must stay local."""
    path = write(
        tmp_path, "r.yaml",
        '- name: "r"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [NOT_A_CODE]\n  match: all\n'
        '- name: "other"\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: all\n',
    )
    with pytest.raises(ValueError) as excinfo:
        reg.load_rules([path])
    message = str(excinfo.value)
    assert "NOT_A_CODE" in message
    assert "other" not in message
