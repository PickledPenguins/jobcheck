"""Differential checks: the behaviour jobchain's suite asserted of the check-era engine.

``~/work/ai/jobchain`` was written against the pre-rename library and is the only
surviving *written* record of what that engine did -- its checks are executable
expectations, not prose. Each check here is one of those expectations, restated in
this package's vocabulary (``check_group``, ``CheckResult``, ``load_checks``).

They exist to answer one question: does this tree behave the way the tree
jobchain was written against behaved? A failure here that a rename does not
explain is a real behavioural difference between the two lineages, so these are
kept as their own module rather than folded into the unit suites.

Two differences are already known and are not defects here:

- the override rule format gained ``match:``. The check era took a single
  top-level ``column``/``pattern`` pair matched with ``fnmatchcase``; this tree
  takes a list of criteria matched as regular expressions (see
  ``recovery/bytecode/jobcheck/rules.cpython-312.pyc``, whose ``RULE_KEYS`` is
  ``{name, action, codes, column, pattern}``).
- ``ctx.count(column, value)`` is jobchain's own :class:`RowContext` subclass,
  not part of this library. The population is built here the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from jobcheck import (
    ERRORED,
    load_overrides_from_files,
    load_checks,
    validate,
)

pytestmark = pytest.mark.fast

SIMPLE = """
from jobcheck import PASS, Status, CheckResult, check_group
g = check_group()

@g("B_INT", "b must be a whole number")
def b_int(row):
    if not row["b"].isdigit():
        return CheckResult(Status.MALFORMED, {"value": row["b"]})
    return PASS
"""

LAYERED = """
from jobcheck import PASS, Status, CheckResult, check_group
g = check_group()

@g("B_PRESENT", "b is missing")
def b_present(row):
    return PASS if row["b"].strip() else CheckResult(Status.MISSING)

@g("B_INT", "b must be a whole number", depends_on=["B_PRESENT"])
def b_int(row):
    return PASS if row["b"].isdigit() else CheckResult(Status.MALFORMED)

@g("B_POSITIVE", "b must be positive", depends_on=["B_INT"])
def b_positive(row):
    return PASS if int(row["b"]) > 0 else CheckResult(Status.INVALID)
"""

CROSS_ROW = """
from jobcheck import PASS, Status, CheckResult, check_group
g = check_group()

@g("A_UNIQUE", "a is not unique in this file")
def a_unique(row, ctx):
    n = ctx.count("a", row["a"])
    return PASS if n <= 1 else CheckResult(Status.INVALID, {"a": row["a"], "n": n})
"""

CRASHES = """
from jobcheck import check_group
from jobcheck import engine
g = check_group()

@g("BOOM", "b is above the limit")
def boom(row):
    return 1 / 0
"""


@dataclass
class CountingContext:
    """jobchain's context: the whole file, plus a per-column value count.

    Every row is handed the same instance, built once, which is what makes a
    cross-row check possible at all.
    """

    counts: dict[str, dict[Any, int]] = field(default_factory=dict)

    def count(self, column: str, value: Any) -> int:
        return self.counts.get(column, {}).get(value, 0)


def counting_builder(frame: pd.DataFrame) -> Any:
    """A ``context_builder`` handing every row one context built from *frame*."""

    counts = {column: frame[column].value_counts().to_dict() for column in frame.columns}
    shared = CountingContext(counts=counts)
    return lambda row: shared


def write_file(tmp_path: Path, body: str, name: str = "c.py") -> str:
    path = tmp_path / name
    path.write_text(body)
    return str(path)


def frame(*records: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(list(records))


def test_no_records_is_no_results(fresh_registry: None, tmp_path: Path) -> None:
    load_checks([write_file(tmp_path, SIMPLE)])
    assert list(validate(pd.DataFrame(columns=["a", "b"]))) == []


def test_a_passing_row_has_no_failures(fresh_registry: None, tmp_path: Path) -> None:
    load_checks([write_file(tmp_path, SIMPLE)])
    assert validate(frame({"a": "x", "b": "1"})).explain(0).failures == []


def test_a_failing_row_reports_the_code_message_and_comments(
    fresh_registry: None, tmp_path: Path
) -> None:
    load_checks([write_file(tmp_path, SIMPLE)])
    (failure,) = validate(frame({"a": "x", "b": "zz"})).explain(0).failures
    assert failure.code == "B_INT"
    assert failure.message == "b must be a whole number"
    assert failure.comments == {"value": "zz"}
    assert failure.outcome != ERRORED


def test_failures_line_up_with_the_rows_they_came_from(
    fresh_registry: None, tmp_path: Path
) -> None:
    load_checks([write_file(tmp_path, SIMPLE)])
    run = validate(frame({"a": "x", "b": "1"}, {"a": "y", "b": "zz"}, {"a": "z", "b": "3"}))
    assert [bool(trace.failures) for trace in run] == [False, True, False]


def test_a_blank_column_produces_one_failure_not_three(
    fresh_registry: None, tmp_path: Path
) -> None:
    # The dependency layering is the reason to use this library at all.
    load_checks([write_file(tmp_path, LAYERED)])
    trace = validate(frame({"a": "x", "b": ""})).explain(0)
    assert [failure.code for failure in trace.failures] == ["B_PRESENT"]


def test_the_shallowest_failure_is_the_root_cause(
    fresh_registry: None, tmp_path: Path
) -> None:
    load_checks([write_file(tmp_path, LAYERED)])
    trace = validate(frame({"a": "x", "b": "0"})).explain(0)
    assert [failure.code for failure in trace.failures] == ["B_POSITIVE"]
    assert trace.root_cause == "B_POSITIVE"


def test_a_cross_row_test_sees_the_whole_file(fresh_registry: None, tmp_path: Path) -> None:
    load_checks([write_file(tmp_path, CROSS_ROW)])
    data = frame({"a": "dup", "b": "1"}, {"a": "dup", "b": "2"})
    run = validate(data, context_builder=counting_builder(data))
    assert [trace.failures[0].code for trace in run] == ["A_UNIQUE", "A_UNIQUE"]
    assert run.explain(0).failures[0].comments["n"] == 2


def test_the_population_can_come_from_rows_that_are_not_being_validated(
    fresh_registry: None, tmp_path: Path
) -> None:
    # jobchain's among=: correcting one row asks whether it is acceptable *in
    # this run*, so the counts come from every row, not from the one corrected.
    load_checks([write_file(tmp_path, CROSS_ROW)])
    population = frame({"a": "taken", "b": "9"}, {"a": "taken", "b": "1"})
    run = validate(frame({"a": "taken", "b": "1"}),
                   context_builder=counting_builder(population))
    assert run.explain(0).failures[0].code == "A_UNIQUE"


def test_a_test_that_raises_is_recorded_as_errored_and_keeps_the_exception(
    fresh_registry: None, tmp_path: Path
) -> None:
    load_checks([write_file(tmp_path, CRASHES)])
    (failure,) = validate(frame({"a": "x", "b": "1"})).explain(0).failures
    assert failure.outcome == ERRORED
    assert "ZeroDivisionError" in failure.detail


def test_the_run_counts_the_tests_that_raised(fresh_registry: None, tmp_path: Path) -> None:
    load_checks([write_file(tmp_path, CRASHES)])
    assert validate(frame({"a": "x", "b": "1"}, {"a": "y", "b": "2"})).errors == 2


def test_a_rule_file_switches_a_test_off_for_chosen_rows(
    fresh_registry: None, tmp_path: Path
) -> None:
    load_checks([write_file(tmp_path, SIMPLE)])
    rules = tmp_path / "r.yaml"
    rules.write_text(
        "- name: off_for_x\n"
        "  action: disable\n"
        "  codes: [B_INT]\n"
        "  match:\n"
        "    - column: a\n"
        "      pattern: '^x$'\n"
    )
    overrides = load_overrides_from_files([str(rules)])
    run = validate(frame({"a": "x", "b": "zz"}, {"a": "y", "b": "zz"}), overrides=overrides)
    assert run.explain(0).failures == []
    assert run.explain(1).failures[0].code == "B_INT"


def test_a_test_file_that_does_not_import_raises(fresh_registry: None, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="boom at import"):
        load_checks([write_file(tmp_path, "raise RuntimeError('boom at import')")])


def test_a_dangling_prerequisite_raises(fresh_registry: None, tmp_path: Path) -> None:
    body = (
        "from jobcheck import PASS, check_group\n"
        "g = check_group(depends_on=['NO_SUCH'])\n"
        "@g('X', 'x')\n"
        "def x(row): return PASS\n"
    )
    with pytest.raises(ValueError, match="NO_SUCH"):
        load_checks([write_file(tmp_path, body)])


def test_a_rule_naming_an_unknown_code_raises(fresh_registry: None, tmp_path: Path) -> None:
    load_checks([write_file(tmp_path, SIMPLE)])
    rules = tmp_path / "r.yaml"
    rules.write_text("- name: r\n  action: disable\n  codes: [NO_SUCH]\n  match: all\n")
    with pytest.raises(ValueError, match="NO_SUCH"):
        load_overrides_from_files([str(rules)])


def test_the_check_era_rule_format_is_rejected_rather_than_ignored(
    fresh_registry: None, tmp_path: Path
) -> None:
    # jobchain's rule files are still written in the check-era format: a single
    # top-level column/pattern pair, globbed. Silently ignoring the keys would
    # disable nothing and report failures the caller thought were switched off.
    load_checks([write_file(tmp_path, SIMPLE)])
    rules = tmp_path / "r.yaml"
    rules.write_text(
        "- name: off_for_x\n  action: disable\n  codes: [B_INT]\n  column: a\n  pattern: 'x'\n")
    with pytest.raises(ValueError):
        load_overrides_from_files([str(rules)])
