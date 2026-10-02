"""Unit checks: the step both loaders take before they open anything.

A missing file is the most common load-time mistake, and the message is the
whole of what the person sees. What is pinned here is that it says where the
path was resolved to, since a relative path and a working directory the reader
cannot see are what made the old message unhelpful.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import yaml

from jobcheck.paths import _read_yaml, _resolve_input_file

pytestmark = pytest.mark.fast


def test_an_existing_file_comes_back_resolved(tmp_path: Path) -> None:
    target = tmp_path / "checks.py"
    target.write_text("")
    assert _resolve_input_file(str(target), "check file", "load_checks()") == target.resolve()


def test_a_relative_path_is_resolved_against_the_working_directory(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / "checks.py").write_text("")
    monkeypatch.chdir(tmp_path)
    assert _resolve_input_file("checks.py", "check file", "load_checks()") == (
        (tmp_path / "checks.py").resolve())


def test_a_symlink_comes_back_as_its_target(tmp_path: Path) -> None:
    """`resolve` follows the link, so the two paths to one file are one entry
    in the loaded-files list rather than two."""

    target = tmp_path / "real.py"
    target.write_text("")
    link = tmp_path / "link.py"
    link.symlink_to(target)
    assert _resolve_input_file(str(link), "check file", "load_checks()") == target.resolve()


def test_base_dir_anchors_a_relative_path(tmp_path: Path, monkeypatch: Any) -> None:
    """The point of the argument: the caller's directory decides, not the
    directory the process happens to have been started in."""

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    (tmp_path / "checks.py").write_text("")
    assert _resolve_input_file("checks.py", "check file", "load_checks()", tmp_path) == (
        (tmp_path / "checks.py").resolve())


def test_an_absolute_path_ignores_base_dir(tmp_path: Path) -> None:
    target = tmp_path / "checks.py"
    target.write_text("")
    assert _resolve_input_file(str(target), "check file", "load_checks()",
                              tmp_path / "nowhere") == target.resolve()


def test_a_missing_path_under_base_dir_says_which_directory_it_used(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as raised:
        _resolve_input_file("checks.py", "check file", "load_checks()", tmp_path)
    assert str(raised.value) == (
        f"No check file at 'checks.py': nothing at {tmp_path.resolve() / 'checks.py'}, "
        f"where a relative path is resolved against base_dir {tmp_path}. "
        "load_checks() names files explicitly; nothing is discovered."
    )


def test_a_missing_relative_path_says_what_it_looked_at(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError) as raised:
        _resolve_input_file("checks.py", "check file", "load_checks()")
    assert str(raised.value) == (
        f"No check file at 'checks.py': nothing at {tmp_path.resolve() / 'checks.py'}, "
        "where a relative path is resolved against the working directory. "
        "load_checks() names files explicitly; nothing is discovered."
    )


def test_a_missing_absolute_path_is_left_to_speak_for_itself() -> None:
    """An absolute path that is not there needs no second copy of itself."""

    with pytest.raises(ValueError) as raised:
        _resolve_input_file("/no/such/file.py", "check file", "load_checks()")
    assert str(raised.value) == (
        "No check file at '/no/such/file.py'. load_checks() names files "
        "explicitly; nothing is discovered."
    )


def test_a_directory_is_named_as_the_mistake_it_is(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as raised:
        _resolve_input_file(str(tmp_path), "rule file", "load_rules()")
    assert str(raised.value) == (
        f"No rule file at {str(tmp_path)!r}: {tmp_path.resolve()} is a directory, "
        "so name the file in it. load_rules() names files explicitly; "
        "nothing is discovered."
    )


def test_the_kind_and_the_caller_are_the_words_the_message_uses(tmp_path: Path) -> None:
    """Both loaders share this code, so neither may describe itself as the other."""

    with pytest.raises(ValueError) as raised:
        _resolve_input_file(str(tmp_path / "absent.yaml"), "rule file", "load_rules()")
    message = str(raised.value)
    assert message.startswith("No rule file at ")
    assert "load_rules() names files explicitly" in message


def test_a_repeat_after_a_merge_key_is_still_refused(tmp_path: Path) -> None:
    """The `<<` is skipped, not the rest of the mapping after it."""

    path = tmp_path / "f.yaml"
    path.write_text("base: &b {x: 1}\nm:\n  <<: *b\n  y: 1\n  y: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="^f.yaml: key 'y' appears twice in one mapping, "
                                         "on lines 4 and 5"):
        _read_yaml(path, "f.yaml")


def test_the_yaml_reader_leaves_an_unhashable_key_to_yaml(tmp_path: Path) -> None:
    """A list as a key cannot be looked up to find a repeat; SafeLoader refuses it
    with its own message rather than the reader failing with a TypeError."""

    path = tmp_path / "f.yaml"
    path.write_text("? [a, b]\n: 1\n", encoding="utf-8")
    with pytest.raises(yaml.constructor.ConstructorError, match="found unhashable key"):
        _read_yaml(path, "f.yaml")
