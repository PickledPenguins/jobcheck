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


def test_two_base_contexts_are_equal_and_separate_objects() -> None:
    first, second = RowContext(), RowContext()
    assert first == second
    assert first is not second


@dataclass
class FileContext(RowContext):
    """What an adopter writes: the base plus the fields its checks read."""

    counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, row: "pd.Series[Any]") -> "FileContext":
        return cls(counts={str(row["source"]): 1})


def test_a_subclass_carries_whatever_the_pipeline_needs() -> None:
    context = FileContext(counts={"MODERN": 2})
    assert isinstance(context, RowContext)
    assert context.counts == {"MODERN": 2}
    assert FileContext().counts == {}


def test_validate_without_a_builder_hands_every_row_a_bare_context(
    fresh_registry: None,
) -> None:
    """The default path: no builder, so a check that reads the context gets one."""

    from jobcheck import PASS, CheckResult, validate
    from jobcheck import registry as reg

    seen: list[RowContext | None] = []

    @reg.register_check(code="SEES_CONTEXT", message="never fails")
    def check(row: "pd.Series[Any]", context: RowContext | None) -> CheckResult:
        seen.append(context)
        return PASS

    validate(pd.DataFrame([{"a": 1}, {"a": 2}]))
    assert seen == [RowContext(), RowContext()]
    assert all(isinstance(context, RowContext) for context in seen)


def test_a_caller_supplied_builder_is_what_reaches_the_checks(fresh_registry: None) -> None:
    """The documented replacement path, exercised rather than described."""

    from jobcheck import PASS, CheckResult, Status, validate
    from jobcheck import registry as reg

    @reg.register_check(code="NEEDS_FLAG", message="the context said no")
    def check(row: "pd.Series[Any]", context: RowContext | None) -> CheckResult:
        counts = getattr(context, "counts", {})
        return PASS if counts.get("MODERN") else CheckResult(Status.INVALID, {})

    frame = pd.DataFrame([{"source": "MODERN"}, {"source": "LEGACY"}])
    outcomes = validate(frame, context_builder=FileContext.build)
    assert [o[0].failed for o in outcomes] == [False, True]
