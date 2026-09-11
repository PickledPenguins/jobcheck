"""Unit checks: loading check files by path, the only way checks are loaded.

The behaviour a pipeline depends on is that a file written into a run directory
can be loaded without being importable as a package, that loading it twice does
nothing, and that a bad path is loud rather than silently empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jobcheck import registry as reg

pytestmark = pytest.mark.fast

FILE_WITH_ONE_TEST = '''
from jobcheck import PASS, Status, CheckResult, register_check

@register_check("{code}", "{code} failed")
def rule(row):
    return PASS if row.get("value") == 1 else CheckResult(Status.INVALID, {{"value": row.get("value")}})
'''


def write_test_file(directory: Path, name: str, code: str) -> str:
    """A one-check file on disk, named as a caller's pipeline would name it."""

    path = directory / name
    path.write_text(FILE_WITH_ONE_TEST.format(code=code))
    return str(path)


def test_loads_a_file_by_path(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_checks([write_test_file(tmp_path, "checks.py", "BY_PATH")])
    assert [t.code for t in reg.CHECKS] == ["BY_PATH"]


def test_accepts_a_bare_string_as_one_path(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_checks(write_test_file(tmp_path, "checks.py", "SINGLE"))
    assert [t.code for t in reg.CHECKS] == ["SINGLE"]


def test_loaded_files_records_resolved_paths_in_order(fresh_registry: None, tmp_path: Path) -> None:
    first = write_test_file(tmp_path, "first.py", "FIRST")
    second = write_test_file(tmp_path, "second.py", "SECOND")
    reg.load_checks([first, second])
    assert reg.loaded_files() == [str(Path(first).resolve()), str(Path(second).resolve())]


def test_loaded_files_is_a_copy(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_checks([write_test_file(tmp_path, "checks.py", "COPY")])
    reg.loaded_files().append("invented")
    assert len(reg.loaded_files()) == 1


def test_the_same_file_twice_in_one_call_is_loaded_once(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "ONCE")
    reg.load_checks([path, path])
    assert [t.code for t in reg.CHECKS] == ["ONCE"]


def test_reloading_a_file_is_a_no_op(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "AGAIN")
    reg.load_checks([path])
    reg.load_checks([path])
    assert [t.code for t in reg.CHECKS] == ["AGAIN"]


def test_two_files_of_the_same_name_in_different_directories_both_load(
    fresh_registry: None, tmp_path: Path
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    reg.load_checks([
        write_test_file(left, "checks.py", "LEFT"),
        write_test_file(right, "checks.py", "RIGHT"),
    ])
    assert sorted(t.code for t in reg.CHECKS) == ["LEFT", "RIGHT"]


def test_a_missing_path_raises_and_registers_nothing(fresh_registry: None, tmp_path: Path) -> None:
    good = write_test_file(tmp_path, "checks.py", "GOOD")
    with pytest.raises(ValueError, match="No check file at"):
        reg.load_checks([good, str(tmp_path / "absent.py")])
    assert reg.CHECKS == []


def test_a_directory_is_not_a_test_file(fresh_registry: None, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No check file at"):
        reg.load_checks([str(tmp_path)])


def test_a_file_that_raises_on_import_propagates(fresh_registry: None, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError, match="boom"):
        reg.load_checks([str(path)])
    assert reg.loaded_files() == []


def test_a_file_that_raises_on_import_leaves_no_module_behind(
    fresh_registry: None, tmp_path: Path
) -> None:
    import sys

    path = tmp_path / "broken.py"
    path.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError):
        reg.load_checks([str(path)])
    assert not [name for name in sys.modules if name.startswith("jobcheck_check_file_")]


def test_a_prerequisite_may_live_in_another_file_of_the_same_call(
    fresh_registry: None, tmp_path: Path
) -> None:
    base = tmp_path / "base.py"
    base.write_text(FILE_WITH_ONE_TEST.format(code="BASE"))
    dependent = tmp_path / "dependent.py"
    dependent.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('DEPENDENT', 'DEPENDENT failed', depends_on=['BASE'])\n"
        "def rule(row):\n"
        "    return PASS\n"
    )
    reg.load_checks([str(dependent), str(base)])
    assert sorted(t.code for t in reg.CHECKS) == ["BASE", "DEPENDENT"]


def test_a_dangling_prerequisite_raises_at_the_end_of_the_call(
    fresh_registry: None, tmp_path: Path
) -> None:
    path = tmp_path / "dependent.py"
    path.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('DEPENDENT', 'DEPENDENT failed', depends_on=['ABSENT'])\n"
        "def rule(row):\n"
        "    return PASS\n"
    )
    with pytest.raises(ValueError, match="ABSENT"):
        reg.load_checks([str(path)])


def test_clear_registry_forgets_loaded_files(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "FORGOTTEN")
    reg.load_checks([path])
    reg.clear_registry()
    assert reg.loaded_files() == []


def test_a_file_can_be_loaded_again_after_clear_registry(fresh_registry: None, tmp_path: Path) -> None:
    path = write_test_file(tmp_path, "checks.py", "RELOADED")
    reg.load_checks([path])
    reg.clear_registry()
    reg.load_checks([path])
    assert [t.code for t in reg.CHECKS] == ["RELOADED"]


def test_path_loaded_tests_run(fresh_registry: None, tmp_path: Path) -> None:
    import pandas as pd

    from jobcheck import validate_row

    reg.load_checks([write_test_file(tmp_path, "checks.py", "RUNS")])
    failures = validate_row(pd.Series({"value": 2}))
    assert [f.code for f in failures] == ["RUNS"]


def test_no_bytecode_is_left_beside_a_loaded_file(fresh_registry: None, tmp_path: Path) -> None:
    # The file comes from a caller's data directory, which is a record of what
    # was read rather than somewhere this library may write to.
    reg.load_checks([write_test_file(tmp_path, "checks.py", "NO_PYC")])
    assert not (tmp_path / "__pycache__").exists()


def test_the_process_bytecode_setting_is_restored(fresh_registry: None, tmp_path: Path) -> None:
    import sys

    before = sys.dont_write_bytecode
    reg.load_checks([write_test_file(tmp_path, "checks.py", "RESTORED")])
    assert sys.dont_write_bytecode is before


def test_a_file_python_cannot_import_says_so(fresh_registry: None, tmp_path: Path) -> None:
    # A path that exists but has no importer -- the likely mistake being a rule
    # file passed where a check file was meant.
    path = tmp_path / "rules.yaml"
    path.write_text("- name: r\n")
    with pytest.raises(ValueError, match="as a Python file"):
        reg.load_checks([str(path)])


def test_the_loaded_module_is_registered_under_its_generated_name(
    fresh_registry: None, tmp_path: Path
) -> None:
    """A check file that imports itself, or is pickled by a worker, has to find it.

    Written against a surviving mutant: replacing the module object in
    ``sys.modules`` with ``None`` broke nothing any check asserted.
    """

    import sys

    reg.load_checks([write_test_file(tmp_path, "checks.py", "IN_SYS_MODULES")])
    names = [name for name in sys.modules
             if name.startswith("jobcheck_check_file_")]
    assert len(names) == 1
    module = sys.modules[names[0]]
    assert module is not None
    assert module.__file__ == str((tmp_path / "checks.py").resolve())


def test_clear_registry_evicts_the_module_it_registered(fresh_registry: None,
                                                        tmp_path: Path) -> None:
    """Otherwise a later load is a no-op -- Python caches modules -- and the
    registry stays silently empty. Written against a mutant that recorded
    ``None`` as the registering module's name."""

    import sys

    reg.load_checks([write_test_file(tmp_path, "checks.py", "EVICTED")])
    name = next(n for n in sys.modules if n.startswith("jobcheck_check_file_"))
    reg.clear_registry()
    assert name not in sys.modules


def test_the_bytecode_setting_is_restored_to_its_exact_value(fresh_registry: None,
                                                             tmp_path: Path) -> None:
    """`is False`, not merely falsy: a mutant setting it to None passed a
    truthiness check while leaving the interpreter in a state nobody chose."""

    import sys

    assert sys.dont_write_bytecode is False
    reg.load_checks([write_test_file(tmp_path, "checks.py", "EXACT")])
    assert sys.dont_write_bytecode is False


def test_the_bytecode_setting_is_restored_when_a_file_raises(fresh_registry: None,
                                                             tmp_path: Path) -> None:
    import sys

    path = tmp_path / "broken.py"
    path.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError):
        reg.load_checks([str(path)])
    assert sys.dont_write_bytecode is False


def test_a_file_that_registers_nothing_can_still_be_loaded_again(fresh_registry: None,
                                                                 tmp_path: Path) -> None:
    """The eviction has to cover the file itself, not only the checks it defines.

    A check file registers its module name as a side effect of the decorator, so
    a file with no checks in it is the only case where load_checks' own
    bookkeeping is what makes a reload work. Written against a mutant that
    recorded ``None`` there and passed everything else.
    """

    import sys

    path = tmp_path / "empty_checks.py"
    path.write_text("VALUE = 1\n")
    reg.load_checks([str(path)])
    name = next(n for n in sys.modules if n.startswith("jobcheck_check_file_"))
    assert sys.modules[name].VALUE == 1

    reg.clear_registry()
    assert name not in sys.modules
    assert reg.loaded_files() == []
