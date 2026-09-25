"""The bytecode interface reader, against the commit that holds the bytecode.

The directory it reads was deleted from the working tree in the commit after
`3fce4b4`, so the reader takes it from history by default. These pin that the
default still finds it, and that a directory argument still works for a
restored copy.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from conftest import PROJECT_ROOT

pytestmark = pytest.mark.fast


def reader() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "read_bytecode_api", Path(PROJECT_ROOT) / "scripts" / "read_bytecode_api.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def history_has_the_commit() -> bool:
    done = subprocess.run(["git", "-C", PROJECT_ROOT, "cat-file", "-e", "3fce4b4^{commit}"],
                          capture_output=True)
    return done.returncode == 0


needs_history = pytest.mark.skipif(not history_has_the_commit(),
                                   reason="a clone without the recovery commit")


@needs_history
def test_the_default_reads_the_bytecode_out_of_history() -> None:
    module = reader()
    files = module.from_history()
    # Both generations of every check-era module, lint and parallel among them.
    assert "lint.cpython-312.pyc" in files and "parallel.cpython-312.pyc" in files
    text = module.report("jobcheck", files)
    assert "## `lint.cpython-312.pyc` (source was 14,326 bytes)" in text


@needs_history
def test_a_directory_argument_reads_the_same_files(tmp_path: Path) -> None:
    module = reader()
    files = module.from_history()
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    assert module.from_directory(tmp_path) == files


def test_a_commit_git_cannot_find_is_a_runtime_error() -> None:
    with pytest.raises(RuntimeError):
        reader().from_history(commit="0000000")


def test_a_missing_directory_and_a_surplus_argument_exit_2(capsys: Any) -> None:
    module = reader()
    assert module.main(["read_bytecode_api.py", "/no/such/dir"]) == 2
    assert module.main(["read_bytecode_api.py", "a", "b"]) == 2
    err = capsys.readouterr().err
    assert "No such directory: /no/such/dir" in err and "usage:" in err
