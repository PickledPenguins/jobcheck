"""Fault injection: what the filesystem does to a run that assumed it worked.

Every loader here reads a path somebody else controls. The parser's own error
paths are covered by the unit checks; what is covered here is the layer
underneath them -- a file that cannot be read, a file Python cannot compile --
where the failure arrives from the operating system or the interpreter rather
than as a message this library wrote.

The rule this pins is that such a failure propagates with the path in it and
leaves nothing half-applied: no partial registry.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from conftest import make_check
from jobcheck import (
    load_rules,
    load_checks,
    registry as reg,
)

pytestmark = pytest.mark.long

RULE = ("- name: r\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n  match: all\n")

CHECK_FILE = (
    "from jobcheck import OK, register_check\n"
    "@register_check('FROM_FILE', 'from file')\n"
    "def rule(row):\n"
    "    return OK\n"
)

unwritable_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root ignores the permission bits these checks set"
)


def unreadable(path: Path) -> Path:
    """Strip every read bit from *path*, restored by tmp_path's own cleanup."""
    path.chmod(0)
    return path


# --- reading rule files -----------------------------------------------------


@unwritable_as_root
def test_an_unreadable_rule_file_stops_the_whole_load_naming_itself(fresh_registry: None,
                                                                   tmp_path: Path) -> None:
    """Half a list of rules is not a smaller set of rules; it is the wrong set."""
    make_check("A_CODE")
    good = tmp_path / "01.yaml"
    good.write_text(RULE)
    path = tmp_path / "02.yaml"
    path.write_text(RULE.replace("name: r", "name: s"))
    unreadable(path)
    with pytest.raises(PermissionError) as raised:
        load_rules([str(good), str(path)])
    assert str(path) in str(raised.value)


# --- reading check files -----------------------------------------------------


@unwritable_as_root
def test_an_unreadable_check_file_raises_and_registers_nothing(fresh_registry: None,
                                                              tmp_path: Path) -> None:
    path = tmp_path / "checks.py"
    path.write_text(CHECK_FILE)
    unreadable(path)
    with pytest.raises(PermissionError):
        load_checks([str(path)])
    assert reg._CHECKS == []


def test_a_check_file_holding_a_syntax_error_propagates_it(fresh_registry: None,
                                                          tmp_path: Path) -> None:
    path = tmp_path / "checks.py"
    path.write_text("def rule(row:\n")
    with pytest.raises(SyntaxError):
        load_checks([str(path)])
    assert reg._CHECKS == []
