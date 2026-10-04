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
    RowContext,
    register_check,
    validate,
    Outcome,
)
from jobcheck.rules import Rule
from jobcheck import registry as reg
from jobcheck.results import OK, Verdict

pytestmark = pytest.mark.fast


def frame(rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame([{"id": index, "value": index} for index in range(rows)])


@dataclass
class RunContext(RowContext):
    """A context with one option, for the tests that pass a context through."""

    strict: bool = False


def test_each_row_gets_its_own_outcomes_in_its_own_position(fresh_registry: None) -> None:
    """The contract every caller indexes by: outcome list *i* describes row *i*.

    Nothing else here would notice the rows being reversed, because the checks
    used elsewhere give every row the same verdict. This one fails the odd rows
    only, so the position of the failure is the assertion. A filtered frame keeps
    its original labels; the outcomes are positional all the same.
    """

    @register_check(code="ODD_VALUE", message="value is odd")
    def odd_value(row: "pd.Series[Any]") -> Verdict:
        return Verdict(int(row["value"]) % 2 == 0)

    df = frame(4)
    df.index = [100, 200, 300, 400]
    outcomes = validate(df)
    assert [[o.code for o in row] for row in outcomes] == [["ODD_VALUE"]] * 4
    assert [row[0].outcome for row in outcomes] == [Outcome.PASSED, Outcome.FAILED, Outcome.PASSED, Outcome.FAILED]


def test_an_empty_frame_produces_no_outcomes(fresh_registry: None) -> None:
    make_check("A")
    assert validate(frame(0)) == []


def test_rules_given_as_a_generator_apply_to_every_row(fresh_registry: None) -> None:
    """A filtering generator is the idiomatic way to pass a subset. Read once per
    row as it came, it was empty from the second row on, and the check ran there."""

    make_check("A", passes=False)
    rules = [Rule(name="off", action="disable", codes=["A"], criteria=[], match_all=True,
                  message="why the rule exists")]
    outcomes = validate(frame(3), rules=(rule for rule in rules))  # type: ignore[arg-type]
    assert [row[0].outcome for row in outcomes] == [Outcome.DISABLED] * 3
    assert outcomes[2][0].detail == "disabled by rule 'off'"


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
    assert [row[0].outcome for row in outcomes] == [Outcome.PASSED, Outcome.PASSED]


def test_on_error_records_the_exception_and_keeps_going(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("nope"))
    outcomes = validate(frame(2))
    assert [row[0].outcome for row in outcomes] == [Outcome.ERRORED, Outcome.ERRORED]
    assert outcomes[0][0].detail.startswith("RuntimeError: nope (conftest.py:")


def test_on_error_raise_stops_at_the_first_broken_check(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("nope"))
    with pytest.raises(RuntimeError, match="nope"):
        validate(frame(2), on_error="raise")


def test_a_bad_on_error_is_refused_even_on_an_empty_frame(fresh_registry: None) -> None:
    """The mode was only checked per row, so an empty frame let a typo through."""

    make_check("CODE")
    with pytest.raises(ValueError, match="on_error must be 'record' or 'raise'"):
        validate(pd.DataFrame(columns=["age"]), on_error="ignore")


def test_a_context_builder_taking_two_arguments_is_given_the_context_args(
    fresh_registry: None,
) -> None:
    """The shape a pipeline wants: a named function taking `(row, args)`, not a
    lambda closing over them. `context_args` is passed through untouched."""

    rows_seen: list[int] = []

    def build_context(row: Any, args: Any) -> RunContext:
        rows_seen.append(row["a"])
        return RunContext(strict=args["strict"])

    seen: list[bool] = []

    @reg.register_check("STRICTNESS", "m")
    def strictness(row: Any, context: Any) -> Any:
        seen.append(context.strict)
        return OK

    frame = pd.DataFrame([{"a": 1}, {"a": 2}])
    validate(frame, context_builder=build_context, context_args={"strict": True})
    assert seen == [True, True]
    assert rows_seen == [1, 2]


def test_a_builder_taking_neither_shape_says_so(fresh_registry: None) -> None:
    """The same message shape a check gets for the same mistake, and raised once
    per validate rather than once per row."""

    make_check("CODE")
    with pytest.raises(ValueError) as raised:
        validate(pd.DataFrame([{"a": 1}]),
                 context_builder=lambda row, args, extra: RowContext())
    assert "must take (row) or (row, context_args), not 3 positional argument(s)" in str(
        raised.value)


def test_a_builder_whose_keyword_argument_has_a_default_is_accepted(
    fresh_registry: None
) -> None:
    make_check("CODE")
    seen: list[str] = []

    def build(row, *, mode="strict"):  # type: ignore[no-untyped-def]
        seen.append(mode)
        return RowContext()

    validate(pd.DataFrame([{"a": 1}]), context_builder=build)
    assert seen == ["strict"]


def test_a_builder_that_raises_propagates_unchanged_under_record(
    fresh_registry: None,
) -> None:
    """The documented contract (owner's decision, 2026-09-28): on_error covers the
    checks, not the builder, so a builder must not raise on the data. Pinned so a
    change to it is a decision rather than an accident. Unchanged means the
    type and message; a note naming the row is added where Python has notes."""

    make_check("CODE")

    def build_context(row: Any) -> RowContext:
        raise TypeError("blank cell")

    with pytest.raises(TypeError) as raised:
        validate(frame(2), context_builder=build_context)
    assert str(raised.value) == "blank cell"


def _notes(exc: BaseException) -> list[str]:
    return list(getattr(exc, "__notes__", []))


@pytest.mark.skipif(not hasattr(Exception, "add_note"), reason="add_note is Python 3.11+")
def test_an_exception_escaping_validate_names_the_row_and_keeps_its_type(
    fresh_registry: None,
) -> None:
    """On a large frame, the row is what the reader needs to find; the type is
    what a caller's except clause matches, so it must not change."""

    @register_check("ROW_ONE", "row one is bad")
    def row_one(row: Any) -> Verdict:
        if row["id"] == 1:
            raise ZeroDivisionError("division by zero")
        return OK

    df = frame(3).set_axis(["a", "b", "c"])
    with pytest.raises(ZeroDivisionError) as raised:
        validate(df, on_error="raise")
    assert str(raised.value) == "division by zero"
    assert _notes(raised.value) == [
        "validate: raised on the row at position 1 (index label 'b')."]


@pytest.mark.skipif(not hasattr(Exception, "add_note"), reason="add_note is Python 3.11+")
def test_a_raising_builder_and_a_bad_return_name_the_row_too(fresh_registry: None) -> None:
    def build_context(row: Any) -> RowContext:
        raise KeyError("ctx")

    make_check("CODE")
    with pytest.raises(KeyError) as raised:
        validate(frame(2), context_builder=build_context)
    assert _notes(raised.value) == [
        "validate: raised on the row at position 0 (index label 0)."]

    # A bad return is an authoring bug, not a data problem, so it is never
    # recorded. The only test of that path through the engine, so the message
    # names the check.
    @register_check("NONE", "returns nothing")
    def returns_none(row: Any) -> Any:
        return None

    with pytest.raises(TypeError, match=r"Check 'NONE' returned None") as raised_type:
        validate(frame(2))
    assert _notes(raised_type.value) == [
        "validate: raised on the row at position 0 (index label 0)."]


@pytest.mark.skipif(not hasattr(Exception, "add_note"), reason="add_note is Python 3.11+")
def test_a_broken_registry_is_not_blamed_on_a_row(fresh_registry: None) -> None:
    """A prerequisite nothing registered is the check author's mistake, and no
    row would fix it: the note must not send the reader to row 0."""

    make_check("DANGLING", depends_on=["NOT_A_REAL_CODE"])
    with pytest.raises(ValueError, match="which is not registered") as raised:
        validate(frame(2))
    assert _notes(raised.value) == []
