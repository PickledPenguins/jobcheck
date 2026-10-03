"""Load: behavior at volume, with asserted ceilings rather than observations.

Thresholds are deliberately loose -- they catch an order-of-magnitude
regression (an accidental per-row topological sort, a per-row file read), not
small variation between machines. For a gate that notices a *small* regression,
see ``tests/test_perf.py``, which compares against this machine's own baseline.

Peak-memory ceilings live in ``tests/test_memory.py``: tracemalloc roughly
triples the time it measures, so the two cannot share a run without one of them
lying.
"""

from __future__ import annotations

import time

import pandas as pd
import pytest

from conftest import enabled_only, failures, make_check
from jobcheck import registry as reg
from jobcheck import views
from jobcheck import validate
from jobcheck import engine
from jobcheck.rules import _MatchCriterion

pytestmark = pytest.mark.long




def frame(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age": [30, -1, 200, 41.5, None] * (rows // 5),
            "email": ["a@b.com", "nope", "a@nodot", "qa@internal.test", None] * (rows // 5),
            "start_date": ["2024-01-01"] * rows,
            "end_date": ["2024-02-01"] * rows,
            "source_system": ["LEGACY_A", "MODERN"] * (rows // 2),
            "record_type": ["BATCH", "STREAM"] * (rows // 2),
        }
    )


def test_validating_reporting_and_summarizing_many_rows_stays_within_the_ceiling(
    example_checks: None,
) -> None:
    """Collecting outcomes keeps an object per check per row, so it is the report
    path that has to be watched at volume. The one absolute ceiling in the long
    suite: scaling's ratios catch growth, and the perf gate a small slowdown."""

    df = frame(5000)
    start = time.monotonic()
    outcomes = validate(df)
    report = views.build_report(outcomes, df=df)
    summary = views.summarize_outcomes(outcomes)
    elapsed = time.monotonic() - start
    assert len(report) == 6000, "one line per failure, not per row"
    assert summary["failed"].sum() == 6000
    assert elapsed < 60.0, f"5000 rows took {elapsed:.1f}s"


def test_topological_order_is_not_recomputed_per_row(fresh_registry: None) -> None:
    calls: list[int] = []
    original = reg._topological_order

    def counting() -> list[reg._Check]:
        calls.append(1)
        return original()

    make_check("ROOT")
    make_check("LEAF", depends_on=["ROOT"])
    reg._get_topo_order()
    monkeyed = calls.copy()
    reg._topological_order = counting  # type: ignore[assignment]
    try:
        row = pd.Series({"age": 1})
        for _ in range(500):
            failures(row)
    finally:
        reg._topological_order = original  # type: ignore[assignment]
    assert calls == monkeyed, "the sort ran inside the per-row loop"





def test_many_rules_resolve_within_the_ceiling(fresh_registry: None) -> None:
    import re

    make_check("A_CODE")
    rules = [
        reg.Rule(
            name=f"rule_{i}", action="disable", codes=["A_CODE"],
            criteria=[_MatchCriterion("email", "@internal", re.compile("@internal"))],
            match_all=False, message="why the rule exists",
        )
        for i in range(500)
    ]
    row = pd.Series({"email": "qa@internal.test"})
    start = time.monotonic()
    for _ in range(200):
        enabled_only(engine._resolve_enabled_state(row, rules))
    elapsed = time.monotonic() - start
    assert elapsed < 30.0, f"500 rules x 200 rows took {elapsed:.1f}s"

