"""Scaling: how cost grows as one dimension grows, not how fast it is once.

A fixed ceiling ("20,000 rows in under 60s") catches a tenfold regression on the
machine that wrote it and nothing on a faster one. These checks assert the
*shape* instead -- doubling the rows should roughly double the work, not
quadruple it -- which is machine-independent and is what an accidental per-row
sort, per-row file read or per-row registry rebuild actually breaks.

Ratios are generous on purpose. The failure being hunted is quadratic growth,
which shows as a ratio of 4 or more where 2 was expected; noise of 50% either
way is normal on a shared machine and must not fail a run.
"""

from __future__ import annotations

import time
import tracemalloc
from typing import Any, Callable

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import collect_outcomes, iter_traces, registry as reg
from jobcheck import report as rep

pytestmark = pytest.mark.long


def frame(rows: int) -> pd.DataFrame:
    """A frame of *rows* rows, one in four failing, in a repeating pattern."""

    pattern = [
        {"age": 34, "email": "a@b.com", "start_date": "2024-01-01", "end_date": "2024-02-01"},
        {"age": -5, "email": "nope", "start_date": "2024-01-01", "end_date": "2024-02-01"},
        {"age": 200, "email": "c@nodot", "start_date": "2024-01-01", "end_date": "2024-02-01"},
        {"age": None, "email": None, "start_date": None, "end_date": None},
    ]
    return pd.DataFrame([pattern[i % 4] for i in range(rows)])


def seconds(work: Callable[[], Any]) -> float:
    """Wall time for one call, with a floor so a ratio never divides by zero."""

    started = time.perf_counter()
    work()
    return max(time.perf_counter() - started, 1e-6)


def test_validating_twice_the_rows_costs_about_twice_as_much(example_suites: None) -> None:
    small = seconds(lambda: collect_outcomes(frame(2_000)))
    large = seconds(lambda: collect_outcomes(frame(8_000)))
    ratio = large / small
    # Four times the rows: linear is 4, quadratic is 16.
    assert ratio < 8, f"4x the rows cost {ratio:.1f}x the time"


def test_twice_the_tests_costs_about_twice_as_much(fresh_registry: None) -> None:
    df = frame(500)
    for index in range(50):
        make_check(f"CODE_{index}")
    small = seconds(lambda: collect_outcomes(df))
    for index in range(50, 200):
        make_check(f"CODE_{index}")
    large = seconds(lambda: collect_outcomes(df))
    ratio = large / small
    # Four times the checks: linear is 4. A per-row topological sort over a
    # growing registry would show here as well above that.
    assert ratio < 8, f"4x the checks cost {ratio:.1f}x the time"
    assert len(reg.CHECKS) == 200


def test_a_deep_dependency_chain_does_not_cost_more_than_a_flat_one(
    fresh_registry: None,
) -> None:
    """Layers are resolved once, not walked per row."""

    df = frame(500)
    for index in range(100):
        make_check(f"FLAT_{index}")
    flat = seconds(lambda: collect_outcomes(df))

    reg.clear_registry()
    make_check("DEEP_0")
    for index in range(1, 100):
        make_check(f"DEEP_{index}", depends_on=[f"DEEP_{index - 1}"])
    deep = seconds(lambda: collect_outcomes(df))

    assert deep / flat < 5, f"a 100-deep chain cost {deep / flat:.1f}x a flat registry"


def test_building_a_report_scales_with_the_failures_not_the_rows(
    example_suites: None,
) -> None:
    """A frame of passing rows costs the report almost nothing."""

    clean = pd.DataFrame([{"age": 34, "email": "a@b.com",
                           "start_date": "2024-01-01", "end_date": "2024-02-01"}] * 4_000)
    messy = frame(4_000)
    clean_outcomes = collect_outcomes(clean)
    messy_outcomes = collect_outcomes(messy)

    quick = seconds(lambda: rep.build_report(clean_outcomes, df=clean))
    slow = seconds(lambda: rep.build_report(messy_outcomes, df=messy))

    assert len(rep.build_report(clean_outcomes, df=clean)) == 0
    assert len(rep.build_report(messy_outcomes, df=messy)) > 4_000
    assert quick < slow


def test_streaming_holds_less_than_collecting_on_the_same_frame(
    example_suites: None,
) -> None:
    """iter_traces' whole reason to exist, measured rather than asserted in a docstring.

    collect_outcomes keeps one outcome per check per row; iter_traces keeps one
    row's worth at a time. On 6,000 rows the difference is the thing that decides
    whether a large frame can be reported on at all.
    """

    df = frame(6_000)

    tracemalloc.start()
    collected = collect_outcomes(df)
    collected_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert len(collected) == 6_000
    del collected

    tracemalloc.start()
    failures = 0
    for trace in iter_traces(df):
        failures += len(trace.failures)
    streamed_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    assert failures > 0
    assert streamed_peak * 4 < collected_peak, (
        f"streaming peaked at {streamed_peak / 1e6:.1f} MB against "
        f"{collected_peak / 1e6:.1f} MB collected"
    )


def test_streaming_memory_does_not_grow_with_the_frame(example_suites: None) -> None:
    """Twice the rows, the same peak: nothing accumulates between yields."""

    def peak_for(rows: int) -> int:
        tracemalloc.start()
        for _ in iter_traces(frame(rows)):
            pass
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return peak

    small = peak_for(2_000)
    large = peak_for(8_000)
    # The frame itself is four times bigger, so the peak may not be flat -- but
    # it must not carry the outcomes, which would be four times as many objects.
    assert large < small * 4, f"peak went {small / 1e6:.1f} MB to {large / 1e6:.1f} MB"
