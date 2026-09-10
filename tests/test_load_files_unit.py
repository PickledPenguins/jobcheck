"""Unit tests: loading test files by path, the counterpart to load_suites.

The behaviour a pipeline depends on is that a file written into a run directory
can be loaded without being importable as a package, that loading it twice does
nothing, and that a bad path is loud rather than silently empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pandas_row_validation import registry as reg

pytestmark = pytest.mark.fast

FILE_WITH_ONE_TEST = '''
from pandas_row_validation import PASS, Status, TestResult, test_group

g = test_group()


@g("{code}", "{code} failed")
def rule(row):
    return PASS if row.get("value") == 1 else TestResult(Status.INVALID, {{"value": row.get("value")}})
'''


def write_test_file(directory: Path, name: str, code: str) -> str:
    """A one-test file on disk, named as a caller's pipeline would name it."""

    path = directory / name
    path.write_text(FILE_WITH_ONE_TEST.format(code=code))
    return str(path)


def test_loads_a_file_by_path(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_test_files([write_test_file(tmp_path, "checks.py", "BY_PATH")])
    assert [t.code for t in reg.TESTS] == ["BY_PATH"]


def test_accepts_a_bare_string_as_one_path(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_test_files(write_test_file(tmp_path, "checks.py", "SINGLE"))
    assert [t.code for t in reg.TESTS] == ["SINGLE"]


def test_a_path_loaded_file_lands_in_the_base_suite(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_test_files([write_test_file(tmp_path, "checks.py", "BASED")])
    assert reg.TESTS[0].suite == reg.BASE_SUITE
    assert reg.BASE_SUITE in reg.loaded_suites()


def test_loaded_files_records_resolved_paths_in_order(fresh_registry: None, tmp_path: Path) -> None:
    first = write_test_file(tmp_path, "first.py", "FIRST")
    second = write_test_file(tmp_path, "second.py", "SECOND")
    reg.load_test_files([first, second])
    assert reg.loaded_files() == [str(Path(first).resolve()), str(Path(second).resolve())]


def test_loaded_files_is_a_copy(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_test_files([write_test_file(tmp_path, "checks.py", "COPY")])
    reg.loaded_files().append("invented")
    assert len(reg.loaded_files()) == 1


def test_the_same_file_twice_in_one_call_is_loaded_once(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "ONCE")
    reg.load_test_files([path, path])
    assert [t.code for t in reg.TESTS] == ["ONCE"]


def test_reloading_a_file_is_a_no_op(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "AGAIN")
    reg.load_test_files([path])
    reg.load_test_files([path])
    assert [t.code for t in reg.TESTS] == ["AGAIN"]


def test_two_files_of_the_same_name_in_different_directories_both_load(
    fresh_registry: None, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    reg.load_test_files([
        write_test_file(left, "checks.py", "LEFT"),
        write_test_file(right, "checks.py", "RIGHT"),
    ])
    assert sorted(t.code for t in reg.TESTS) == ["LEFT", "RIGHT"]


def test_a_missing_path_raises_and_registers_nothing(fresh_registry: None, tmp_path: Path) -> None:
    good = write_test_file(tmp_path, "checks.py", "GOOD")
    with pytest.raises(ValueError, match="No test file at"):
        reg.load_test_files([good, str(tmp_path / "absent.py")])
    assert reg.TESTS == []


def test_a_directory_is_not_a_test_file(fresh_registry: None, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No test file at"):
        reg.load_test_files([str(tmp_path)])


def test_a_file_that_raises_on_import_propagates(fresh_registry: None, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError, match="boom"):
        reg.load_test_files([str(path)])
    assert reg.loaded_files() == []


def test_a_file_that_raises_on_import_leaves_no_module_behind(
    fresh_registry: None, tmp_path: Path
) -> None:
    import sys

    path = tmp_path / "broken.py"
    path.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError):
        reg.load_test_files([str(path)])
    assert not [name for name in sys.modules if name.startswith("pandas_row_validation_test_file_")]


def test_a_prerequisite_may_live_in_another_file_of_the_same_call(
    fresh_registry: None, tmp_path: Path
) -> None:
    base = tmp_path / "base.py"
    base.write_text(FILE_WITH_ONE_TEST.format(code="BASE"))
    dependent = tmp_path / "dependent.py"
    dependent.write_text(
        "from pandas_row_validation import PASS, test_group\n"
        "g = test_group(depends_on=['BASE'])\n"
        "@g('DEPENDENT', 'DEPENDENT failed')\n"
        "def rule(row):\n"
        "    return PASS\n"
    )
    reg.load_test_files([str(dependent), str(base)])
    assert sorted(t.code for t in reg.TESTS) == ["BASE", "DEPENDENT"]


def test_a_dangling_prerequisite_raises_at_the_end_of_the_call(
    fresh_registry: None, tmp_path: Path
) -> None:
    path = tmp_path / "dependent.py"
    path.write_text(
        "from pandas_row_validation import PASS, test_group\n"
        "g = test_group(depends_on=['ABSENT'])\n"
        "@g('DEPENDENT', 'DEPENDENT failed')\n"
        "def rule(row):\n"
        "    return PASS\n"
    )
    with pytest.raises(ValueError, match="ABSENT"):
        reg.load_test_files([str(path)])


def test_clear_registry_forgets_loaded_files(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "FORGOTTEN")
    reg.load_test_files([path])
    reg.clear_registry()
    assert reg.loaded_files() == []


def test_a_file_can_be_loaded_again_after_clear_registry(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "RELOADED")
    reg.load_test_files([path])
    reg.clear_registry()
    reg.load_test_files([path])
    assert [t.code for t in reg.TESTS] == ["RELOADED"]


def test_path_loaded_tests_run(fresh_registry: None, tmp_path: Path) -> None:
    import pandas as pd

    from pandas_row_validation import validate_row

    reg.load_test_files([write_test_file(tmp_path, "checks.py", "RUNS")])
    failures = validate_row(pd.Series({"value": 2}))
    assert [f.code for f in failures] == ["RUNS"]


def test_no_bytecode_is_left_beside_a_loaded_file(fresh_registry: None, tmp_path: Path) -> None:
    # The file comes from a caller's data directory, which is a record of what
    # was read rather than somewhere this library may write to.
    reg.load_test_files([write_test_file(tmp_path, "checks.py", "NO_PYC")])
    assert not (tmp_path / "__pycache__").exists()


def test_the_process_bytecode_setting_is_restored(fresh_registry: None, tmp_path: Path) -> None:
    import sys

    before = sys.dont_write_bytecode
    reg.load_test_files([write_test_file(tmp_path, "checks.py", "RESTORED")])
    assert sys.dont_write_bytecode is before
