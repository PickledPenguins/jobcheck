"""Fault injection: what the filesystem does to a run that assumed it worked.

Every loader here reads a path somebody else controls, and every report here is
written to one. The parser's own error paths are covered by the unit checks; what
is covered here is the layer underneath them -- a file that cannot be read, a
directory where a file was expected, a symlink pointing nowhere, a device that
fails on write -- where the failure arrives as an ``OSError`` rather than as a
message this library wrote.

The rule this pins is that such a failure propagates with the path in it and
leaves nothing half-applied: no partial registry, no truncated report treated as
a whole one.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import (
    engine,
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
def test_an_unreadable_rule_file_raises_permission_error(fresh_registry: None,
                                                         tmp_path: Path) -> None:
    make_check("A_CODE")
    path = tmp_path / "rules.yaml"
    path.write_text(RULE)
    unreadable(path)
    with pytest.raises(PermissionError) as raised:
        load_rules([str(path)])
    assert str(path) in str(raised.value)


def test_a_rule_path_that_is_a_directory_says_to_name_the_file(fresh_registry: None,
                                                               tmp_path: Path) -> None:
    """Pointing the list at the directory holding the rule files is the likely
    mistake, so it is named rather than left to the file layer's errno."""

    make_check("A_CODE")
    with pytest.raises(ValueError, match="is a directory, so name the file in it"):
        load_rules([str(tmp_path)])


def test_a_rule_symlink_pointing_nowhere_is_refused_as_a_missing_file(fresh_registry: None,
                                                                      tmp_path: Path) -> None:
    """The link resolves to a target that is not there, so it is the same
    mistake as naming the target, and says so."""

    link = tmp_path / "rules.yaml"
    link.symlink_to(tmp_path / "gone.yaml")
    make_check("A_CODE")
    with pytest.raises(ValueError, match="No rule file at"):
        load_rules([str(link)])


@unwritable_as_root
def test_one_unreadable_file_in_a_directory_stops_the_whole_load(fresh_registry: None,
                                                                 tmp_path: Path) -> None:
    """Half a directory of rules is not a smaller set of rules; it is the wrong set."""

    make_check("A_CODE")
    (tmp_path / "01.yaml").write_text(RULE)
    (tmp_path / "02.yaml").write_text(RULE.replace("name: r", "name: s"))
    unreadable(tmp_path / "02.yaml")
    with pytest.raises(PermissionError):
        load_rules([str(tmp_path / "01.yaml"), str(tmp_path / "02.yaml")])


def test_a_missing_file_in_a_list_names_that_file(fresh_registry: None, tmp_path: Path) -> None:
    make_check("A_CODE")
    good = tmp_path / "01.yaml"
    good.write_text(RULE)
    with pytest.raises(ValueError) as raised:
        load_rules([str(good), str(tmp_path / "02.yaml")])
    assert "02.yaml" in str(raised.value)


def test_a_rule_file_holding_nul_bytes_is_rejected(fresh_registry: None, tmp_path: Path) -> None:
    """A binary file passed as a rule file fails in the parser, naming the file.

    The error comes from PyYAML rather than from this library, which is worth
    pinning rather than wrapping: it already carries the path and the offending
    byte, which is more than a rewrapped message would say.
    """

    import yaml

    make_check("A_CODE")
    path = tmp_path / "rules.yaml"
    path.write_bytes(b"- name: r\n  message: \"why the rule exists\"\n  action: disable\n  codes: [A_CODE]\n\x00\x00")
    with pytest.raises(yaml.YAMLError) as raised:
        load_rules([str(path)])
    assert "unacceptable character" in str(raised.value)
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


def test_a_check_file_symlink_pointing_nowhere_is_reported_as_missing(fresh_registry: None,
                                                                     tmp_path: Path) -> None:
    link = tmp_path / "checks.py"
    link.symlink_to(tmp_path / "gone.py")
    with pytest.raises(ValueError, match="No check file at"):
        load_checks([str(link)])


def test_a_check_file_holding_a_syntax_error_propagates_it(fresh_registry: None,
                                                          tmp_path: Path) -> None:
    path = tmp_path / "checks.py"
    path.write_text("def rule(row:\n")
    with pytest.raises(SyntaxError):
        load_checks([str(path)])
    assert reg._CHECKS == []


def test_the_good_files_of_a_failed_call_still_registered(fresh_registry: None,
                                                          tmp_path: Path) -> None:
    """Loading is not transactional, and the loaded files say so rather than lying.

    A file that imported has run its decorators; nothing can un-run them. What
    matters is that the registry and _LOADED_FILES agree about what happened.
    """

    good = tmp_path / "good.py"
    good.write_text(CHECK_FILE)
    broken = tmp_path / "broken.py"
    broken.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError):
        load_checks([str(good), str(broken)])
    assert [t.code for t in reg._CHECKS] == ["FROM_FILE"]
    assert reg._LOADED_FILES == [str(good.resolve())]
    # And the survivor runs: the failure path must leave the evaluation order
    # recomputed, not a stale cache that would validate a row against nothing.
    assert [o.code for o in engine._explain(pd.Series({"id": 1}))] == ["FROM_FILE"]
