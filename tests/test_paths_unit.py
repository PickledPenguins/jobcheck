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

from jobcheck.paths import resolve_input_file

pytestmark = pytest.mark.fast


def test_an_existing_file_comes_back_resolved(tmp_path: Path) -> None:
    target = tmp_path / "checks.py"
    target.write_text("")
    assert resolve_input_file(str(target), "check file", "load_checks()") == target.resolve()


def test_a_relative_path_is_resolved_against_the_working_directory(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / "checks.py").write_text("")
    monkeypatch.chdir(tmp_path)
    assert resolve_input_file("checks.py", "check file", "load_checks()") == (
        (tmp_path / "checks.py").resolve())


def test_a_symlink_comes_back_as_its_target(tmp_path: Path) -> None:
    """`resolve` follows the link, so the two paths to one file are one entry
    in the loaded-files list rather than two."""

    target = tmp_path / "real.py"
    target.write_text("")
    link = tmp_path / "link.py"
    link.symlink_to(target)
    assert resolve_input_file(str(link), "check file", "load_checks()") == target.resolve()


def test_a_missing_relative_path_says_what_it_looked_at(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError) as raised:
        resolve_input_file("checks.py", "check file", "load_checks()")
    assert str(raised.value) == (
        f"No check file at 'checks.py': nothing at {tmp_path.resolve() / 'checks.py'}, "
        "where a relative path is resolved against the working directory. "
        "load_checks() names files explicitly; nothing is discovered."
    )


def test_a_missing_absolute_path_is_left_to_speak_for_itself() -> None:
    """An absolute path that is not there needs no second copy of itself."""

    with pytest.raises(ValueError) as raised:
        resolve_input_file("/no/such/file.py", "check file", "load_checks()")
    assert str(raised.value) == (
        "No check file at '/no/such/file.py'. load_checks() names files "
        "explicitly; nothing is discovered."
    )


def test_a_directory_is_named_as_the_mistake_it_is(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as raised:
        resolve_input_file(str(tmp_path), "override file", "load_overrides()")
    assert str(raised.value) == (
        f"No override file at {str(tmp_path)!r}: {tmp_path.resolve()} is a directory, "
        "so name the file in it. load_overrides() names files explicitly; "
        "nothing is discovered."
    )


def test_the_kind_and_the_caller_are_the_words_the_message_uses(tmp_path: Path) -> None:
    """Both loaders share this code, so neither may describe itself as the other."""

    with pytest.raises(ValueError) as raised:
        resolve_input_file(str(tmp_path / "absent.yaml"), "override file", "load_overrides()")
    message = str(raised.value)
    assert message.startswith("No override file at ")
    assert "load_overrides() names files explicitly" in message
