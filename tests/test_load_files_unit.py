"""Unit checks: loading check files by path, the only way checks are loaded.

The behavior a pipeline depends on is that a file written into a run directory
can be loaded without being importable as a package, that loading it twice does
nothing, and that a bad path is loud rather than silently empty.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

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


def test_a_file_named_twice_in_one_call_or_reloaded_is_loaded_once(
    fresh_registry: None, tmp_path: Path
) -> None:
    path = write_check_file(tmp_path, "checks.py", "AGAIN")
    reg.load_checks([path, path])
    reg.load_checks([path])
    assert [t.code for t in reg._CHECKS] == ["AGAIN"]


def test_every_file_of_one_name_gets_its_own_module(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Three, not two: a sequence stuck at one still names the first two apart,
    and only the third collides. Sharing a name, the later file would replace the
    earlier one in sys.modules."""

    paths = []
    for side in ("a", "b", "c"):
        (tmp_path / side).mkdir()
        paths.append(write_check_file(tmp_path / side, "checks.py", side.upper()))
    reg.load_checks(paths)
    names = [name for name in sys.modules if name.startswith("jobcheck_check_file_checks_")]
    assert len(names) == 3
    assert [t.code for t in reg._CHECKS] == ["A", "B", "C"]


def test_a_missing_path_raises_and_registers_nothing(fresh_registry: None, tmp_path: Path) -> None:
    good = write_check_file(tmp_path, "checks.py", "GOOD")
    with pytest.raises(ValueError, match="No check file at"):
        reg.load_checks([good, str(tmp_path / "absent.py")])
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


def test_no_bytecode_is_left_beside_a_loaded_file(fresh_registry: None, tmp_path: Path) -> None:
    # The file comes from a caller's data directory, which is a record of what
    # was read rather than somewhere this library may write to.
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


def test_the_bytecode_setting_is_restored_to_its_exact_value(fresh_registry: None,
                                                             tmp_path: Path) -> None:
    """`is False`, not merely falsy: a mutant setting it to None passed a
    truthiness check while leaving the interpreter in a state nobody chose."""

    import sys

    assert sys.dont_write_bytecode is False
    reg.load_checks([write_check_file(tmp_path, "checks.py", "EXACT")])
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
    """A file with no checks, such as a bundle, is still dropped and run again."""

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
    assert reg._LOADING == []

    broken.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('A', 'a')\n"
        "def a(row): return OK\n"
    )
    reg.clear_registry()
    assert not [name for name in sys.modules if name.startswith("jobcheck_check_file_")]
    reg.load_checks([good, str(broken)])
    assert [t.code for t in reg._CHECKS] == ["KEPT", "A"]


def test_an_interrupted_import_unwinds_the_load_stack(
    fresh_registry: None, tmp_path: Path
) -> None:
    """KeyboardInterrupt is not an Exception. The in-progress stack must still
    unwind, or the next load_checks would believe it is nested and never
    validate the dependency graph."""

    path = tmp_path / "check_interrupted.py"
    path.write_text("raise KeyboardInterrupt('ctrl-c during the import')\n")
    with pytest.raises(KeyboardInterrupt):
        reg.load_checks([str(path)])
    assert reg._LOADING == []


# --- bundles: a check file that loads check files ----------------------------
#
# One path in the caller's list, ten files behind it. What this has to get right
# is the boundary between the bundle and its members: when the dependency graph
# is validated, and whose checks a failure drops.


BUNDLE = '''
import os
from jobcheck import load_checks

load_checks({members!r}, base_dir=os.path.dirname(os.path.abspath(__file__)))
'''


def write_bundle(directory: Path, name: str, members: list[str]) -> str:
    """A check file whose whole job is to load the files beside it."""

    path = directory / name
    path.write_text(BUNDLE.format(members=members))
    return str(path)


def test_a_bundle_loads_the_files_it_names(fresh_registry: None, tmp_path: Path) -> None:
    write_check_file(tmp_path, "check_first.py", "FIRST")
    write_check_file(tmp_path, "check_second.py", "SECOND")
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_first.py", "check_second.py"])

    reg.load_checks([bundle])

    assert [t.code for t in reg._CHECKS] == ["FIRST", "SECOND"]
    # The members are loaded files in their own right, and they finish first.
    assert reg._LOADED_FILES == [
        str((tmp_path / "check_first.py").resolve()),
        str((tmp_path / "check_second.py").resolve()),
        str(Path(bundle).resolve()),
    ]


def test_a_prerequisite_may_arrive_after_the_bundle_that_needs_it(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Validation waits for the outermost call, so the order the caller wrote
    its list in is not a constraint on where a prerequisite lives."""

    dependent = tmp_path / "check_dependent.py"
    dependent.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('NEEDS_BASE', 'needs base', depends_on=['BASE'])\n"
        "def needs_base(row): return OK\n"
    )
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_dependent.py"])
    base = write_check_file(tmp_path, "check_base.py", "BASE")

    reg.load_checks([bundle, base])

    assert sorted(t.code for t in reg._CHECKS) == ["BASE", "NEEDS_BASE"]


def test_a_prerequisite_nothing_provides_still_fails_the_whole_load(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Deferring the validation must not lose it: the outermost call runs it."""

    dependent = tmp_path / "check_dependent.py"
    dependent.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('NEEDS_BASE', 'needs base', depends_on=['BASE'])\n"
        "def needs_base(row): return OK\n"
    )
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_dependent.py"])
    with pytest.raises(ValueError, match="depends on 'BASE', which is not registered"):
        reg.load_checks([bundle])


def test_a_dangling_prerequisite_names_the_way_out_of_the_load_it_leaves_behind(
    fresh_registry: None, tmp_path: Path
) -> None:
    """F.30. The validation runs after the files are recorded, so the file holding
    the bad depends_on is already loaded and the next call skips it -- correcting
    the typo in it changes nothing. The message is the only thing that says so, and
    clear_registry is the only way through."""

    path = tmp_path / "check_dependent.py"
    path.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('NEEDS_BASE', 'needs base', depends_on=['BASE'])\n"
        "def needs_base(row): return OK\n"
    )
    with pytest.raises(ValueError) as raised:
        reg.load_checks([str(path)])
    assert "call clear_registry() first" in str(raised.value)
    assert reg._LOADED_FILES == [str(path.resolve())]

    # The author fixes the file. It is skipped as already loaded, so the broken
    # check is still there and the same error comes back.
    path.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('BASE', 'base')\n"
        "def base(row): return OK\n"
        "@register_check('NEEDS_BASE', 'needs base', depends_on=['BASE'])\n"
        "def needs_base(row): return OK\n"
    )
    with pytest.raises(ValueError, match="depends on 'BASE', which is not registered"):
        reg.load_checks([str(path)])

    # What the message told them to do.
    reg.clear_registry()
    reg.load_checks([str(path)])
    assert sorted(check.code for check in reg._CHECKS) == ["BASE", "NEEDS_BASE"]


def test_a_bundle_that_names_itself_is_skipped_rather_than_recursing(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Without the in-progress guard this is a RecursionError, which says
    nothing about the file that caused it."""

    write_check_file(tmp_path, "check_first.py", "FIRST")
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_first.py", "all_checks.py"])
    reg.load_checks([bundle])
    assert [t.code for t in reg._CHECKS] == ["FIRST"]
    assert len(reg._LOADED_FILES) == 2


def test_a_bundle_and_a_member_of_one_name_get_different_module_names(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Written against a defect: the module name counted loaded files, and a
    bundle's name is computed before its members run, so a bundle and a member
    both called ``checks.py`` were given one name and the member's module
    replaced the bundle's in ``sys.modules`` -- where the bundle's own dataclass
    annotations, ``get_type_hints`` and ``pickle`` would have looked for it."""

    import sys

    inner = tmp_path / "inner"
    inner.mkdir()
    write_check_file(inner, "checks.py", "INNER")
    bundle = tmp_path / "checks.py"
    bundle.write_text(
        "import os, sys\n"
        "from jobcheck import OK, load_checks, register_check\n"
        "load_checks([os.path.join(os.path.dirname(os.path.abspath(__file__)),\n"
        "                          'inner', 'checks.py')])\n"
        "MARKER = 'the bundle'\n"
        "@register_check('OUTER', 'from the bundle itself')\n"
        "def own(row): return OK\n"
        "assert sys.modules[__name__].MARKER == 'the bundle', sys.modules[__name__]\n"
    )

    reg.load_checks([str(bundle)])

    assert sorted(t.code for t in reg._CHECKS) == ["INNER", "OUTER"]
    names = [name for name in sys.modules if name.startswith("jobcheck_check_file_")]
    assert len(names) == 2, names


def test_a_member_that_raises_propagates_through_its_bundle(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The member's error reaches the caller unchanged, and every level of the
    in-progress stack unwinds on the way out."""

    write_check_file(tmp_path, "check_first.py", "FIRST")
    (tmp_path / "check_broken.py").write_text("raise RuntimeError('boom in a member')\n")
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_first.py", "check_broken.py"])
    with pytest.raises(RuntimeError, match="boom in a member"):
        reg.load_checks([bundle])
    assert reg._LOADING == []
    assert reg._LOADED_FILES == [str((tmp_path / "check_first.py").resolve())]


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
    never load, and nothing would say so. The only test that a reader error names
    the setup file rather than a rule file."""

    path = _setup(tmp_path, "checks: [one.py]\nrules: [r.yaml]\nchecks: [two.py]\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == (
        f"{path}: key 'checks' appears twice in one mapping, on lines 1 and 3. "
        "YAML would keep only the last; remove one.")


def test_a_setup_file_that_is_not_a_mapping_says_so(
    fresh_registry: None, tmp_path: Path
) -> None:
    """A flat list is the rule file's shape, and the mistake somebody makes having
    written one of those first."""

    path = _setup(tmp_path, "- checks/all_checks.py\n")
    with pytest.raises(ValueError) as raised:
        reg.load_setup(path)
    assert str(raised.value) == (
        f"{path}: a setup file is a mapping of 'checks' and 'rules', got list.")


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
        f"{path}: 'checks' must be a list of paths, got str. "
        "Write it as a list even for one file.")


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


