"""The whole-frame entry point: one list of outcomes per row, in frame order.

`tests/test_validate_row_unit.py` covers the per-row algorithm `validate` calls.
These cover what `validate` itself adds: the shape it hands back, the order it
hands it back in, and that every argument reaches `explain_row` unchanged.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import (
    DISABLED,
    ERRORED,
    FAILED,
    PASSED,
    SKIPPED,
    RowContext,
    register_check,
    validate,
)
from jobcheck.rules import OverrideRule

pytestmark = pytest.mark.fast


def frame(rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame([{"id": index, "value": index} for index in range(rows)])


def test_one_list_of_outcomes_per_row(fresh_registry: None) -> None:
    make_check("A")
    outcomes = validate(frame(3))
    assert [[o.code for o in row] for row in outcomes] == [["A"], ["A"], ["A"]]


def test_outcomes_follow_frame_order_not_index_labels(fresh_registry: None) -> None:
    """A filtered frame keeps its original labels; the outcomes are positional."""

    make_check("A", passes=False)
    df = frame(3)
    df.index = [100, 200, 300]
    outcomes = validate(df)
    assert [row[0].outcome for row in outcomes] == [FAILED, FAILED, FAILED]


def test_each_row_gets_its_own_outcomes_in_its_own_position(fresh_registry: None) -> None:
    """The contract every caller indexes by: outcome list *i* describes row *i*.

    Nothing else here would notice the rows being reversed, because the checks
    used elsewhere give every row the same verdict. This one fails the middle
    row only, so the position of the failure is the assertion.
    """

    @register_check(code="ODD_VALUE", message="value is odd")
    def odd_value(row: "pd.Series[Any]") -> bool:
        return int(row["value"]) % 2 == 0

    outcomes = validate(frame(4))
    assert [row[0].outcome for row in outcomes] == [PASSED, FAILED, PASSED, FAILED]


def test_checks_that_did_not_run_are_kept(fresh_registry: None) -> None:
    make_check("A", passes=False)
    make_check("B", depends_on=["A"])
    outcomes = validate(frame(1))
    assert [(o.code, o.outcome) for o in outcomes[0]] == [("A", FAILED), ("B", SKIPPED)]
    assert outcomes[0][1].detail == "prerequisite did not pass: A"


def test_an_empty_frame_produces_no_outcomes(fresh_registry: None) -> None:
    make_check("A")
    assert validate(frame(0)) == []


def test_overrides_reach_the_per_row_engine(fresh_registry: None) -> None:
    make_check("A", passes=False)
    rule = OverrideRule(name="off", action="disable", codes=["A"], criteria=[], match_all=True)
    outcomes = validate(frame(1), overrides=[rule])
    assert outcomes[0][0].outcome == DISABLED
    assert outcomes[0][0].detail == "disabled by rule 'off'"


def test_the_context_builder_is_called_once_per_row(fresh_registry: None) -> None:
    """The context reaches the check unchanged, which is what lets one shared
    object carry the whole frame to a cross-row check."""

    seen: list[Any] = []

    @register_check(code="CTX", message="ctx")
    def uses_context(row: "pd.Series[Any]", ctx: Any) -> bool:
        seen.append(ctx)
        return True

    shared = RowContext(flags={"whole_frame": True})
    outcomes = validate(frame(2), context_builder=lambda row: shared)
    assert seen == [shared, shared]
    assert [row[0].outcome for row in outcomes] == [PASSED, PASSED]


def test_on_error_records_the_exception_and_keeps_going(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("nope"))
    outcomes = validate(frame(2))
    assert [row[0].outcome for row in outcomes] == [ERRORED, ERRORED]
    assert outcomes[0][0].detail == "RuntimeError: nope"


def test_on_error_raise_stops_at_the_first_broken_check(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("nope"))
    with pytest.raises(RuntimeError, match="nope"):
        validate(frame(2), on_error="raise")


def test_a_bad_on_error_is_rejected_before_anything_runs(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("A", calls=calls)
    with pytest.raises(ValueError, match="on_error must be 'record' or 'raise'"):
        validate(frame(2), on_error="explode")
    assert calls == []
