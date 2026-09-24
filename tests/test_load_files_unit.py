"""Unit checks: loading check files by path, the only way checks are loaded.

The behavior a pipeline depends on is that a file written into a run directory
can be loaded without being importable as a package, that loading it twice does
nothing, and that a bad path is loud rather than silently empty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jobcheck import registry as reg

pytestmark = pytest.mark.fast

FILE_WITH_ONE_CHECK = '''
from jobcheck import PASS, Status, CheckResult, register_check

@register_check("{code}", "{code} failed")
def rule(row):
    return PASS if row.get("value") == 1 else CheckResult(Status.INVALID, {{"value": row.get("value")}})
'''


def write_check_file(directory: Path, name: str, code: str) -> str:
    """A one-check file on disk, named as a caller's pipeline would name it."""

    path = directory / name
    path.write_text(FILE_WITH_ONE_CHECK.format(code=code))
    return str(path)


def test_loads_a_file_by_path(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_checks([write_check_file(tmp_path, "checks.py", "BY_PATH")])
    assert [t.code for t in reg.CHECKS] == ["BY_PATH"]





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
    assert [t.code for t in reg.CHECKS] == ["ANCHORED"]
    assert reg.loaded_check_files() == [str((tmp_path / "checks.py").resolve())]


def test_an_absolute_path_is_loaded_whatever_base_dir_says(fresh_registry: None,
                                                           tmp_path: Path) -> None:
    path = write_check_file(tmp_path, "checks.py", "ABSOLUTE")
    reg.load_checks([path], base_dir=tmp_path / "no-such-directory")
    assert [t.code for t in reg.CHECKS] == ["ABSOLUTE"]


def test_a_missing_file_under_base_dir_names_that_directory(fresh_registry: None,
                                                            tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=f"resolved against base_dir {tmp_path}"):
        reg.load_checks(["absent.py"], base_dir=tmp_path)


def test_loaded_files_records_resolved_paths_in_order(fresh_registry: None, tmp_path: Path) -> None:
    first = write_check_file(tmp_path, "first.py", "FIRST")
    second = write_check_file(tmp_path, "second.py", "SECOND")
    reg.load_checks([first, second])
    assert reg.loaded_check_files() == [str(Path(first).resolve()), str(Path(second).resolve())]


def test_loaded_files_is_a_copy(fresh_registry: None, tmp_path: Path) -> None:
    reg.load_checks([write_check_file(tmp_path, "checks.py", "COPY")])
    reg.loaded_check_files().append("invented")
    assert len(reg.loaded_check_files()) == 1


def test_the_same_file_twice_in_one_call_is_loaded_once(fresh_registry: None, tmp_path: Path) -> None:
    path = write_check_file(tmp_path, "checks.py", "ONCE")
    reg.load_checks([path, path])
    assert [t.code for t in reg.CHECKS] == ["ONCE"]


def test_reloading_a_file_is_a_no_op(fresh_registry: None, tmp_path: Path) -> None:
    path = write_check_file(tmp_path, "checks.py", "AGAIN")
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
        write_check_file(left, "checks.py", "LEFT"),
        write_check_file(right, "checks.py", "RIGHT"),
    ])
    assert sorted(t.code for t in reg.CHECKS) == ["LEFT", "RIGHT"]


def test_a_missing_path_raises_and_registers_nothing(fresh_registry: None, tmp_path: Path) -> None:
    good = write_check_file(tmp_path, "checks.py", "GOOD")
    with pytest.raises(ValueError, match="No check file at"):
        reg.load_checks([good, str(tmp_path / "absent.py")])
    assert reg.CHECKS == []


def test_a_directory_is_not_a_check_file(fresh_registry: None, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No check file at"):
        reg.load_checks([str(tmp_path)])


def test_a_file_that_raises_on_import_propagates(fresh_registry: None, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(RuntimeError, match="boom"):
        reg.load_checks([str(path)])
    assert reg.loaded_check_files() == []


def test_a_file_that_raises_after_registering_leaves_none_of_its_checks_behind(
    fresh_registry: None, tmp_path: Path
) -> None:
    """A file that registers A and B and then raises must leave neither: the
    registry and loaded_check_files() would otherwise disagree about it, and a
    retry of the corrected file would be refused as a duplicate of A."""

    good = write_check_file(tmp_path, "good.py", "KEPT")
    broken = tmp_path / "broken.py"
    broken.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('A', 'a')\n"
        "def a(row): return PASS\n"
        "@register_check('B', 'b')\n"
        "def b(row): return PASS\n"
        "raise RuntimeError('boom after two registrations')\n"
    )
    with pytest.raises(RuntimeError, match="boom"):
        reg.load_checks([good, str(broken)])
    assert [t.code for t in reg.CHECKS] == ["KEPT"]
    assert reg.loaded_check_files() == [str(Path(good).resolve())]

    broken.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('A', 'a')\n"
        "def a(row): return PASS\n"
    )
    reg.load_checks([str(broken)])
    assert [t.code for t in reg.CHECKS] == ["KEPT", "A"]


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
    base.write_text(FILE_WITH_ONE_CHECK.format(code="BASE"))
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
    path = write_check_file(tmp_path, "checks.py", "FORGOTTEN")
    reg.load_checks([path])
    reg.clear_registry()
    assert reg.loaded_check_files() == []


def test_a_file_can_be_loaded_again_after_clear_registry(fresh_registry: None, tmp_path: Path) -> None:
    path = write_check_file(tmp_path, "checks.py", "RELOADED")
    reg.load_checks([path])
    reg.clear_registry()
    reg.load_checks([path])
    assert [t.code for t in reg.CHECKS] == ["RELOADED"]


def test_path_loaded_checks_run(fresh_registry: None, tmp_path: Path) -> None:
    import pandas as pd

    from jobcheck import validate_row

    reg.load_checks([write_check_file(tmp_path, "checks.py", "RUNS")])
    failures = validate_row(pd.Series({"value": 2}))
    assert [f.code for f in failures] == ["RUNS"]


def test_no_bytecode_is_left_beside_a_loaded_file(fresh_registry: None, tmp_path: Path) -> None:
    # The file comes from a caller's data directory, which is a record of what
    # was read rather than somewhere this library may write to.
    reg.load_checks([write_check_file(tmp_path, "checks.py", "NO_PYC")])
    assert not (tmp_path / "__pycache__").exists()


def test_the_process_bytecode_setting_is_restored(fresh_registry: None, tmp_path: Path) -> None:
    import sys

    before = sys.dont_write_bytecode
    reg.load_checks([write_check_file(tmp_path, "checks.py", "RESTORED")])
    assert sys.dont_write_bytecode is before


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


def test_clear_registry_evicts_the_module_it_registered(fresh_registry: None,
                                                        tmp_path: Path) -> None:
    """Otherwise a later load is a no-op -- Python caches modules -- and the
    registry stays silently empty. Written against a mutant that recorded
    ``None`` as the registering module's name."""

    import sys

    reg.load_checks([write_check_file(tmp_path, "checks.py", "EVICTED")])
    name = next(n for n in sys.modules if n.startswith("jobcheck_check_file_"))
    reg.clear_registry()
    assert name not in sys.modules


def test_a_module_that_registered_by_plain_import_is_evicted_too(
    fresh_registry: None, tmp_path: Path
) -> None:
    """`load_checks` records the modules it imports itself, so the line in
    `register_check` that records `fn.__module__` is what covers every other
    route in: a check file importing a shared module of its own, which Python
    would otherwise keep cached and which would register nothing on the next
    load.

    The cost of that decision, and why it is pinned rather than dropped: the
    module a check registers from is evicted whatever it is, a test module
    included, and after eviction ``sys.modules[name]`` is None. A dataclass
    whose annotations have to be resolved -- ``ClassVar``, ``InitVar``, or
    anything calling ``get_type_hints`` -- then raises ``AttributeError:
    'NoneType' object has no attribute '__dict__'`` from ``dataclasses``, which
    looks its module up there. Define such a class at module level, or before
    the clear.
    """

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
        assert [check.code for check in reg.CHECKS] == ["IMPORTED"]
        reg.clear_registry()
        assert "shared_checks_by_import" not in sys.modules
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
    assert reg.loaded_check_files() == []


def test_a_bare_string_path_is_refused_by_load_checks(fresh_registry: None) -> None:
    """A string is a list of its characters, so iterating one loads nothing and
    reports a missing file named 'c'. Say what to pass instead."""

    with pytest.raises(TypeError, match=r"load_checks takes a list of paths"):
        reg.load_checks("checks.py")  # type: ignore[arg-type]


def test_a_bare_string_path_is_refused_by_load_rules(fresh_registry: None) -> None:
    with pytest.raises(TypeError, match=r"load_rules takes a list of paths"):
        reg.load_rules("rules.yaml")  # type: ignore[arg-type]


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

    assert [t.code for t in reg.CHECKS] == ["FIRST", "SECOND"]
    # The members are loaded files in their own right, and they finish first.
    assert reg.loaded_check_files() == [
        str((tmp_path / "check_first.py").resolve()),
        str((tmp_path / "check_second.py").resolve()),
        str(Path(bundle).resolve()),
    ]


def test_a_member_is_not_loaded_twice_when_the_caller_names_it_too(
    fresh_registry: None, tmp_path: Path
) -> None:
    member = write_check_file(tmp_path, "check_first.py", "FIRST")
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_first.py"])
    reg.load_checks([member, bundle])
    assert [t.code for t in reg.CHECKS] == ["FIRST"]


def test_a_prerequisite_may_arrive_after_the_bundle_that_needs_it(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Validation waits for the outermost call, so the order the caller wrote
    its list in is not a constraint on where a prerequisite lives."""

    dependent = tmp_path / "check_dependent.py"
    dependent.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('NEEDS_BASE', 'needs base', depends_on=['BASE'])\n"
        "def needs_base(row): return PASS\n"
    )
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_dependent.py"])
    base = write_check_file(tmp_path, "check_base.py", "BASE")

    reg.load_checks([bundle, base])

    assert sorted(t.code for t in reg.CHECKS) == ["BASE", "NEEDS_BASE"]


def test_a_prerequisite_nothing_provides_still_fails_the_whole_load(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Deferring the validation must not lose it: the outermost call runs it."""

    dependent = tmp_path / "check_dependent.py"
    dependent.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('NEEDS_BASE', 'needs base', depends_on=['BASE'])\n"
        "def needs_base(row): return PASS\n"
    )
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_dependent.py"])
    with pytest.raises(ValueError, match="depends on 'BASE', which is not registered"):
        reg.load_checks([bundle])


def test_a_member_that_raises_leaves_the_earlier_members_loaded(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Loading is per file at every depth. The registry and the loaded-file
    list have to agree afterwards, or the corrected bundle is skipped as
    already loaded and its missing checks never come back."""

    write_check_file(tmp_path, "check_first.py", "FIRST")
    broken = tmp_path / "check_broken.py"
    broken.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('BROKEN', 'broken')\n"
        "def broken(row): return PASS\n"
        "raise RuntimeError('boom half way through the bundle')\n"
    )
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_first.py", "check_broken.py"])

    with pytest.raises(RuntimeError, match="boom half way through the bundle"):
        reg.load_checks([bundle])

    assert [t.code for t in reg.CHECKS] == ["FIRST"]
    assert reg.loaded_check_files() == [str((tmp_path / "check_first.py").resolve())]

    # The author fixes the member and runs the same command again.
    broken.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('BROKEN', 'broken')\n"
        "def broken(row): return PASS\n"
    )
    reg.load_checks([bundle])
    assert [t.code for t in reg.CHECKS] == ["FIRST", "BROKEN"]


def test_a_bundle_that_raises_drops_its_own_checks_and_keeps_its_members(
    fresh_registry: None, tmp_path: Path
) -> None:
    write_check_file(tmp_path, "check_first.py", "FIRST")
    bundle = tmp_path / "all_checks.py"
    bundle.write_text(
        "import os\n"
        "from jobcheck import PASS, load_checks, register_check\n"
        "@register_check('BUNDLE_OWN', 'the bundle registered this itself')\n"
        "def own(row): return PASS\n"
        "load_checks(['check_first.py'], base_dir=os.path.dirname(os.path.abspath(__file__)))\n"
        "raise RuntimeError('boom after the members loaded')\n"
    )

    with pytest.raises(RuntimeError, match="boom after the members loaded"):
        reg.load_checks([str(bundle)])

    assert [t.code for t in reg.CHECKS] == ["FIRST"]
    assert reg.loaded_check_files() == [str((tmp_path / "check_first.py").resolve())]
    assert reg._LOADING == []


def test_a_bundle_that_names_itself_is_skipped_rather_than_recursing(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Without the in-progress guard this is a RecursionError, which says
    nothing about the file that caused it."""

    write_check_file(tmp_path, "check_first.py", "FIRST")
    bundle = write_bundle(tmp_path, "all_checks.py", ["check_first.py", "all_checks.py"])
    reg.load_checks([bundle])
    assert [t.code for t in reg.CHECKS] == ["FIRST"]
    assert len(reg.loaded_check_files()) == 2


def test_two_bundles_that_name_each_other_both_load(fresh_registry: None,
                                                    tmp_path: Path) -> None:
    for name, code, other in (("left.py", "LEFT", "right.py"),
                              ("right.py", "RIGHT", "left.py")):
        (tmp_path / name).write_text(
            "import os\n"
            "from jobcheck import PASS, load_checks, register_check\n"
            f"@register_check({code!r}, 'from {name}')\n"
            "def check(row): return PASS\n"
            f"load_checks([{other!r}], base_dir=os.path.dirname(os.path.abspath(__file__)))\n"
        )
    reg.load_checks([str(tmp_path / "left.py")])
    assert sorted(t.code for t in reg.CHECKS) == ["LEFT", "RIGHT"]


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
        "from jobcheck import PASS, load_checks, register_check\n"
        "load_checks([os.path.join(os.path.dirname(os.path.abspath(__file__)),\n"
        "                          'inner', 'checks.py')])\n"
        "MARKER = 'the bundle'\n"
        "@register_check('OUTER', 'from the bundle itself')\n"
        "def own(row): return PASS\n"
        "assert sys.modules[__name__].MARKER == 'the bundle', sys.modules[__name__]\n"
    )

    reg.load_checks([str(bundle)])

    assert sorted(t.code for t in reg.CHECKS) == ["INNER", "OUTER"]
    names = [name for name in sys.modules if name.startswith("jobcheck_check_file_")]
    assert len(names) == 2, names


def test_a_file_interrupted_part_way_drops_its_checks_like_any_other_failure(
    fresh_registry: None, tmp_path: Path
) -> None:
    """Written against a defect: the rollback caught ``Exception``, so a
    ``KeyboardInterrupt`` during a slow import -- or a check file calling
    ``sys.exit()`` -- left its checks registered while the file stayed out of
    ``loaded_check_files()``, and the retry refused the author's own check as a
    duplicate of itself."""

    path = tmp_path / "check_interrupted.py"
    path.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('INTERRUPTED', 'registered before the interrupt')\n"
        "def rule(row): return PASS\n"
        "raise KeyboardInterrupt('ctrl-c during the import')\n"
    )

    with pytest.raises(KeyboardInterrupt):
        reg.load_checks([str(path)])

    assert reg.CHECKS == []
    assert reg.loaded_check_files() == []
    assert reg._LOADING == []

    # The author runs the same command again, uninterrupted this time.
    path.write_text(
        "from jobcheck import PASS, register_check\n"
        "@register_check('INTERRUPTED', 'registered before the interrupt')\n"
        "def rule(row): return PASS\n"
    )
    reg.load_checks([str(path)])
    assert [t.code for t in reg.CHECKS] == ["INTERRUPTED"]
