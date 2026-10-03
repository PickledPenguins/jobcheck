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

pytestmark = pytest.mark.memory


def test_report_memory_stays_bounded_for_a_large_frame(example_checks: None) -> None:
    """validate keeps an object per check per row, so this is the number that
    decides how large a frame the report path can take. That the per-row path
    holds nothing between rows is `test_scaling.py`'s memory test."""

    df = frame(2000)
    tracemalloc.start()
    outcomes = validate(df)
    report = views.build_report(outcomes, df=df)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(report) == 2400
    assert peak < 128 * 1024 * 1024, f"peak {peak / 1e6:.0f} MB"
