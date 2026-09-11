"""Unit checks: registration, file loading, dependency validation, ordering."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from conftest import EXAMPLE_CHECK_FILES, make_check
from jobcheck import registry as reg
from jobcheck import engine

pytestmark = pytest.mark.fast


def test_register_test_captures_code_and_message(fresh_registry: None) -> None:
    make_check("A_CODE")
    check = reg.CHECKS[0]
    assert (check.code, check.message) == ("A_CODE", "A_CODE failed")


def test_register_test_defaults_are_enabled_no_deps_no_description(fresh_registry: None) -> None:
    make_check("A_CODE")
    check = reg.CHECKS[0]
    assert (check.default_enabled, check.depends_on, check.description) == (True, [], "")


def test_register_test_returns_the_undecorated_function(fresh_registry: None) -> None:
    @reg.register_check(code="RETURNED", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        return False

    assert check(pd.Series(dtype=object)) is False


def test_register_test_copies_depends_on_so_caller_list_cannot_mutate_it(fresh_registry: None) -> None:
    codes = ["FIRST"]
    make_check("FIRST")
    make_check("SECOND", depends_on=codes)
    codes.append("LATER")
    assert reg.CHECKS[1].depends_on == ["FIRST"]


def test_duplicate_code_raises_naming_the_code(fresh_registry: None) -> None:
    make_check("SAME")
    with pytest.raises(ValueError, match=r"Duplicate check code 'SAME'"):
        make_check("SAME")


def test_source_file_points_at_the_defining_file(example_checks: None) -> None:
    check = next(t for t in reg.CHECKS if t.code == "AGE_NEGATIVE")
    assert check.source_file.endswith("examples/checks/check_age.py")


def test_a_check_defined_by_exec_registers(fresh_registry: None) -> None:
    """Regression: a function from exec() has __module__ set to None, which the
    registration path must not assume is a string."""

    namespace: dict[str, Any] = {}
    exec(
        "from jobcheck import PASS, register_check\n"
        '@register_check("EXECED", "m")\n'
        "def check(row):\n"
        "    return PASS\n",
        namespace,
    )
    registered = reg.CHECKS[0]
    assert registered.code == "EXECED"
    assert registered.source_file == "<unknown>"
    assert engine.validate_row(pd.Series({"age": 1})) == []


def test_a_duplicate_code_from_exec_still_names_the_function(fresh_registry: None) -> None:
    namespace: dict[str, Any] = {}
    source = (
        "from jobcheck import PASS, register_check\n"
        '@register_check("EXECED", "m")\n'
        "def check(row):\n"
        "    return PASS\n"
    )
    exec(source, namespace)
    with pytest.raises(ValueError, match=r"Duplicate check code 'EXECED' \(registering check\)"):
        exec(source, namespace)


def test_importing_the_package_alone_registers_nothing(fresh_registry: None) -> None:
    import jobcheck

    assert jobcheck.CHECKS == []


def test_clear_registry_empties_the_checks_and_the_loaded_files(example_checks: None) -> None:
    reg.clear_registry()
    assert reg.CHECKS == []
    assert reg.loaded_files() == []


def test_clear_registry_then_load_checks_re_registers(fresh_registry: None) -> None:
    """Regression: clearing left the modules in sys.modules, so the re-import was a
    no-op and the registry stayed silently empty."""

    reg.load_checks(EXAMPLE_CHECK_FILES)
    reg.clear_registry()
    reg.load_checks(EXAMPLE_CHECK_FILES)
    assert sorted(t.code for t in reg.CHECKS) == [
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
    reg.validate_registry()
    assert [t.code for t in reg._get_topo_order()] == ["BASE_CHECK", "DEPENDENT"]


def test_unregistered_prerequisite_raises_naming_both_codes(fresh_registry: None) -> None:
    make_check("DANGLING", depends_on=["NOT_A_REAL_CODE"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    message = str(excinfo.value)
    assert "Check 'DANGLING' depends on 'NOT_A_REAL_CODE', which is not registered." in message
    assert "currently loaded" in message


def test_prerequisite_in_an_unloaded_file_raises_rather_than_skipping(fresh_registry: None) -> None:
    """check_email.py is not loaded, so EMAIL_MISSING_AT is unknown and must be loud."""

    reg.load_checks([path for path in EXAMPLE_CHECK_FILES if "email" not in path])
    make_check("NEEDS_EMAIL", depends_on=["EMAIL_MISSING_AT"])
    with pytest.raises(ValueError, match="EMAIL_MISSING_AT"):
        reg.validate_registry()


def test_direct_cycle_raises_naming_the_path(fresh_registry: None) -> None:
    make_check("CYCLE_A", depends_on=["CYCLE_B"])
    make_check("CYCLE_B", depends_on=["CYCLE_A"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    assert str(excinfo.value) == "Dependency cycle among checks: CYCLE_A -> CYCLE_B -> CYCLE_A"


def test_transitive_cycle_raises_naming_the_whole_chain(fresh_registry: None) -> None:
    make_check("C_A", depends_on=["C_B"])
    make_check("C_B", depends_on=["C_C"])
    make_check("C_C", depends_on=["C_A"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    assert str(excinfo.value) == "Dependency cycle among checks: C_A -> C_B -> C_C -> C_A"


def test_self_dependency_is_reported_as_a_cycle(fresh_registry: None) -> None:
    make_check("SELF", depends_on=["SELF"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    assert str(excinfo.value) == "Dependency cycle among checks: SELF -> SELF"


def test_topological_order_puts_a_diamond_in_dependency_order(fresh_registry: None) -> None:
    make_check("D_TOP", depends_on=["D_LEFT", "D_RIGHT"])
    make_check("D_LEFT", depends_on=["D_ROOT"])
    make_check("D_RIGHT", depends_on=["D_ROOT"])
    make_check("D_ROOT")
    order = [t.code for t in reg._get_topo_order()]
    assert order.index("D_ROOT") < order.index("D_LEFT") < order.index("D_TOP")
    assert order.index("D_RIGHT") < order.index("D_TOP")


def test_registering_a_test_invalidates_the_cached_order(fresh_registry: None) -> None:
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
        "from jobcheck import PASS, register_check\n"
        "@register_check('SHARED', 'again')\n"
        "def rule(row): return PASS\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        reg.load_checks([str(path)])
    assert "(registering jobcheck_check_file_second_0.rule)" in str(excinfo.value)


def test_an_empty_string_prerequisite_is_refused(fresh_registry: None) -> None:
    """`depends_on=[""]` is a typo, not a check with no name, and it would
    otherwise reach validate_registry as a prerequisite nothing can satisfy."""

    with pytest.raises(ValueError, match="depends_on must be a list of check codes"):
        reg.register_check(code="CODE", message="m", depends_on=[""])(lambda row: True)


def test_the_description_reaches_the_registered_check(fresh_registry: None) -> None:
    """It is the column a reader scans in the registry table, and nothing else
    asserted that it survives registration."""

    @reg.register_check(code="DESCRIBED", message="m", description="why this exists")
    def described(row: Any) -> bool:
        return True

    assert reg.CHECKS[0].description == "why this exists"


def test_two_required_keyword_arguments_are_both_named(fresh_registry: None) -> None:
    """The message lists them comma-separated; with one argument a broken
    separator is invisible."""

    with pytest.raises(ValueError) as excinfo:
        @reg.register_check(code="CODE", message="m")
        def check(row, *, low, high):  # type: ignore[no-untyped-def]
            return True
    assert "needs keyword argument(s) low, high that the engine cannot supply" in str(excinfo.value)
