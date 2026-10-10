"""Pathological input: a rule file that is not YAML, and checks that break."""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from conftest import failures, make_check
from jobcheck import registry as reg
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


def test_invalid_yaml_raises_a_yaml_error_naming_the_file(one_code: None, tmp_path: Path) -> None:
    """The error comes from PyYAML rather than from this library, which is worth
    pinning rather than wrapping: it already carries the path and the offending
    character, which is more than a rewrapped message would say.
    """
    path = write(tmp_path, "bad.yaml", "- name: [unclosed\n  message: \"why the rule exists\"\n")
    with pytest.raises(yaml.YAMLError) as raised:
        reg.load_rules([path])
    assert path in str(raised.value)


# --- checks that break ------------------------------------------------------


def test_a_check_that_raises_is_recorded_as_an_error_not_a_pass(fresh_registry: None) -> None:
    """A broken check must never be mistaken for a happy one. Checks read the row
    themselves, so a typo in a column name surfaces here too, as a KeyError."""
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
