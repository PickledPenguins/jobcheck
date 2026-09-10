"""Memory ceilings, in their own invocation.

``tracemalloc`` roughly triples the time of the code it watches, so these cannot
share a run with the timing gates without making those meaningless. They are
marked ``memory`` and run by ``./run-tests.sh memory``.

The ceilings are absolute rather than baseline-relative, because peak memory is
a property of the program rather than of the machine: the same frame allocates
the same objects everywhere, give or take the interpreter's own overhead.
"""

from __future__ import annotations

import tracemalloc

import pytest

from jobcheck import validate, validate_row, registry as reg
from jobcheck import report as rep
from test_load import frame
from jobcheck import engine

pytestmark = pytest.mark.memory


def test_memory_stays_bounded_across_many_rows(example_checks: None) -> None:
    """Validation holds no per-row state, so peak memory must not scale with rows."""

    df = frame(5000)
    tracemalloc.start()
    for _, row in df.iterrows():
        engine.validate_row(row)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 64 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"


def test_report_memory_stays_bounded_for_a_large_frame(example_checks: None) -> None:
    """validate keeps an object per check per row, so this is the number that
    decides how large a frame the report path can take. Deliberately a smaller frame
    than the validation ceiling above: the point is the ratio, not the absolute size."""

    df = frame(2000)
    tracemalloc.start()
    outcomes = validate(df)
    report = rep.build_report(outcomes, df=df)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(report) == 2400
    assert peak < 128 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"


def test_row_by_row_stays_far_below_the_collected_ceiling(
    example_checks: None,
) -> None:
    """The reason validate_row exists: one row's failures at a time, not the frame's.

    Held to a quarter of the report path's ceiling above, on a frame three times
    the size -- if the per-row path ever starts accumulating, this is where it shows.
    """

    tracemalloc.start()
    failures = 0
    for _, row in frame(6000).iterrows():
        failures += len(validate_row(row))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert failures > 0
    assert peak < 32 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"
