"""Unit checks: registration, suite loading, dependency validation, ordering."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from conftest import make_check
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


def test_source_file_points_at_the_defining_file(example_suites: None) -> None:
    check = next(t for t in reg.CHECKS if t.code == "AGE_NEGATIVE")
    assert check.source_file.endswith("examples/example_suites/hard_checks/check_age.py")


def test_suite_comes_from_the_subpackage_directory(example_suites: None) -> None:
    suites = {t.code: t.suite for t in reg.CHECKS}
    assert suites["AGE_NEGATIVE"] == "hard_checks"
    assert suites["EMAIL_MISSING_AT"] == "soft_checks"


def test_module_in_the_package_root_gets_the_base_suite(example_suites: None) -> None:
    assert next(t for t in reg.CHECKS if t.code == "ROW_ALL_NULL").suite == reg.BASE_SUITE


def test_a_test_defined_by_exec_registers_under_the_base_suite(fresh_registry: None) -> None:
    """Regression: a function from exec() has __module__ set to None, and suite
    inference called .split() on it, so a notebook cell or a doc example crashed
    with AttributeError instead of registering."""

    namespace: dict[str, Any] = {}
    exec(
        "from jobcheck import PASS, register_check\n"
        '@register_check("EXECED", "m")\n'
        "def check(row):\n"
        "    return PASS\n",
        namespace,
    )
    registered = reg.CHECKS[0]
    assert (registered.code, registered.suite) == ("EXECED", reg.BASE_SUITE)
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


def test_infer_suite_of_a_function_outside_any_package_is_base(fresh_registry: None) -> None:
    def check(row: "pd.Series[Any]") -> bool:
        return True

    assert reg._infer_suite(check) == "base"


def test_load_suites_registers_only_the_requested_suites_plus_base(fresh_registry: None) -> None:
    reg.load_suites(["hard_checks"], package="example_suites")
    assert sorted({t.suite for t in reg.CHECKS}) == ["base", "hard_checks"]


def test_load_suites_registers_the_expected_codes(fresh_registry: None) -> None:
    reg.load_suites(["hard_checks", "soft_checks"], package="example_suites")
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


def test_importing_the_package_alone_registers_nothing(fresh_registry: None) -> None:
    import jobcheck

    assert jobcheck.CHECKS == []


def test_loaded_suites_includes_base_and_is_a_copy(fresh_registry: None) -> None:
    reg.load_suites(["hard_checks"], package="example_suites")
    suites = reg.loaded_suites()
    assert suites == {"base", "hard_checks"}
    suites.add("mutated")
    assert reg.loaded_suites() == {"base", "hard_checks"}


def test_repeated_load_suites_does_not_register_twice(fresh_registry: None) -> None:
    reg.load_suites(["hard_checks"], package="example_suites")
    count = len(reg.CHECKS)
    reg.load_suites(["hard_checks"], package="example_suites")
    reg.load_suites(["hard_checks", "hard_checks"], package="example_suites")
    assert len(reg.CHECKS) == count


def test_overlapping_load_suites_adds_only_the_new_suite(fresh_registry: None) -> None:
    reg.load_suites(["hard_checks"], package="example_suites")
    reg.load_suites(["hard_checks", "soft_checks"], package="example_suites")
    assert reg.loaded_suites() == {"base", "hard_checks", "soft_checks"}
    assert sum(t.code == "AGE_NEGATIVE" for t in reg.CHECKS) == 1


def test_unknown_suite_names_the_expected_subpackage(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as excinfo:
        reg.load_suites(["nope_tests"], package="example_suites")
    message = str(excinfo.value)
    assert "Unknown suite 'nope_tests'" in message
    assert "'example_suites.nope_tests'" in message
    assert "example_suites/nope_tests/" in message


def test_an_unimportable_package_says_so_rather_than_naming_a_suite(
    fresh_registry: None,
) -> None:
    """A typo in package= is a different mistake from a typo in a suite name, and
    the message has to say which one happened."""

    with pytest.raises(ValueError) as excinfo:
        reg.load_suites(["hard_checks"], package="no_such_package")
    message = str(excinfo.value)
    assert "Unknown package 'no_such_package'" in message
    assert "package= is the package your own checks live in" in message
    assert reg.CHECKS == []


def test_unknown_suite_leaves_it_out_of_loaded_suites(fresh_registry: None) -> None:
    with pytest.raises(ValueError):
        reg.load_suites(["nope_tests"], package="example_suites")
    assert "nope_tests" not in reg.loaded_suites()


def test_load_suites_rejects_a_module_that_is_not_a_package(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="is a module, not a package"):
        reg._import_test_modules("example_suites.check_row_shape")


def test_load_suites_takes_a_package_argument(fresh_registry: None) -> None:
    reg.load_suites(["hard_checks"], package="example_suites")
    assert any(t.code == "AGE_NEGATIVE" for t in reg.CHECKS)


def test_files_named_tests_plural_are_not_collected(fresh_registry: None, tmp_path: Any) -> None:
    package = tmp_path / "plural_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tests_ignored.py").write_text(
        "raise AssertionError('tests_*.py must not be imported')", encoding="utf-8"
    )
    import sys

    sys.path.insert(0, str(tmp_path))
    try:
        reg._import_test_modules("plural_pkg")
    finally:
        sys.path.remove(str(tmp_path))
    assert reg.CHECKS == []


def test_clear_registry_empties_tests_and_suites(example_suites: None) -> None:
    reg.clear_registry()
    assert reg.CHECKS == []
    assert reg.loaded_suites() == set()


def test_clear_registry_then_load_suites_re_registers(fresh_registry: None) -> None:
    """Regression: clearing left the modules in sys.modules, so the re-import was a
    no-op and the registry stayed silently empty."""

    reg.load_suites(["hard_checks"], package="example_suites")
    reg.clear_registry()
    reg.load_suites(["hard_checks"], package="example_suites")
    assert sorted(t.code for t in reg.CHECKS) == [
        "AGE_NEGATIVE",
        "AGE_NOT_A_NUMBER",
        "AGE_NOT_INTEGER",
        "AGE_PRESENT",
        "AGE_TOO_HIGH",
        "DATES_OUT_OF_ORDER",
        "DATES_PRESENT",
        "ROW_ALL_NULL",
    ]


def test_clear_registry_re_registers_a_module_imported_by_another_route(
    fresh_registry: None,
) -> None:
    """Regression: eviction tracked only modules imported by the suite loader, so a
    check module already imported directly (as a check file does) was never re-executed
    and its checks vanished from the registry after a clear."""

    import example_suites.hard_checks.check_age as check_age

    assert check_age.age_present is not None
    reg.clear_registry()
    reg.load_suites(["hard_checks"], package="example_suites")
    assert any(t.code == "AGE_NEGATIVE" for t in reg.CHECKS)


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


def test_prerequisite_in_an_unloaded_suite_raises_rather_than_skipping(fresh_registry: None) -> None:
    """soft_checks is not loaded, so EMAIL_MISSING_AT is unknown and must be loud."""

    reg.load_suites(["hard_checks"], package="example_suites")
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
