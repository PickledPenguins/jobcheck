"""Unit checks: registration, file loading, dependency validation, ordering."""

from __future__ import annotations

import functools
import re
import sys
from typing import Any

import pandas as pd
import pytest

from conftest import EXAMPLE_CHECK_FILES, failures, make_check
from registry_state import SavedRegistry
from jobcheck import registry as reg
from jobcheck import engine
from jobcheck.results import Verdict, OK, Status

pytestmark = pytest.mark.fast


def test_register_check_captures_code_and_message(fresh_registry: None) -> None:
    make_check("A_CODE")
    check = reg._CHECKS[0]
    assert (check.code, check.message) == ("A_CODE", "A_CODE failed")


def test_register_check_defaults_are_enabled_with_no_dependencies(fresh_registry: None) -> None:
    make_check("A_CODE")
    check = reg._CHECKS[0]
    assert (check.default_enabled, check.depends_on) == (True, [])


def test_register_check_returns_the_undecorated_function(fresh_registry: None) -> None:
    @reg.register_check(code="RETURNED", message="m")
    def check(row: "pd.Series[Any]") -> Verdict:
        return Verdict(Status.INVALID)

    assert bool(check(pd.Series(dtype=object))) is False


def test_register_check_copies_depends_on_so_caller_list_cannot_mutate_it(fresh_registry: None) -> None:
    codes = ["FIRST"]
    make_check("FIRST")
    make_check("SECOND", depends_on=codes)
    codes.append("LATER")
    assert reg._CHECKS[1].depends_on == ["FIRST"]


def test_duplicate_code_raises_naming_the_code(fresh_registry: None) -> None:
    make_check("SAME")
    with pytest.raises(ValueError, match=r"Duplicate check code 'SAME'"):
        make_check("SAME")


def test_source_file_points_at_the_defining_file(example_checks: None) -> None:
    check = next(t for t in reg._CHECKS if t.code == "AGE_NEGATIVE")
    assert check.source_file.endswith("examples/checks/check_age.py")


def test_a_partial_registers_and_is_named_by_its_own_kind(fresh_registry: None) -> None:
    """Regression: `fn.__name__` was reached for before any of the library's own
    messages, so a functools.partial -- the obvious way to write a parameterized
    check factory -- died with a bare AttributeError naming nothing."""

    def above(limit: int, row: "pd.Series[Any]") -> Verdict:
        return Verdict(Status.INVALID) if row["age"] > limit else OK

    reg.register_check(code="AGE_ABOVE", message="m")(functools.partial(above, 130))
    registered = reg._CHECKS[0]
    assert registered.code == "AGE_ABOVE"
    assert registered.source_file == "<unknown>"
    assert failures(pd.Series({"age": 200}))[0].code == "AGE_ABOVE"


def test_the_two_fixes_for_a_defaulted_second_parameter_both_register(
    fresh_registry: None,
) -> None:
    """The refusal names two ways to write `age_below(row, limit=130)`, and a
    default of None on the context stays allowed: each one registers and runs."""

    def below(row: "pd.Series[Any]", limit: int) -> Verdict:
        return OK if row["age"] <= limit else Verdict(Status.INVALID)

    def below_keyword(row: "pd.Series[Any]", *, limit: int = 130) -> Verdict:
        return OK if row["age"] <= limit else Verdict(Status.INVALID)

    def reads_context(row: "pd.Series[Any]", context: Any = None) -> Verdict:
        return OK if context is not None else Verdict(Status.INVALID)

    reg.register_check(code="PARTIAL", message="m")(functools.partial(below, limit=130))
    reg.register_check(code="KEYWORD", message="m")(below_keyword)
    reg.register_check(code="CONTEXT", message="m")(reads_context)
    failed = [outcome.code for outcome in failures(pd.Series({"age": 200}))]
    assert failed == ["PARTIAL", "KEYWORD"]


def test_clearing_leaves_every_module_a_check_came_from_imported(fresh_registry: None) -> None:
    """Only the check-file modules `load_checks` made are dropped. Evicting the
    module of a partial, a callable object or an imported function would leave
    earlier importers holding a second copy of it."""

    import operator

    def above(limit: int, row: "pd.Series[Any]") -> Verdict:
        return OK

    reg.register_check(code="AGE_ABOVE", message="m")(functools.partial(above, 130))
    reg.register_check(code="CALLS", message="m")(operator.methodcaller("get", "age"))
    reg.register_check(code="TRUTHY", message="m")(operator.truth)
    reg.clear_registry()
    assert sys.modules.get("functools") is functools
    assert sys.modules.get("operator") is operator
    assert sys.modules.get(__name__) is not None


def test_a_callable_object_of_the_wrong_shape_is_refused_with_a_message(
    fresh_registry: None,
) -> None:
    """The same name lookup, on the path that rejects: the message has to name
    something, and a callable object has no __name__ either."""

    class TooManyArguments:
        def __call__(self, row: Any, context: Any, extra: Any) -> Verdict:
            return OK

    with pytest.raises(ValueError) as raised:
        reg.register_check(code="OBJ", message="m")(TooManyArguments())
    assert str(raised.value) == (
        "Check 'OBJ': TooManyArguments(row: 'Any', context: 'Any', extra: 'Any') "
        "-> 'Verdict' must take (row) or (row, context), not 3 positional argument(s)."
    )


def test_a_check_defined_by_exec_registers(fresh_registry: None) -> None:
    """Regression: a function from exec() has __module__ set to None, which the
    registration path must not assume is a string."""

    namespace: dict[str, Any] = {}
    exec(
        "from jobcheck import OK, register_check\n"
        '@register_check("EXECED", "m")\n'
        "def check(row):\n"
        "    return OK\n",
        namespace,
    )
    registered = reg._CHECKS[0]
    assert registered.code == "EXECED"
    assert registered.source_file == "<unknown>"
    assert failures(pd.Series({"age": 1})) == []


def test_a_duplicate_code_from_exec_still_names_the_function(fresh_registry: None) -> None:
    namespace: dict[str, Any] = {}
    source = (
        "from jobcheck import OK, register_check\n"
        '@register_check("EXECED", "m")\n'
        "def check(row):\n"
        "    return OK\n"
    )
    exec(source, namespace)
    with pytest.raises(ValueError, match=r"Duplicate check code 'EXECED' \(registering check\)"):
        exec(source, namespace)


def test_importing_the_package_alone_registers_nothing(fresh_registry: None) -> None:
    """Asserted through the public read path rather than the registry list, which
    is internal: `registry_table` is what a caller has."""

    import jobcheck

    assert jobcheck.registry_table().empty
    assert jobcheck.registry._LOADED_FILES == []


def test_clear_registry_empties_the_checks_and_the_loaded_files(example_checks: None) -> None:
    reg.clear_registry()
    assert reg._CHECKS == []
    assert reg._LOADED_FILES == []





def test_clear_registry_then_load_checks_re_registers(fresh_registry: None) -> None:
    """Regression: clearing left the modules in sys.modules, so the re-import was a
    no-op and the registry stayed silently empty."""

    reg.load_checks(EXAMPLE_CHECK_FILES)
    reg.clear_registry()
    reg.load_checks(EXAMPLE_CHECK_FILES)
    assert sorted(t.code for t in reg._CHECKS) == [
        "AGE_NEGATIVE",
        "AGE_NOT_A_NUMBER",
        "AGE_NOT_INTEGER",
        "AGE_PRESENT",
        "AGE_TOO_HIGH",
        "DATES_OUT_OF_ORDER",
        "DATES_PRESENT",
        "EMAIL_DOMAIN_INVALID",
        "EMAIL_MISSING_AT",
        "EMAIL_PRESENT",
        "ROW_ALL_NULL",
    ]


def test_validate_registry_accepts_a_satisfied_dependency(fresh_registry: None) -> None:
    make_check("BASE_CHECK")
    make_check("DEPENDENT", depends_on=["BASE_CHECK"])
    reg._validate_registry()
    assert [t.code for t in reg._get_topo_order()] == ["BASE_CHECK", "DEPENDENT"]


def test_unregistered_prerequisite_raises_naming_both_codes(fresh_registry: None) -> None:
    make_check("DANGLING", depends_on=["NOT_A_REAL_CODE"])
    with pytest.raises(ValueError) as excinfo:
        reg._validate_registry()
    message = str(excinfo.value)
    assert "Check 'DANGLING' depends on 'NOT_A_REAL_CODE', which is not registered." in message
    assert "currently loaded" in message


def test_prerequisite_in_an_unloaded_file_raises_rather_than_skipping(fresh_registry: None) -> None:
    """check_email.py is not loaded, so EMAIL_MISSING_AT is unknown and must be loud."""

    reg.load_checks([path for path in EXAMPLE_CHECK_FILES if "email" not in path])
    make_check("NEEDS_EMAIL", depends_on=["EMAIL_MISSING_AT"])
    with pytest.raises(ValueError, match="EMAIL_MISSING_AT"):
        reg._validate_registry()


def test_direct_cycle_raises_naming_the_path(fresh_registry: None) -> None:
    make_check("CYCLE_A", depends_on=["CYCLE_B"])
    make_check("CYCLE_B", depends_on=["CYCLE_A"])
    with pytest.raises(ValueError) as excinfo:
        reg._validate_registry()
    assert str(excinfo.value) == "Dependency cycle among checks: CYCLE_A -> CYCLE_B -> CYCLE_A"


def test_transitive_cycle_raises_naming_the_whole_chain(fresh_registry: None) -> None:
    make_check("C_A", depends_on=["C_B"])
    make_check("C_B", depends_on=["C_C"])
    make_check("C_C", depends_on=["C_A"])
    with pytest.raises(ValueError) as excinfo:
        reg._validate_registry()
    assert str(excinfo.value) == "Dependency cycle among checks: C_A -> C_B -> C_C -> C_A"


def test_self_dependency_is_reported_as_a_cycle(fresh_registry: None) -> None:
    make_check("SELF", depends_on=["SELF"])
    with pytest.raises(ValueError) as excinfo:
        reg._validate_registry()
    assert str(excinfo.value) == "Dependency cycle among checks: SELF -> SELF"


def test_a_chain_too_deep_to_walk_names_the_registry_rather_than_the_recursion(
    fresh_registry: None,
) -> None:
    """The ordering walk is recursive, so a chain registered dependent-first is
    walked to its full depth. A bare RecursionError out of `visit` names neither
    the registry nor the chain."""

    depth = 2000
    for index in range(depth):
        make_check(f"DEEP_{index}",
                   depends_on=[f"DEEP_{index + 1}"] if index + 1 < depth else [])
    with pytest.raises(ValueError) as excinfo:
        reg._validate_registry()
    assert str(excinfo.value) == (
        f"Dependency chain too deep to resolve among {depth} checks: the ordering walk "
        f"is recursive and gives out near Python's recursion limit of "
        f"{sys.getrecursionlimit()} (widest declared depends_on: 1). Shorten the chain, "
        "or register prerequisites before the checks that depend on them."
    )


def test_topological_order_puts_a_diamond_in_dependency_order(fresh_registry: None) -> None:
    make_check("D_TOP", depends_on=["D_LEFT", "D_RIGHT"])
    make_check("D_LEFT", depends_on=["D_ROOT"])
    make_check("D_RIGHT", depends_on=["D_ROOT"])
    make_check("D_ROOT")
    order = [t.code for t in reg._get_topo_order()]
    assert order.index("D_ROOT") < order.index("D_LEFT") < order.index("D_TOP")
    assert order.index("D_RIGHT") < order.index("D_TOP")


def test_registering_a_check_invalidates_the_cached_order(fresh_registry: None) -> None:
    make_check("FIRST")
    assert len(reg._get_topo_order()) == 1
    make_check("SECOND")
    assert reg._TOPO_ORDER is None
    assert len(reg._get_topo_order()) == 2


def test_get_topo_order_recomputes_after_the_cache_is_dropped(fresh_registry: None) -> None:
    make_check("ONLY")
    reg._TOPO_ORDER = None
    assert [t.code for t in reg._get_topo_order()] == ["ONLY"]


# --- what mutation testing found the suite was not pinning ------------------


def test_a_duplicate_code_names_the_module_the_second_check_lives_in(
    fresh_registry: None, tmp_path: Any
) -> None:
    """The message says which *module* redefined the code, not just which function.

    A code is usually duplicated across two files, so the function name alone
    sends the reader to the wrong one. Mutation found nothing asserting the
    module half: only the exec() case, where there is no module to name.
    """

    make_check("SHARED")
    path = tmp_path / "second.py"
    path.write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('SHARED', 'again')\n"
        "def rule(row): return OK\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        reg.load_checks([str(path)])
    assert re.search(r"\(registering jobcheck_check_file_second_\d+\.rule\)", str(excinfo.value))


def test_an_empty_string_prerequisite_is_refused(fresh_registry: None) -> None:
    """`depends_on=[""]` is a typo, not a check with no name, and it would
    otherwise reach _validate_registry as a prerequisite nothing can satisfy."""

    with pytest.raises(ValueError, match="depends_on must be a list of check codes"):
        reg.register_check(code="CODE", message="m", depends_on=[""])(lambda row: True)


def test_two_required_keyword_arguments_are_both_named(fresh_registry: None) -> None:
    """The message lists them comma-separated; with one argument a broken
    separator is invisible."""

    with pytest.raises(ValueError) as excinfo:
        @reg.register_check(code="CODE", message="m")
        def check(row, *, low, high):  # type: ignore[no-untyped-def]
            return OK
    assert "needs keyword argument(s) low, high that the engine cannot supply" in str(excinfo.value)


def _check_file(path: Any, code: str) -> str:
    """A one-check file, for the tests that care which module it loads as."""

    path.write_text(
        "from jobcheck import OK, register_check\n"
        f"@register_check({code!r}, 'm')\n"
        "def rule(row): return OK\n",
        encoding="utf-8",
    )
    return str(path)


def test_saving_the_registry_copies_every_global_clear_registry_clears(
    fresh_registry: None,
) -> None:
    """The suite's own isolation depends on it: a registry global added to the
    module and not to SavedRegistry is state every test silently loses. That is
    what happened to the load sequence."""

    saved = set(SavedRegistry.__slots__)
    cleared = {"checks", "loaded_files", "topo_order"}
    assert saved == cleared


def test_saving_the_registry_leaves_out_the_in_progress_load_stack() -> None:
    """Deliberate, not an oversight: the stack belongs to the `load_checks`
    call that is running, and a frame put back from a finished load would take
    the blame for the next file's checks."""

    assert not any("loading" in name for name in SavedRegistry.__slots__)


def test_the_load_sequence_survives_a_clear(fresh_registry: None, tmp_path: Any) -> None:
    """A module name is numbered by the load sequence, which never goes back:
    a number reused after a clear would name a second module like the first."""

    reg.load_checks([_check_file(tmp_path / "first.py", "FIRST")])
    first = reg._LOAD_SEQUENCE
    reg.clear_registry()
    reg.load_checks([_check_file(tmp_path / "first.py", "FIRST")])
    assert f"jobcheck_check_file_first_{first}" in sys.modules


def test_putting_the_registry_back_restores_checks_that_still_run(
    fresh_registry: None, tmp_path: Any
) -> None:
    """The nesting case the suite relies on: an inner scope loads a file and
    hands back exactly what it found, checks included, runnable."""

    reg.load_checks([_check_file(tmp_path / "outer.py", "OUTER")])
    saved = SavedRegistry()
    reg.load_checks([_check_file(tmp_path / "inner.py", "INNER")])
    assert sorted(c.code for c in reg._CHECKS) == ["INNER", "OUTER"]

    saved.restore()
    assert [c.code for c in reg._CHECKS] == ["OUTER"]
    outcomes = engine._explain(pd.Series({"a": 1}))
    assert [o.code for o in outcomes] == ["OUTER"]


def test_the_registry_list_is_not_part_of_the_public_surface() -> None:
    """It was exported until 2026-09-24, with `interfaces.md` asking callers not to
    mutate it and nothing enforcing that. Nothing outside this package ever read it:
    the read path is `registry_table`, which every legitimate use wanted."""

    import jobcheck

    assert "_CHECKS" not in jobcheck.__all__
    assert not hasattr(jobcheck, "CHECKS")
    assert set(jobcheck.registry_table().columns) >= {
        "code", "layer", "default", "message", "depends_on"}
