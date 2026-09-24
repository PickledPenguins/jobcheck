"""The whole-frame entry point: one list of outcomes per row, in frame order.

`tests/test_validate_row_unit.py` covers the per-row algorithm `validate` calls.
These cover what `validate` itself adds: the shape it hands back, the order it
hands it back in, and that every argument reaches `explain_row` unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from jobcheck.rules import Rule
from jobcheck import registry as reg
from jobcheck.results import OK, Verdict

pytestmark = pytest.mark.fast


def frame(rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame([{"id": index, "value": index} for index in range(rows)])



@dataclass
class RunContext(RowContext):
    """Defined at module level on purpose: `clear_registry` evicts whatever module
    a check registered from, and a dataclass built after that eviction raises from
    `dataclasses` while resolving its annotations."""

    strict: bool = False


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
    def odd_value(row: "pd.Series[Any]") -> Verdict:
        return Verdict(int(row["value"]) % 2 == 0)

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


def test_rules_reach_the_per_row_engine(fresh_registry: None) -> None:
    make_check("A", passes=False)
    rule = Rule(name="off", action="disable", codes=["A"], criteria=[], match_all=True, message="why the rule exists")
    outcomes = validate(frame(1), rules=[rule])
    assert outcomes[0][0].outcome == DISABLED
    assert outcomes[0][0].detail == "disabled by rule 'off'"


def test_the_context_builder_is_called_once_per_row(fresh_registry: None) -> None:
    """The context reaches the check unchanged, which is what lets one shared
    object carry the whole frame to a cross-row check."""

    seen: list[Any] = []

    @register_check(code="CTX", message="ctx")
    def uses_context(row: "pd.Series[Any]", context: Any) -> Verdict:
        seen.append(context)
        return OK

    shared = RowContext()
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


def test_a_bad_on_error_is_refused_even_on_an_empty_frame(fresh_registry: None) -> None:
    """The mode was only checked per row, so an empty frame let a typo through."""

    make_check("CODE")
    with pytest.raises(ValueError, match="on_error must be 'record' or 'raise'"):
        validate(pd.DataFrame(columns=["age"]), on_error="ignore")


def test_a_series_is_refused_with_a_pointer_to_the_per_row_functions(
    fresh_registry: None,
) -> None:
    make_check("CODE")
    with pytest.raises(TypeError, match="validate takes a DataFrame, got Series"):
        validate(pd.Series({"age": 1}))  # type: ignore[arg-type]


def test_a_context_builder_taking_two_arguments_is_given_the_context_args(
    fresh_registry: None,
) -> None:
    """The shape a pipeline wants: a named function taking `(row, args)`, not a
    lambda closing over them. `context_args` is passed through untouched."""

    def build_context(row: Any, args: Any) -> RunContext:
        return RunContext(strict=args["strict"])

    seen: list[bool] = []

    @reg.register_check("STRICTNESS", "m")
    def strictness(row: Any, context: Any) -> Any:
        seen.append(context.strict)
        return OK

    frame = pd.DataFrame([{"a": 1}, {"a": 2}])
    validate(frame, context_builder=build_context, context_args={"strict": True})
    assert seen == [True, True]


def test_a_context_builder_taking_one_argument_still_gets_only_the_row(
    fresh_registry: None,
) -> None:
    """The corner case keeps working, and needs no context_args."""

    built: list[Any] = []

    def build_context(row: Any) -> RowContext:
        built.append(row["a"])
        return RowContext()

    make_check("CODE")
    validate(pd.DataFrame([{"a": 1}, {"a": 2}]), context_builder=build_context)
    assert built == [1, 2]


def test_a_builder_taking_neither_shape_says_so(fresh_registry: None) -> None:
    """The same message shape a check gets for the same mistake, and raised once
    per validate rather than once per row."""

    make_check("CODE")
    with pytest.raises(ValueError) as raised:
        validate(pd.DataFrame([{"a": 1}]),
                 context_builder=lambda row, args, extra: RowContext())
    assert "must take (row) or (row, context_args), not 3 positional argument(s)" in str(
        raised.value)
