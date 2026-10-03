"""Unit checks: RowContext as the base type an adopter subclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest

from jobcheck import RowContext

pytestmark = pytest.mark.fast


def test_the_base_context_carries_no_fields() -> None:
    """Bare by design: the library defines the type and invents no fields."""

    import dataclasses

    assert [f.name for f in dataclasses.fields(RowContext)] == []


@dataclass
class FileContext(RowContext):
    """What an adopter writes: the base plus the fields its checks read."""

    counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, row: "pd.Series[Any]") -> "FileContext":
        return cls(counts={str(row["source"]): 1})


def test_a_check_caching_on_the_shared_context_errors_rather_than_reusing_a_row(
    fresh_registry: None,
) -> None:
    """The memo pattern the context exists for. On the shared context it gave
    every row the first row's value, so -3 and -7 passed as 5; now it errors.

    The base refuses a new attribute because, without a builder, every row shares
    one bare context: a value cached on it would reach every later row, and later
    calls too."""

    from jobcheck import OK, Verdict, validate
    from jobcheck import registry as reg
    from jobcheck.results import Outcome

    @reg.register_check(code="PARSES", message="m")
    def parses(row: "pd.Series[Any]", context: Any) -> Verdict:
        if getattr(context, "parsed", None) is None:
            context.parsed = float(row["x"])
        return OK

    outcomes = validate(pd.DataFrame({"x": ["5", "-3"]}))
    assert [row[0].outcome for row in outcomes] == [Outcome.ERRORED] * 2
    assert "AttributeError" in outcomes[0][0].detail


def test_a_subclass_carries_whatever_the_pipeline_needs() -> None:
    context = FileContext(counts={"MODERN": 2})
    assert isinstance(context, RowContext)
    assert context.counts == {"MODERN": 2}
    assert FileContext().counts == {}
    # The base's empty __slots__ does not reach a subclass: it keeps its __dict__.
    context.cached = 1  # type: ignore[attr-defined]
    assert context.cached == 1  # type: ignore[attr-defined]


def test_validate_without_a_context_hands_every_row_a_bare_one(
    fresh_registry: None,
) -> None:
    """The default path: no builder, or a builder returning None (``ContextBuilder``
    may), so a check that reads the context still gets one."""

    from jobcheck import OK, Verdict, validate
    from jobcheck import registry as reg

    seen: list[RowContext | None] = []

    @reg.register_check(code="SEES_CONTEXT", message="never fails")
    def check(row: "pd.Series[Any]", context: RowContext | None) -> Verdict:
        seen.append(context)
        return OK

    validate(pd.DataFrame([{"a": 1}, {"a": 2}]))
    validate(pd.DataFrame([{"a": 1}]), context_builder=lambda row: None)
    assert seen == [RowContext()] * 3
    assert all(isinstance(context, RowContext) for context in seen)


def test_a_caller_supplied_builder_is_what_reaches_the_checks(fresh_registry: None) -> None:
    """The documented replacement path, exercised rather than described."""

    from jobcheck import OK, Verdict, Status, validate
    from jobcheck import registry as reg

    @reg.register_check(code="NEEDS_FLAG", message="the context said no")
    def check(row: "pd.Series[Any]", context: RowContext | None) -> Verdict:
        counts = getattr(context, "counts", {})
        return OK if counts.get("MODERN") else Verdict(Status.INVALID, {})

    frame = pd.DataFrame([{"source": "MODERN"}, {"source": "LEGACY"}])
    outcomes = validate(frame, context_builder=FileContext.build)
    assert [o[0].failed for o in outcomes] == [False, True]
