"""Fault injection: what the filesystem does to a run that assumed it worked.

Every loader here reads a path somebody else controls, and every report here is
written to one. The parser's own error paths are covered by the unit tests; what
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
import stat
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import make_test
from pandas_row_validation import (
    build_report,
    collect_outcomes,
    load_overrides,
    load_overrides_from_dir,
    load_overrides_from_files,
    load_test_files,
    registry as reg,
    write_report,
)

pytestmark = pytest.mark.long

RULE = ("- name: r\n  action: disable\n  codes: [A_CODE]\n  match: all\n")

TEST_FILE = (
    "from pandas_row_validation import PASS, test_group\n"
    "g = test_group()\n"
    "@g('FROM_FILE', 'from file')\n"
    "def rule(row):\n"
    "    return PASS\n"
)

unwritable_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root ignores the permission bits these tests set"
)


def unreadable(path: Path) -> Path:
    """Strip every read bit from *path*, restored by tmp_path's own cleanup."""

    path.chmod(0)
    return path


# --- reading rule files -----------------------------------------------------


@unwritable_as_root
def test_an_unreadable_rule_file_raises_permission_error(fresh_registry: None,
                                                         tmp_path: Path) -> None:
    make_test("A_CODE")
    path = tmp_path / "rules.yaml"
    path.write_text(RULE)
    unreadable(path)
    with pytest.raises(PermissionError) as raised:
        load_overrides(str(path))
    assert str(path) in str(raised.value)


def test_a_rule_path_that_is_a_directory_raises(fresh_registry: None, tmp_path: Path) -> None:
    make_test("A_CODE")
    with pytest.raises(IsADirectoryError):
        load_overrides(str(tmp_path))


def test_a_rule_symlink_pointing_nowhere_raises_file_not_found(fresh_registry: None,
                                                               tmp_path: Path) -> None:
    link = tmp_path / "rules.yaml"
    link.symlink_to(tmp_path / "gone.yaml")
    make_test("A_CODE")
    with pytest.raises(FileNotFoundError):
        load_overrides(str(link))


@unwritable_as_root
def test_one_unreadable_file_in_a_directory_stops_the_whole_load(fresh_registry: None,
                                                                 tmp_path: Path) -> None:
    """Half a directory of rules is not a smaller set of rules; it is the wrong set."""

    make_test("A_CODE")
    (tmp_path / "01.yaml").write_text(RULE)
    (tmp_path / "02.yaml").write_text(RULE.replace("name: r", "name: s"))
    unreadable(tmp_path / "02.yaml")
    with pytest.raises(PermissionError):
        load_overrides_from_dir(str(tmp_path))


def test_a_missing_file_in_a_list_names_that_file(fresh_registry: None, tmp_path: Path) -> None:
    make_test("A_CODE")
    good = tmp_path / "01.yaml"
    good.write_text(RULE)
    with pytest.raises(FileNotFoundError) as raised:
        load_overrides_from_files([str(good), str(tmp_path / "02.yaml")])
    assert "02.yaml" in str(raised.value)


def test_a_rule_file_holding_nul_bytes_is_rejected(fresh_registry: None, tmp_path: Path) -> None:
    """A binary file passed as a rule file fails in the parser, naming the file.

    The error comes from PyYAML rather than from this library, which is worth
    pinning rather than wrapping: it already carries the path and the offending
    byte, which is more than a rewrapped message would say.
    """

    import yaml

    make_test("A_CODE")
    path = tmp_path / "rules.yaml"
    path.write_bytes(b"- name: r\n  action: disable\n  codes: [A_CODE]\n\x00\x00")
    with pytest.raises(yaml.YAMLError) as raised:
        load_overrides(str(path))
    assert "unacceptable character" in str(raised.value)
    assert str(path) in str(raised.value)


# --- reading test files -----------------------------------------------------


@unwritable_as_root
def test_an_unreadable_test_file_raises_and_registers_nothing(fresh_registry: None,
                                                              tmp_path: Path) -> None:
    path = tmp_path / "checks.py"
    path.write_text(TEST_FILE)
    unreadable(path)
    with pytest.raises(PermissionError):
        load_test_files([str(path)])
    assert reg.TESTS == []


def test_a_test_file_symlink_pointing_nowhere_is_reported_as_missing(fresh_registry: None,
                                                                     tmp_path: Path) -> None:
    link = tmp_path / "checks.py"
    link.symlink_to(tmp_path / "gone.py")
    with pytest.raises(ValueError, match="No test file at"):
        load_test_files([str(link)])


def test_a_test_file_holding_a_syntax_error_propagates_it(fresh_registry: None,
                                                          tmp_path: Path) -> None:
    path = tmp_path / "checks.py"
    path.write_text("def rule(row:\n")
    with pytest.raises(SyntaxError):
        load_test_files([str(path)])
    assert reg.TESTS == []


def test_the_good_files_of_a_failed_call_still_registered(fresh_registry: None,
                                                          tmp_path: Path) -> None:
    """Loading is not transactional, and the loaded files say so rather than lying.

    A file that imported has run its decorators; nothing can un-run them. What
    matters is that the registry and loaded_files() agree about what happened.
    """

    good = tmp_path / "good.py"
    good.write_text(TEST_FILE)
    broken = tmp_path / "broken.py"
    broken.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError):
        load_test_files([str(good), str(broken)])
    assert [t.code for t in reg.TESTS] == ["FROM_FILE"]
    assert reg.loaded_files() == [str(good.resolve())]


# --- writing reports --------------------------------------------------------


def report_of(fresh: None) -> pd.DataFrame:
    make_test("FAILS", passes=False)
    frame = pd.DataFrame([{"id": 1}])
    return build_report(collect_outcomes(frame), df=frame, key_column="id")


def test_writing_into_a_missing_directory_raises_naming_the_path(fresh_registry: None,
                                                                 tmp_path: Path) -> None:
    report = report_of(fresh_registry)
    target = tmp_path / "no-such-dir" / "report.csv"
    with pytest.raises(FileNotFoundError) as raised:
        write_report(report, str(target))
    assert "report.csv" in str(raised.value)


@unwritable_as_root
def test_writing_into_a_read_only_directory_raises(fresh_registry: None, tmp_path: Path) -> None:
    report = report_of(fresh_registry)
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(PermissionError):
            write_report(report, str(locked / "report.csv"))
    finally:
        locked.chmod(stat.S_IRWXU)


def test_a_write_that_fails_midway_leaves_no_half_report(fresh_registry: None,
                                                         tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    """A full disk is an OSError from write(); the caller must see it, not a short file."""

    report = report_of(fresh_registry)
    target = tmp_path / "report.csv"
    real_open = open

    class FailingHandle:
        def __init__(self, handle: Any) -> None:
            self._handle = handle

        def write(self, _text: str) -> int:
            raise OSError(28, "No space left on device")

        def __enter__(self) -> "FailingHandle":
            return self

        def __exit__(self, *exc: Any) -> None:
            self._handle.close()

    def failing_open(path: Any, *args: Any, **kwargs: Any) -> Any:
        if str(path) == str(target):
            return FailingHandle(real_open(path, *args, **kwargs))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)
    with pytest.raises(OSError, match="No space left on device"):
        write_report(report, str(target))
    monkeypatch.undo()
    assert target.read_text() == ""


def test_writing_to_a_path_that_is_a_directory_raises(fresh_registry: None,
                                                      tmp_path: Path) -> None:
    report = report_of(fresh_registry)
    with pytest.raises(IsADirectoryError):
        write_report(report, str(tmp_path))
