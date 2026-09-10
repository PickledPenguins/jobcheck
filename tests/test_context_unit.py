"""Unit checks: RowContext and the build_context integration stub."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from jobcheck import RowContext, build_context

pytestmark = pytest.mark.fast


def test_row_context_defaults_to_four_empty_dicts() -> None:
    context = RowContext()
    assert (context.flags, context.paths, context.state, context.extra) == ({}, {}, {}, {})


def test_row_context_instances_do_not_share_their_dicts() -> None:
    first = RowContext()
    first.flags["x"] = 1
    assert RowContext().flags == {}


def test_build_context_returns_an_empty_context() -> None:
    """The default builder invents nothing: the adopter fills the context."""

    ctx = build_context(pd.Series({"source_system": "LEGACY_A", "age": 30}))
    assert (ctx.flags, ctx.paths, ctx.state, ctx.extra) == ({}, {}, {}, {})


def test_build_context_reads_nothing_out_of_the_row() -> None:
    """Two different rows produce contexts that are equal and independent."""

    first = build_context(pd.Series({"a": 1}))
    second = build_context(pd.Series({"b": 2}))
    assert first == second == RowContext()
    first.flags["mine"] = True
    assert second.flags == {}


def test_a_caller_supplied_builder_is_what_reaches_the_checks(fresh_registry: None) -> None:
    """The documented replacement path, exercised rather than described."""

    from jobcheck import PASS, CheckResult, Status, collect_outcomes
    from jobcheck import registry as reg

    @reg.register_check(code="NEEDS_FLAG", message="the context said no")
    def check(row: "pd.Series[Any]", ctx: RowContext | None) -> CheckResult:
        return PASS if ctx and ctx.flags.get("allowed") else CheckResult(Status.INVALID, {})

    frame = pd.DataFrame([{"allow": True}, {"allow": False}])
    outcomes = collect_outcomes(
        frame, context_builder=lambda row: RowContext(flags={"allowed": bool(row["allow"])})
    )
    assert [o[0].failed for o in outcomes] == [False, True]
