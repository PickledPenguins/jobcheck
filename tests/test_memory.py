"""Memory ceilings, in their own invocation.

``tracemalloc`` roughly triples the time of the code it watches, so these cannot
share a run with the timing gates without making those meaningless. They are
marked ``memory`` and run by ``./tests/run-tests.sh memory``.

The ceilings are absolute rather than baseline-relative, because peak memory is
a property of the program rather than of the machine: the same frame allocates
the same objects everywhere, give or take the interpreter's own overhead.
"""

from __future__ import annotations

import tracemalloc

import pytest

from jobcheck import validate
from jobcheck import views
from test_load import frame
from jobcheck import engine

pytestmark = pytest.mark.memory


def test_memory_stays_bounded_across_many_rows(example_checks: None) -> None:
    """Validation holds no per-row state, so peak memory must not scale with rows."""

    df = frame(5000)
    tracemalloc.start()
    for _, row in df.iterrows():
        engine._explain(row)
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
    report = views.build_report(outcomes, df=df)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(report) == 2400
    assert peak < 128 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"
