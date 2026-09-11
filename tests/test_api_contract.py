"""Interface checks: the public surface other code depends on.

These are the checks that fail when an export is forgotten, a default changes, or
a permanent identifier moves -- the kind of break that is invisible until someone
else's import fails.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

import pytest

import jobcheck as validation
from jobcheck import registry as reg
from jobcheck import engine
from jobcheck import registry_tables
from jobcheck import report as rep
from jobcheck import results as res
from jobcheck import rules, tables
from jobcheck.results import PASS, Status

pytestmark = pytest.mark.fast

MODULES = [res, reg, rep, tables, validation.context]
# rules is a module the package deliberately does not re-export wholesale: the
# registry wraps its loaders, and its parser entry points are for that wrapper.
INTERNAL_MODULES = [rules]


def test_every_exported_name_exists() -> None:
    missing = [name for name in validation.__all__ if not hasattr(validation, name)]
    assert missing == []


def test_all_is_sorted_and_free_of_duplicates() -> None:
    names = [name for name in validation.__all__ if not name.startswith("__")]
    assert names == sorted(names)
    assert len(validation.__all__) == len(set(validation.__all__))


def test_every_tool_the_suite_relies_on_is_declared() -> None:
    """Regression: hypothesis sat in an optional extra CI never installed, so
    tests/test_properties.py skipped everywhere but one machine and the summary
    line still read green. A tool the suite imports has to be a declared
    dependency, or its absence is invisible."""

    pyproject = (Path(validation.__file__).parent.parent.parent / "pyproject.toml")
    declared = pyproject.read_text(encoding="utf-8")
    for tool in ("pytest", "coverage", "mypy", "types-PyYAML", "hypothesis", "mutmut"):
        assert f'"{tool}' in declared, f"{tool} is used by the suite but not declared"


def test_the_package_states_a_version() -> None:
    """Anyone depending on this needs to be able to say which behavior they have."""

    assert re.fullmatch(r"\d+\.\d+\.\d+", validation.__version__)
    assert "__version__" in validation.__all__


def test_the_rule_parser_does_not_import_the_registry() -> None:
    """The seam that keeps rules.py a file about a file format: the registry hands
    it the codes that exist, and it never reaches back."""

    code = [
        line for line in Path(rules.__file__).read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    imports = [line for line in code if line.startswith(("import ", "from "))]
    assert not any("registry" in line for line in imports), imports
    assert not any("CHECKS" in line for line in code)


def test_every_public_function_is_exported() -> None:
    """Regression: root_cause_counts was documented but never re-exported, so
    importing it from the package raised."""

    exported = set(validation.__all__)
    unexported: list[str] = []
    for module in MODULES:
        for name, value in vars(module).items():
            if name.startswith("_") or name in exported:
                continue
            if not callable(value) or inspect.getmodule(value) is not module:
                continue
            if isinstance(value, type) and not name[0].isupper():
                continue
            unexported.append(f"{module.__name__}.{name}")
    assert unexported == []


def test_status_values_are_permanent() -> None:
    """Reports and saved data refer to these numbers; they never move."""

    assert {member.name: int(member) for member in res.Status} == {
        "PASS": 0, "MISSING": 1, "MALFORMED": 2, "INVALID": 3, "ERROR": 9
    }


def test_outcome_names_are_permanent() -> None:
    assert (res.PASSED, res.FAILED, res.DISABLED, res.SKIPPED, res.ERRORED) == (
        "passed", "failed", "disabled", "skipped", "errored"
    )


def test_report_columns_are_stable() -> None:
    """Anything reading the CSV depends on these names and this order."""

    assert rep.REPORT_COLUMNS == [
        "row", "code", "status", "layer", "outcome", "message", "detail", "comments",
        "is_root_cause"
    ]


def test_registry_table_columns_are_stable(example_checks: None) -> None:
    assert list(registry_tables.get_registry_table().columns) == [
        "code", "layer", "default", "message", "depends_on"
    ]


def defaults(fn: Any) -> dict[str, Any]:
    return {
        name: parameter.default
        for name, parameter in inspect.signature(fn).parameters.items()
        if parameter.default is not inspect.Parameter.empty
    }


@pytest.mark.parametrize(
    "fn, expected",
    [
        pytest.param(reg.register_check,
                     {"default_enabled": True, "depends_on": None},
                     id="register_check"),
        pytest.param(reg.load_checks, {}, id="load_checks"),
        pytest.param(engine.explain_row,
                     {"context": None, "overrides": None, "on_error": "record"},
                     id="explain_row"),
        pytest.param(engine.validate_row,
                     {"context": None, "overrides": None, "on_error": "record"},
                     id="validate_row"),
        pytest.param(reg.load_overrides, {}, id="load_overrides"),
        pytest.param(engine.validate,
                     {"overrides": None, "context_builder": None,
                      "on_error": "record"}, id="validate"),
        pytest.param(rep.build_report,
                     {"key_column": None, "extra_columns": None,
                      "include": "failures"}, id="build_report"),
        pytest.param(rep.render_report,
                     {"fmt": "table", "wrap_width": 48}, id="render_report"),
        pytest.param(rep.write_report,
                     {"fmt": "csv"}, id="write_report"),
        pytest.param(tables.format_table, {"wrap_columns": None}, id="format_table"),
    ],
)
def test_public_defaults(fn: Any, expected: dict[str, Any]) -> None:
    assert defaults(fn) == expected


def test_load_checks_names_files_explicitly() -> None:
    """This package ships no checks and discovers nothing, so a path is required."""

    with pytest.raises(TypeError):
        reg.load_checks()  # type: ignore[call-arg]


def test_validate_row_returns_outcomes_not_a_separate_result_type(fresh_registry: None) -> None:
    from conftest import first_cause, make_check

    make_check("FAILS", passes=False)
    results = engine.validate_row(_row())
    assert all(isinstance(result, res.CheckOutcome) for result in results)
    assert (results[0].code, results[0].message) == ("FAILS", "FAILS failed")


def test_root_cause_accepts_either_functions_output(fresh_registry: None) -> None:
    from conftest import first_cause, make_check

    make_check("FAILS", passes=False)
    row = _row()
    assert first_cause(engine.validate_row(row)) == "FAILS"
    assert first_cause(engine.explain_row(row)) == "FAILS"


def test_pass_is_a_shared_singleton() -> None:
    assert res.PASS is validation.PASS
    assert res.normalize_result(res.PASS, "CODE") is res.PASS


def _row() -> Any:
    import pandas as pd

    return pd.Series({"age": 1})
