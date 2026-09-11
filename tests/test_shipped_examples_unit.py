"""The shipped examples are part of the product, so they are tested like it.

`examples/` is what an adopter copies: the suites, the rule files and the data.
A rule file that cannot be loaded beside another, a rule naming a code no suite
defines, or a data file that stopped exercising the checks it was built for are
all defects in the documentation as delivered.

The duplicate-name check is a regression check: the four shipped rule files could
not be loaded in one call until 2026-09-10, because two pairs of them shared a
rule name and names are unique across a load.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from conftest import PROJECT_ROOT
from jobcheck import (
    check_rule_columns,
    validate,
    load_overrides,
    registry as reg,
)

pytestmark = pytest.mark.fast

RULES_DIR = Path(PROJECT_ROOT) / "examples" / "rules"
DATA_DIR = Path(PROJECT_ROOT) / "examples" / "data"


def rule_files() -> list[Path]:
    return sorted(RULES_DIR.rglob("*.yaml"))


def test_there_are_rule_files_to_check() -> None:
    assert len(rule_files()) >= 4


def test_every_shipped_rule_file_loads_on_its_own(example_checks: None) -> None:
    for path in rule_files():
        assert load_overrides([str(path)]), path


def test_all_shipped_rule_files_load_together(example_checks: None) -> None:
    """Regression: two pairs of them shared a rule name, so this call raised.

    Rule names are unique across everything loaded in one call, which makes a
    shared name between two shipped files a trap rather than a preference -- the
    two files simply cannot be combined, and every example that combines them
    fails with a duplicate-name error.
    """

    overrides = load_overrides([str(path) for path in rule_files()])
    names = [rule.name for rule in overrides]
    assert len(names) == len(set(names))


def test_every_shipped_rule_name_is_unique_in_its_own_right() -> None:
    """The same check without loading, so it fails on the file rather than the run."""

    names: dict[str, Path] = {}
    for path in rule_files():
        for rule in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            name = rule["name"]
            assert name not in names, f"{name} in {path} and {names.get(name)}"
            names[name] = path


def test_every_shipped_rule_names_a_code_the_example_checks_define(
    example_checks: None,
) -> None:
    known = {check.code for check in reg.CHECKS}
    for path in rule_files():
        for rule in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            for code in rule["codes"]:
                assert code in known, f"{code} in {path}"


def test_every_shipped_rule_matches_a_column_the_data_has(example_checks: None) -> None:
    """A rule filtering on a column the example data lacks can never fire."""

    overrides = load_overrides([str(path) for path in rule_files()])
    frame = pd.read_csv(DATA_DIR / "customers.csv", dtype=str)
    assert check_rule_columns(frame, overrides) == []


# --- the data files ---------------------------------------------------------


@pytest.mark.parametrize("name, rows", [
    ("customers.csv", 49),
    ("customers_clean.csv", 24),
    ("customers_large.csv", 2000),
])
def test_each_data_file_is_the_size_its_documentation_claims(name: str, rows: int) -> None:
    frame = pd.read_csv(DATA_DIR / name, dtype=str)
    assert len(frame) == rows


def test_the_messy_file_exercises_every_shipped_test(example_checks: None) -> None:
    """Data that stopped failing anything would make the whole catalog vacuous."""

    frame = pd.read_csv(DATA_DIR / "customers.csv", dtype=str)
    failed = {outcome.code
              for outcomes in validate(frame)
              for outcome in outcomes if outcome.failed}
    expected = {"ROW_ALL_NULL", "AGE_PRESENT", "AGE_NOT_A_NUMBER", "AGE_NEGATIVE",
                "AGE_TOO_HIGH", "DATES_PRESENT", "DATES_OUT_OF_ORDER",
                "EMAIL_PRESENT", "EMAIL_MISSING_AT", "EMAIL_DOMAIN_INVALID"}
    assert expected <= failed


def test_the_clean_file_fails_nothing(example_checks: None) -> None:
    frame = pd.read_csv(DATA_DIR / "customers_clean.csv", dtype=str)
    failed = [outcome.code
              for outcomes in validate(frame)
              for outcome in outcomes if outcome.failed]
    assert failed == []


def test_the_messy_file_still_holds_the_awkward_values_the_catalog_relies_on() -> None:
    """Named individually: each is a case some example exists to demonstrate."""

    text = (DATA_DIR / "customers.csv").read_text(encoding="utf-8")
    assert "=SUM(A1:A9)" in text, "the formula-injection row"
    assert "Karen Spärck Jones" in text, "the non-ASCII name"
    assert "Sun Microsystems, Inc." in text, "the value holding a comma"
    assert "qa@internal.test" in text, "the exempted internal account"
    assert "LEGACY_A" in text, "the legacy source system the rules select on"
    assert ",,,,,,,," in text, "the entirely blank row"


def test_the_generator_reproduces_the_committed_files_exactly() -> None:
    """The data is generated, so a hand edit to the CSV would be lost silently."""

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_example_data", Path(PROJECT_ROOT) / "scripts" / "make_example_data.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import csv
    import io

    for name, rows in [("customers.csv", module.small_rows()),
                       ("customers_clean.csv", module.clean_rows()),
                       ("customers_large.csv", module.large_rows(2000))]:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=module.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        assert buffer.getvalue() == (DATA_DIR / name).read_text(encoding="utf-8"), name
