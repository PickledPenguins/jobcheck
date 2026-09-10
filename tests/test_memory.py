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

from jobcheck import iter_traces, registry as reg
from jobcheck import report as rep
from test_load import frame
from jobcheck import engine

pytestmark = pytest.mark.memory


def test_memory_stays_bounded_across_many_rows(example_suites: None) -> None:
    """Validation holds no per-row state, so peak memory must not scale with rows."""

    df = frame(5000)
    tracemalloc.start()
    for _, row in df.iterrows():
        engine.validate_row(row)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 64 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"


def test_report_memory_stays_bounded_for_a_large_frame(example_suites: None) -> None:
    """collect_outcomes keeps an object per check per row, so this is the number that
    decides how large a frame the report path can take. Deliberately a smaller frame
    than the validation ceiling above: the point is the ratio, not the absolute size."""

    df = frame(2000)
    tracemalloc.start()
    outcomes = rep.collect_outcomes(df)
    report = rep.build_report(outcomes, df=df)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(report) == 2400
    assert peak < 128 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"


def test_streaming_a_large_frame_stays_far_below_the_collected_ceiling(
    example_suites: None,
) -> None:
    """The reason iter_traces exists: one row's outcomes at a time, not the frame's.

    Held to a quarter of the report path's ceiling above, on a frame three times
    the size -- if streaming ever starts accumulating, this is where it shows.
    """

    tracemalloc.start()
    failures = 0
    for trace in iter_traces(frame(6000)):
        failures += len(trace.failures)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert failures > 0
    assert peak < 32 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"
