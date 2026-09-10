"""Unit tests: registration, suite loading, dependency validation, ordering."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from conftest import make_test
from pandas_row_validation import registry as reg

pytestmark = pytest.mark.fast


def test_register_test_captures_code_and_message(fresh_registry: None) -> None:
    make_test("A_CODE")
    test = reg.TESTS[0]
    assert (test.code, test.message) == ("A_CODE", "A_CODE failed")


def test_register_test_defaults_are_enabled_no_deps_no_description(fresh_registry: None) -> None:
    make_test("A_CODE")
    test = reg.TESTS[0]
    assert (test.default_enabled, test.depends_on, test.description) == (True, [], "")


def test_register_test_returns_the_undecorated_function(fresh_registry: None) -> None:
    @reg.register_test(code="RETURNED", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        return False

    assert check(pd.Series(dtype=object)) is False


def test_register_test_copies_depends_on_so_caller_list_cannot_mutate_it(fresh_registry: None) -> None:
    codes = ["FIRST"]
    make_test("FIRST")
    make_test("SECOND", depends_on=codes)
    codes.append("LATER")
    assert reg.TESTS[1].depends_on == ["FIRST"]


def test_duplicate_code_raises_naming_the_code(fresh_registry: None) -> None:
    make_test("SAME")
    with pytest.raises(ValueError, match=r"Duplicate test code 'SAME'"):
        make_test("SAME")


def test_source_file_points_at_the_defining_file(example_suites: None) -> None:
    test = next(t for t in reg.TESTS if t.code == "AGE_NEGATIVE")
    assert test.source_file.endswith("examples/example_suites/hard_tests/test_age.py")


def test_suite_comes_from_the_subpackage_directory(example_suites: None) -> None:
    suites = {t.code: t.suite for t in reg.TESTS}
    assert suites["AGE_NEGATIVE"] == "hard_tests"
    assert suites["EMAIL_MISSING_AT"] == "soft_tests"


def test_module_in_the_package_root_gets_the_base_suite(example_suites: None) -> None:
    assert next(t for t in reg.TESTS if t.code == "ROW_ALL_NULL").suite == reg.BASE_SUITE


def test_a_test_defined_by_exec_registers_under_the_base_suite(fresh_registry: None) -> None:
    """Regression: a function from exec() has __module__ set to None, and suite
    inference called .split() on it, so a notebook cell or a doc example crashed
    with AttributeError instead of registering."""

    namespace: dict[str, Any] = {}
    exec(
        "from pandas_row_validation import PASS, register_test\n"
        '@register_test("EXECED", "m")\n'
        "def check(row):\n"
        "    return PASS\n",
        namespace,
    )
    registered = reg.TESTS[0]
    assert (registered.code, registered.suite) == ("EXECED", reg.BASE_SUITE)
    assert registered.source_file == "<unknown>"
    assert reg.validate_row(pd.Series({"age": 1})) == []


def test_a_duplicate_code_from_exec_still_names_the_function(fresh_registry: None) -> None:
    namespace: dict[str, Any] = {}
    source = (
        "from pandas_row_validation import PASS, register_test\n"
        '@register_test("EXECED", "m")\n'
        "def check(row):\n"
        "    return PASS\n"
    )
    exec(source, namespace)
    with pytest.raises(ValueError, match=r"Duplicate test code 'EXECED' \(registering check\)"):
        exec(source, namespace)


def test_infer_suite_of_a_function_outside_any_package_is_base(fresh_registry: None) -> None:
    def check(row: "pd.Series[Any]") -> bool:
        return True

    assert reg._infer_suite(check) == "base"


def test_load_suites_registers_only_the_requested_suites_plus_base(fresh_registry: None) -> None:
    reg.load_suites(["hard_tests"], package="example_suites")
    assert sorted({t.suite for t in reg.TESTS}) == ["base", "hard_tests"]


def test_load_suites_registers_the_expected_codes(fresh_registry: None) -> None:
    reg.load_suites(["hard_tests", "soft_tests"], package="example_suites")
    assert sorted(t.code for t in reg.TESTS) == [
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
    import pandas_row_validation

    assert pandas_row_validation.TESTS == []


def test_loaded_suites_includes_base_and_is_a_copy(fresh_registry: None) -> None:
    reg.load_suites(["hard_tests"], package="example_suites")
    suites = reg.loaded_suites()
    assert suites == {"base", "hard_tests"}
    suites.add("mutated")
    assert reg.loaded_suites() == {"base", "hard_tests"}


def test_repeated_load_suites_does_not_register_twice(fresh_registry: None) -> None:
    reg.load_suites(["hard_tests"], package="example_suites")
    count = len(reg.TESTS)
    reg.load_suites(["hard_tests"], package="example_suites")
    reg.load_suites(["hard_tests", "hard_tests"], package="example_suites")
    assert len(reg.TESTS) == count


def test_overlapping_load_suites_adds_only_the_new_suite(fresh_registry: None) -> None:
    reg.load_suites(["hard_tests"], package="example_suites")
    reg.load_suites(["hard_tests", "soft_tests"], package="example_suites")
    assert reg.loaded_suites() == {"base", "hard_tests", "soft_tests"}
    assert sum(t.code == "AGE_NEGATIVE" for t in reg.TESTS) == 1


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
        reg.load_suites(["hard_tests"], package="no_such_package")
    message = str(excinfo.value)
    assert "Unknown package 'no_such_package'" in message
    assert "package= is the package your own tests live in" in message
    assert reg.TESTS == []


def test_unknown_suite_leaves_it_out_of_loaded_suites(fresh_registry: None) -> None:
    with pytest.raises(ValueError):
        reg.load_suites(["nope_tests"], package="example_suites")
    assert "nope_tests" not in reg.loaded_suites()


def test_load_suites_rejects_a_module_that_is_not_a_package(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="is a module, not a package"):
        reg._import_test_modules("example_suites.test_row_shape")


def test_load_suites_takes_a_package_argument(fresh_registry: None) -> None:
    reg.load_suites(["hard_tests"], package="example_suites")
    assert any(t.code == "AGE_NEGATIVE" for t in reg.TESTS)


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
    assert reg.TESTS == []


def test_clear_registry_empties_tests_and_suites(example_suites: None) -> None:
    reg.clear_registry()
    assert reg.TESTS == []
    assert reg.loaded_suites() == set()


def test_clear_registry_then_load_suites_re_registers(fresh_registry: None) -> None:
    """Regression: clearing left the modules in sys.modules, so the re-import was a
    no-op and the registry stayed silently empty."""

    reg.load_suites(["hard_tests"], package="example_suites")
    reg.clear_registry()
    reg.load_suites(["hard_tests"], package="example_suites")
    assert sorted(t.code for t in reg.TESTS) == [
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
    test module already imported directly (as a test file does) was never re-executed
    and its checks vanished from the registry after a clear."""

    import example_suites.hard_tests.test_age as test_age

    assert test_age.age_present is not None
    reg.clear_registry()
    reg.load_suites(["hard_tests"], package="example_suites")
    assert any(t.code == "AGE_NEGATIVE" for t in reg.TESTS)


def test_validate_registry_accepts_a_satisfied_dependency(fresh_registry: None) -> None:
    make_test("BASE_CHECK")
    make_test("DEPENDENT", depends_on=["BASE_CHECK"])
    reg.validate_registry()
    assert [t.code for t in reg._get_topo_order()] == ["BASE_CHECK", "DEPENDENT"]


def test_unregistered_prerequisite_raises_naming_both_codes(fresh_registry: None) -> None:
    make_test("DANGLING", depends_on=["NOT_A_REAL_CODE"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    message = str(excinfo.value)
    assert "Test 'DANGLING' depends on 'NOT_A_REAL_CODE', which is not registered." in message
    assert "currently loaded" in message


def test_prerequisite_in_an_unloaded_suite_raises_rather_than_skipping(fresh_registry: None) -> None:
    """soft_tests is not loaded, so EMAIL_MISSING_AT is unknown and must be loud."""

    reg.load_suites(["hard_tests"], package="example_suites")
    make_test("NEEDS_EMAIL", depends_on=["EMAIL_MISSING_AT"])
    with pytest.raises(ValueError, match="EMAIL_MISSING_AT"):
        reg.validate_registry()


def test_direct_cycle_raises_naming_the_path(fresh_registry: None) -> None:
    make_test("CYCLE_A", depends_on=["CYCLE_B"])
    make_test("CYCLE_B", depends_on=["CYCLE_A"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    assert str(excinfo.value) == "Dependency cycle among tests: CYCLE_A -> CYCLE_B -> CYCLE_A"


def test_transitive_cycle_raises_naming_the_whole_chain(fresh_registry: None) -> None:
    make_test("C_A", depends_on=["C_B"])
    make_test("C_B", depends_on=["C_C"])
    make_test("C_C", depends_on=["C_A"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    assert str(excinfo.value) == "Dependency cycle among tests: C_A -> C_B -> C_C -> C_A"


def test_self_dependency_is_reported_as_a_cycle(fresh_registry: None) -> None:
    make_test("SELF", depends_on=["SELF"])
    with pytest.raises(ValueError) as excinfo:
        reg.validate_registry()
    assert str(excinfo.value) == "Dependency cycle among tests: SELF -> SELF"


def test_topological_order_puts_a_diamond_in_dependency_order(fresh_registry: None) -> None:
    make_test("D_TOP", depends_on=["D_LEFT", "D_RIGHT"])
    make_test("D_LEFT", depends_on=["D_ROOT"])
    make_test("D_RIGHT", depends_on=["D_ROOT"])
    make_test("D_ROOT")
    order = [t.code for t in reg._get_topo_order()]
    assert order.index("D_ROOT") < order.index("D_LEFT") < order.index("D_TOP")
    assert order.index("D_RIGHT") < order.index("D_TOP")


def test_registering_a_test_invalidates_the_cached_order(fresh_registry: None) -> None:
    make_test("FIRST")
    assert len(reg._get_topo_order()) == 1
    make_test("SECOND")
    assert reg._TOPO_ORDER is None
    assert len(reg._get_topo_order()) == 2


def test_get_topo_order_recomputes_after_the_cache_is_dropped(fresh_registry: None) -> None:
    make_test("ONLY")
    reg._TOPO_ORDER = None
    assert [t.code for t in reg._get_topo_order()] == ["ONLY"]
