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
from jobcheck import validate, validate_row, registry as reg
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


def fastest(work: Callable[[], Any], repeats: int = 5) -> float:
    """The best of several calls, after one warm-up call that is not timed.

    Timing noise is additive -- another process or a scheduler steal makes a
    call slower, never faster -- so the smallest of several runs is the one with
    the least of it in, which is what makes a ratio between two of these stable
    on a machine doing other work.

    The warm-up matters as much as the repeats here: one-off costs (import
    paths, first-touch allocation) land on whichever call runs first, and at
    these sizes they were larger than the measurement itself.

    ``repeats=1`` is the warm-up alone, and it is what the three ratios below
    use. Each of them measures the cheaper side first, so an unwarmed run
    inflates the denominator and pushes the ratio *down* -- toward passing, not
    toward a spurious failure -- which is why they ran on single measurements
    for so long without flaking. Measured 2026-09-22 over repeated trials, the
    rows ratio spreads 3.66-4.56 unwarmed, 4.04-4.28 warmed and 4.05-4.22 at
    best-of-five, against a bound of 8: the warm-up removes the bias for about
    six seconds, and the other twenty that best-of-five costs would only pay off
    by tightening the bounds, which this file deliberately keeps loose.
    """

    work()
    return min(seconds(work) for _ in range(repeats))


def test_validating_twice_the_rows_costs_about_twice_as_much(example_checks: None) -> None:
    small = fastest(lambda: validate(frame(2_000)), repeats=1)
    large = fastest(lambda: validate(frame(8_000)), repeats=1)
    ratio = large / small
    # Four times the rows: linear is 4, quadratic is 16.
    assert ratio < 8, f"4x the rows cost {ratio:.1f}x the time"


def test_twice_the_checks_costs_about_twice_as_much(fresh_registry: None) -> None:
    df = frame(500)
    for index in range(50):
        make_check(f"CODE_{index}")
    small = fastest(lambda: validate(df), repeats=1)
    for index in range(50, 200):
        make_check(f"CODE_{index}")
    large = fastest(lambda: validate(df), repeats=1)
    ratio = large / small
    # Four times the checks: linear is 4. A per-row topological sort over a
    # growing registry would show here as well above that.
    assert ratio < 8, f"4x the checks cost {ratio:.1f}x the time"
    assert len(reg._CHECKS) == 200


def test_a_deep_dependency_chain_does_not_cost_more_than_a_flat_one(
    fresh_registry: None,
) -> None:
    """Layers are resolved once, not walked per row."""

    df = frame(500)
    for index in range(100):
        make_check(f"FLAT_{index}")
    flat = fastest(lambda: validate(df), repeats=1)

    reg.clear_registry()
    make_check("DEEP_0")
    for index in range(1, 100):
        make_check(f"DEEP_{index}", depends_on=[f"DEEP_{index - 1}"])
    deep = fastest(lambda: validate(df), repeats=1)

    assert deep / flat < 5, f"a 100-deep chain cost {deep / flat:.1f}x a flat registry"


def test_building_a_report_scales_with_the_failures_not_the_rows(
    example_checks: None,
) -> None:
    """A frame of passing rows costs the report a fraction of a failing one.

    A fraction rather than nothing: the same number of rows is still walked, and
    their root causes still resolved, to produce no report lines at all. Measured
    at about a quarter on 4,000 rows.

    This asserted a bare ``quick < slow`` on two single measurements of about
    50ms each, and failed on a machine running a second suite -- the warm-up cost
    landed on ``quick``, which is measured first, and made the smaller number the
    larger one. Both are the best of five runs now, and the bound is a ratio
    with room in it, like every other check in this file.
    """

    clean = pd.DataFrame([{"age": 34, "email": "a@b.com",
                           "start_date": "2024-01-01", "end_date": "2024-02-01"}] * 4_000)
    messy = frame(4_000)
    clean_outcomes = validate(clean)
    messy_outcomes = validate(messy)

    quick = fastest(lambda: rep.build_report(clean_outcomes, df=clean))
    slow = fastest(lambda: rep.build_report(messy_outcomes, df=messy))

    assert len(rep.build_report(clean_outcomes, df=clean)) == 0
    assert len(rep.build_report(messy_outcomes, df=messy)) > 4_000
    ratio = slow / quick
    assert ratio > 2, f"a frame with no failures cost 1/{ratio:.1f} of a failing one"


def test_row_by_row_holds_less_than_collecting_on_the_same_frame(
    example_checks: None,
) -> None:
    """validate_row's whole reason to exist, measured rather than asserted in a docstring.

    validate keeps one outcome per check per row; validate_row keeps one
    row's worth at a time. On 6,000 rows the difference is the thing that decides
    whether a large frame can be reported on at all.
    """

    df = frame(6_000)

    tracemalloc.start()
    collected = validate(df)
    collected_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert len(collected) == 6_000
    del collected

    tracemalloc.start()
    failures = 0
    for _, row in df.iterrows():
        failures += len(validate_row(row))
    streamed_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    assert failures > 0
    assert streamed_peak * 4 < collected_peak, (
        f"streaming peaked at {streamed_peak / 1e6:.1f} MB against "
        f"{collected_peak / 1e6:.1f} MB collected"
    )


def test_row_by_row_memory_does_not_grow_with_the_frame(example_checks: None) -> None:
    """Twice the rows, the same peak: nothing accumulates between rows."""

    def peak_for(df: pd.DataFrame) -> int:
        tracemalloc.start()
        for _, row in df.iterrows():
            validate_row(row)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return peak

    # Both frames are built before anything is traced: with the frame inside
    # the measurement, a peak four times larger was explained by the frame alone
    # and the bound below could not fail -- an engine leaking every outcome
    # passed it.
    small_frame = frame(2_000)
    large_frame = frame(8_000)
    small = peak_for(small_frame)
    large = peak_for(large_frame)
    # One row's worth of work at a time, whatever the frame. The peaks are
    # under a megabyte and iterrows' own bookkeeping grows a little with the
    # frame, so the bound is absolute: 6,000 more rows of retained outcomes
    # would be well over ten megabytes, and this allows two.
    assert large - small < 2 * 1024 * 1024, (
        f"peak went {small / 1e6:.1f} MB to {large / 1e6:.1f} MB")
