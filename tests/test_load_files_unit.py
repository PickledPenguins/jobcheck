"""Unit checks: loading check files by path, the only way checks are loaded.

The behavior a pipeline depends on is that a file written into a run directory
can be loaded without being importable as a package, that loading it twice
raises, and that a bad path is loud rather than silently empty.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from conftest import explain
from jobcheck import registry as reg

pytestmark = pytest.mark.fast

FILE_WITH_ONE_CHECK = '''
from jobcheck import OK, Status, Verdict, register_check

@register_check("{code}", "{code} failed")
def rule(row):
    return OK if row.get("value") == 1 else Verdict(Status.INVALID, {{"value": row.get("value")}})
'''


def write_check_file(directory: Path, name: str, code: str) -> str:
    """A one-check file on disk, named as a caller's pipeline would name it."""

    path = directory / name
    path.write_text(FILE_WITH_ONE_CHECK.format(code=code))
    return str(path)


def test_base_dir_anchors_the_relative_paths_of_one_call(fresh_registry: None,
                                                         tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    """What an entry point beside its check files needs: the same run whatever
    directory it was started from."""

    write_check_file(tmp_path, "checks.py", "ANCHORED")
    started_in = tmp_path / "started-in"
    started_in.mkdir()
    monkeypatch.chdir(started_in)
    reg.load_checks(["checks.py"], base_dir=tmp_path)
    assert [t.code for t in reg._CHECKS] == ["ANCHORED"]
    assert reg._LOADED_FILES == [str((tmp_path / "checks.py").resolve())]


def test_loaded_files_records_resolved_paths_in_order(fresh_registry: None, tmp_path: Path) -> None:
    first = write_check_file(tmp_path, "first.py", "FIRST")
    second = write_check_file(tmp_path, "second.py", "SECOND")
    reg.load_checks([first, second])
    assert reg._LOADED_FILES == [str(Path(first).resolve()), str(Path(second).resolve())]


def test_a_file_named_twice_in_one_call_or_reloaded_raises(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Before anything is imported: the repeat is the caller's mistake to fix."""

    path = write_check_file(tmp_path, "checks.py", "AGAIN")
    with pytest.raises(ValueError) as raised:
        reg.load_checks([path, path])
    assert str(raised.value) == (
        f"Check file listed twice or already loaded: {Path(path).resolve()}.")
    assert reg._CHECKS == []
    reg.load_checks([path])
    with pytest.raises(ValueError, match="listed twice or already loaded"):
        reg.load_checks([path])
    assert [t.code for t in reg._CHECKS] == ["AGAIN"]


def test_every_file_of_one_name_gets_its_own_module(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Sharing a name, the later file would replace the earlier one in sys.modules."""

    paths = []
    for side in ("a", "b", "c"):
        (tmp_path / side).mkdir()
        paths.append(write_check_file(tmp_path / side, "checks.py", side.upper()))
    reg.load_checks(paths)
    names = [name for name in sys.modules if name.startswith("jobcheck_check_file_checks_")]
    assert len(names) == 3
    assert [t.code for t in reg._CHECKS] == ["A", "B", "C"]


def test_a_file_gets_the_same_module_name_every_time_it_is_loaded(
    fresh_registry: None, tmp_path: Path
) -> None:
    path = write_check_file(tmp_path, "checks.py", "SAME")
    reg.load_checks([path])
    first = [name for name in sys.modules if name.startswith("jobcheck_check_file_checks_")]
    reg.clear_registry()
    reg.load_checks([path])
    again = [name for name in sys.modules if name.startswith("jobcheck_check_file_checks_")]
    assert len(first) == 1
    assert again == first


def test_a_missing_path_raises_and_registers_nothing(fresh_registry: None, tmp_path: Path) -> None:
    """load_checks imports files, so a module name is a missing file, not an import."""

    good = write_check_file(tmp_path, "checks.py", "GOOD")
    with pytest.raises(ValueError, match="No check file at"):
        reg.load_checks([good, str(tmp_path / "absent.py")])
    with pytest.raises(ValueError, match="No check file at 'os'"):
        reg.load_checks(["os"])
    assert reg._CHECKS == []


def test_a_prerequisite_may_live_in_another_file_of_the_same_call(
    fresh_registry: None, tmp_path: Path
) -> None:
    base = tmp_path / "base.py"
    base.write_text(FILE_WITH_ONE_CHECK.format(code="BASE"))
    dependent = tmp_path / "dependent.py"
    dependent.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('DEPENDENT', 'DEPENDENT failed', depends_on=['BASE'])\n"
        "def rule(row):\n"
        "    return OK\n"
    )
    reg.load_checks([str(dependent), str(base)])
    assert sorted(t.code for t in reg._CHECKS) == ["BASE", "DEPENDENT"]


def test_a_file_loaded_by_path_registers_its_checks_and_they_run(
    fresh_registry: None, tmp_path: Path
) -> None:
    import pandas as pd

    from conftest import failures

    reg.load_checks([write_check_file(tmp_path, "checks.py", "RUNS")])
    assert [t.code for t in reg._CHECKS] == ["RUNS"]
    assert [f.code for f in failures(pd.Series({"value": 2}))] == ["RUNS"]


def test_no_bytecode_is_left_beside_a_loaded_file(fresh_registry: None, tmp_path: Path,
                                                  monkeypatch: Any) -> None:
    # The file comes from a caller's data directory, which is a record of what
    # was read rather than somewhere this library may write to.
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    reg.load_checks([write_check_file(tmp_path, "checks.py", "NO_PYC")])
    assert not (tmp_path / "__pycache__").exists()


def test_a_file_python_cannot_import_says_so(fresh_registry: None, tmp_path: Path) -> None:
    # A path that exists but has no importer -- the likely mistake being a rule
    # file passed where a check file was meant.
    path = tmp_path / "rules.yaml"
    path.write_text("- name: r\n  message: \"why the rule exists\"\n")
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

    reg.load_checks([write_check_file(tmp_path, "checks.py", "IN_SYS_MODULES")])
    names = [name for name in sys.modules
             if name.startswith("jobcheck_check_file_")]
    assert len(names) == 1
    module = sys.modules[names[0]]
    assert module is not None
    assert module.__file__ == str((tmp_path / "checks.py").resolve())


def test_a_module_that_registered_by_plain_import_stays_imported(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The documented limit: checks register only in the files `load_checks`
    is given. A module registering by plain import is Python's to cache, so
    after a clear it registers nothing until the process restarts."""

    import importlib.util
    import sys

    path = tmp_path / "shared_checks.py"
    path.write_text(FILE_WITH_ONE_CHECK.format(code="IMPORTED"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("shared_checks_by_import", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["shared_checks_by_import"] = module
    try:
        spec.loader.exec_module(module)
        assert [check.code for check in reg._CHECKS] == ["IMPORTED"]
        reg.clear_registry()
        assert "shared_checks_by_import" in sys.modules
    finally:
        sys.modules.pop("shared_checks_by_import", None)


def test_a_module_a_check_file_imports_still_writes_its_bytecode(
    fresh_registry: None, tmp_path: Path, monkeypatch: Any
) -> None:
    """Only the check file goes without a .pyc: nothing process-wide is switched off."""

    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    library = tmp_path / "library"
    library.mkdir()
    (library / "bytecode_helper_module.py").write_text("LIMIT = 1\n")
    monkeypatch.syspath_prepend(str(library))
    path = tmp_path / "checks.py"
    path.write_text("import bytecode_helper_module\n")
    try:
        reg.load_checks([str(path)])
    finally:
        sys.modules.pop("bytecode_helper_module", None)
    assert list((library / "__pycache__").glob("bytecode_helper_module.*.pyc"))
    assert not (tmp_path / "__pycache__").exists()
    assert sys.dont_write_bytecode is False


def test_a_file_that_registers_nothing_can_still_be_loaded_again(fresh_registry: None,
                                                                 tmp_path: Path) -> None:
    """A file with no checks is still dropped and run again."""

    import sys

    path = tmp_path / "empty_checks.py"
    path.write_text("VALUE = 1\n")
    reg.load_checks([str(path)])
    name = next(n for n in sys.modules if n.startswith("jobcheck_check_file_"))
    assert sys.modules[name].VALUE == 1

    reg.clear_registry()
    assert name not in sys.modules
    assert reg._LOADED_FILES == []


def test_a_file_that_raises_is_not_rolled_back_and_clear_registry_recovers(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The error reaches the caller and ends a run. What the file registered
    before the failing line stays, and the file is not recorded as loaded;
    loading again in the same process starts with clear_registry()."""

    import sys

    good = write_check_file(tmp_path, "good.py", "KEPT")
    broken = tmp_path / "broken.py"
    broken.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('A', 'a')\n"
        "def a(row): return OK\n"
        "raise RuntimeError('boom after one registration')\n"
    )
    with pytest.raises(RuntimeError, match="boom"):
        reg.load_checks([good, str(broken)])
    assert [t.code for t in reg._CHECKS] == ["KEPT", "A"]
    assert reg._LOADED_FILES == [str(Path(good).resolve())]
    # And what registered runs: the failure path must leave the evaluation order
    # recomputed, not a stale cache that would validate a row against nothing.
    assert [o.code for o in explain(pd.Series({"value": 1}))] == ["KEPT", "A"]

    broken.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('A', 'a')\n"
        "def a(row): return OK\n"
    )
    reg.clear_registry()
    assert not [name for name in sys.modules if name.startswith("jobcheck_check_file_")]
    reg.load_checks([good, str(broken)])
    assert [t.code for t in reg._CHECKS] == ["KEPT", "A"]


NEEDS_BASE = (
    "from jobcheck import OK, register_check\n"
    "@register_check('NEEDS_BASE', 'needs base', depends_on=['BASE'])\n"
    "def needs_base(row): return OK\n"
)


def test_a_later_call_may_depend_on_a_file_an_earlier_call_loaded(
    fresh_registry: None, tmp_path: Path
) -> None:
    base = write_check_file(tmp_path, "check_base.py", "BASE")
    dependent = tmp_path / "check_dependent.py"
    dependent.write_text(NEEDS_BASE)
    reg.load_checks([base])
    reg.load_checks([str(dependent)])
    assert sorted(t.code for t in reg._CHECKS) == ["BASE", "NEEDS_BASE"]


def test_an_earlier_call_may_not_depend_on_a_file_a_later_call_loads(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Each call validates the graph as it returns."""

    dependent = tmp_path / "check_dependent.py"
    dependent.write_text(NEEDS_BASE)
    with pytest.raises(ValueError, match="depends on 'BASE', which is not registered"):
        reg.load_checks([str(dependent)])


def test_a_file_fixed_after_a_dangling_prerequisite_loads_after_clear_registry(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The validation runs after the files are recorded, so the file holding the bad
    depends_on is already loaded: loading it again raises until the registry is cleared."""

    path = tmp_path / "check_dependent.py"
    path.write_text(NEEDS_BASE)
    with pytest.raises(ValueError, match="depends on 'BASE', which is not registered"):
        reg.load_checks([str(path)])
    assert reg._LOADED_FILES == [str(path.resolve())]

    path.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('BASE', 'base')\n"
        "def base(row): return OK\n" + NEEDS_BASE.split("\n", 1)[1]
    )
    with pytest.raises(ValueError, match="already loaded"):
        reg.load_checks([str(path)])

    reg.clear_registry()
    reg.load_checks([str(path)])
    assert sorted(check.code for check in reg._CHECKS) == ["BASE", "NEEDS_BASE"]


# --- load_setup: one file, one call -----------------------------------------


def _setup(tmp_path: Path, text: str) -> str:
    path = tmp_path / "setup.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_a_setup_file_loads_the_checks_and_returns_the_rules(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The whole of configuring this library in one call: the check files are
    registered, the rules come back to hand to `validate`."""

    (tmp_path / "check_one.py").write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('A_CODE', 'm')\n"
        "def one(row): return OK\n",
        encoding="utf-8",
    )
    (tmp_path / "r.yaml").write_text(
        "- name: off_everywhere\n  message: \"m\"\n  action: disable\n"
        "  codes: [A_CODE]\n  match: all\n",
        encoding="utf-8",
    )
    rules = reg.load_setup(_setup(tmp_path, "checks: [check_one.py]\nrules: [r.yaml]\n"))

    assert [check.code for check in reg._CHECKS] == ["A_CODE"]
    assert [rule.name for rule in rules] == ["off_everywhere"]


def test_setup_paths_are_relative_to_the_setup_file_not_the_caller(
    fresh_registry: None, tmp_path: Path, monkeypatch: Any
) -> None:
    """The file and the paths in it travel together: a setup file moved to another
    machine, or run from another directory, still finds its own check files."""

    (tmp_path / "check_one.py").write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('A_CODE', 'm')\n"
        "def one(row): return OK\n",
        encoding="utf-8",
    )
    setup = _setup(tmp_path, "checks: [check_one.py]\n")
    monkeypatch.chdir(tmp_path.parent)

    assert reg.load_setup(setup) == []
    assert [check.code for check in reg._CHECKS] == ["A_CODE"]


def test_a_key_given_twice_in_a_setup_file_is_refused(
    fresh_registry: None, tmp_path: Path
) -> None:
    """PyYAML keeps the second `checks:`, so the files the first one named would
    never load, and nothing would say so."""

    path = _setup(tmp_path, "checks: [one.py]\nrules: [r.yaml]\nchecks: [two.py]\n")
    with pytest.raises(yaml.YAMLError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == (
        f'a key appears twice in this mapping\n  in "{path}", line 1, column 1')


def test_a_setup_file_that_is_not_utf8_names_itself(
    fresh_registry: None, tmp_path: Path
) -> None:
    path = tmp_path / "setup.yaml"
    path.write_bytes(b"checks: [caf\xe9.py]\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(str(path))
    assert str(raised.value) == (
        f"{path}: not UTF-8 text: 'utf-8' codec can't decode byte 0xe9 in position 12: "
        "invalid continuation byte. Save the file as UTF-8.")


def test_a_setup_file_that_is_not_a_mapping_says_so(
    fresh_registry: None, tmp_path: Path
) -> None:
    """A flat list is the rule file's shape, and the mistake somebody makes having
    written one of those first."""

    path = _setup(tmp_path, "- checks/check_age.py\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == f"{path}: a setup file is a mapping, got list."


def test_a_setup_key_yaml_reads_as_a_number_is_named_rather_than_crashing(
    fresh_registry: None, tmp_path: Path
) -> None:
    """An int key beside a text one cannot be sorted, which raised a bare TypeError."""

    path = _setup(tmp_path, "checks: [x.py]\n1: a\nextra: b\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == (
        f"{path}: unknown key(s) 1, 'extra'. A setup file holds 'checks', 'rules'.")


def test_a_setup_file_naming_only_rules_is_refused(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Rules switch checks on and off, so a setup with none configures nothing."""

    path = _setup(tmp_path, "rules: [r.yaml]\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == (
        f"{path}: 'checks' is required: a setup file names the files to load.")


def test_a_string_where_a_list_belongs_is_refused(
    fresh_registry: None, tmp_path: Path
) -> None:
    """YAML reads `checks: one.py` as a string, and a string is a list of
    characters -- without this it would try to load a file per character."""

    path = _setup(tmp_path, "checks: one.py\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == (
        f"{path}: 'checks' must be a list of paths, got str.")


def test_an_empty_checks_list_is_refused(fresh_registry: None, tmp_path: Path) -> None:
    path = _setup(tmp_path, "checks: []\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == f"{path}: 'checks' is empty: name at least one file."


def test_a_setup_entry_that_is_not_a_path_names_its_position(
    fresh_registry: None, tmp_path: Path
) -> None:
    path = _setup(tmp_path, "checks: [ok.py, 7]\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == f"{path}: 'checks' entry 2 must be a path, got int."


def test_an_empty_rules_list_is_allowed(fresh_registry: None, tmp_path: Path) -> None:
    """`rules: []` is the baseline every rule file is a deviation from, the same
    reading `--rules` with no paths has."""

    (tmp_path / "check_one.py").write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('A_CODE', 'm')\n"
        "def one(row): return OK\n",
        encoding="utf-8",
    )
    assert reg.load_setup(_setup(tmp_path, "checks: [check_one.py]\nrules: []\n")) == []


def test_a_missing_setup_file_says_where_it_looked(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.load_setup("nope.yaml")
    assert "No setup file at 'nope.yaml'" in str(raised.value)
    assert "load_setup() names files explicitly" in str(raised.value)


