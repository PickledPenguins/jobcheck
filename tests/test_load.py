"""Load: behaviour at volume, with asserted ceilings rather than observations.

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

from conftest import make_check
from jobcheck import build_context, registry as reg
from jobcheck import report as rep
from jobcheck import validate
from jobcheck import engine

pytestmark = pytest.mark.long

ROWS = 20_000


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


def test_twenty_thousand_rows_validate_within_the_time_ceiling(example_checks: None) -> None:
    overrides = reg.load_overrides("examples/rules/error_overrides.yaml")
    df = frame(ROWS)
    start = time.monotonic()
    errors = df.apply(lambda row: engine.validate_row(row, ctx=build_context(row),
                                                   overrides=overrides), axis=1)
    elapsed = time.monotonic() - start
    assert len(errors) == ROWS
    assert elapsed < 60.0, f"{ROWS} rows took {elapsed:.1f}s"


def test_results_are_correct_at_volume_not_just_fast(example_checks: None) -> None:
    df = frame(1000)
    codes = df.apply(lambda row: tuple(r.code for r in engine.validate_row(row)), axis=1)
    counts = codes.value_counts().to_dict()
    assert counts[("AGE_NEGATIVE", "EMAIL_MISSING_AT")] == 200
    assert counts[("AGE_TOO_HIGH", "EMAIL_DOMAIN_INVALID")] == 200
    assert counts[("AGE_PRESENT", "EMAIL_PRESENT")] == 200
    assert counts[()] == 400


def test_building_a_report_over_many_rows_stays_within_the_time_ceiling(
    example_checks: None,
) -> None:
    """Collecting outcomes keeps an object per check per row, so it is the report
    path -- not validate_row -- that has to be watched at volume."""

    df = frame(5000)
    start = time.monotonic()
    outcomes = validate(df)
    report = rep.build_report(outcomes, df=df)
    elapsed = time.monotonic() - start
    assert len(report) == 6000, "one line per failure, not per row"
    assert elapsed < 60.0, f"5000 rows took {elapsed:.1f}s"


def test_topological_order_is_not_recomputed_per_row(fresh_registry: None) -> None:
    calls: list[int] = []
    original = reg._topological_order

    def counting() -> list[reg.Check]:
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
            engine.validate_row(row)
    finally:
        reg._topological_order = original  # type: ignore[assignment]
    assert calls == monkeyed, "the sort ran inside the per-row loop"


def test_many_registered_tests_still_validate_quickly(fresh_registry: None) -> None:
    for i in range(500):
        make_check(f"CODE_{i:04d}", passes=True)
    row = pd.Series({"age": 1})
    start = time.monotonic()
    for _ in range(200):
        engine.validate_row(row)
    elapsed = time.monotonic() - start
    assert elapsed < 30.0, f"500 checks x 200 rows took {elapsed:.1f}s"


def test_many_rules_resolve_within_the_ceiling(fresh_registry: None) -> None:
    import re

    make_check("A_CODE")
    rules = [
        reg.OverrideRule(
            name=f"rule_{i}", action="disable", codes=["A_CODE"],
            criteria=[reg.MatchCriterion("email", "@internal", re.compile("@internal"))],
            match_all=False,
        )
        for i in range(500)
    ]
    row = pd.Series({"email": "qa@internal.test"})
    start = time.monotonic()
    for _ in range(200):
        engine.resolve_enabled_state(row, rules)
    elapsed = time.monotonic() - start
    assert elapsed < 30.0, f"500 rules x 200 rows took {elapsed:.1f}s"


def test_repeated_validation_does_not_leak_registry_state(example_checks: None) -> None:
    row = pd.Series({"age": -1, "email": "nope"})
    before = len(reg.CHECKS)
    for _ in range(1000):
        engine.validate_row(row)
    assert len(reg.CHECKS) == before
    assert [r.code for r in engine.validate_row(row)] == [
        "AGE_NEGATIVE", "DATES_PRESENT", "EMAIL_MISSING_AT"
    ]


def test_rendering_a_large_report_stays_within_the_time_ceiling(example_checks: None) -> None:
    df = frame(2000)
    report = rep.build_report(validate(df), df=df)
    start = time.monotonic()
    text = rep.render_report(report)
    csv = rep.render_report(report, fmt="csv")
    elapsed = time.monotonic() - start
    assert len(text.splitlines()) == len(report) + 2
    assert len(csv.splitlines()) == len(report) + 1
    assert elapsed < 30.0, f"rendering {len(report)} failures took {elapsed:.1f}s"


def test_summarising_a_large_frame_stays_within_the_time_ceiling(example_checks: None) -> None:
    outcomes = validate(frame(2000))
    start = time.monotonic()
    summary = rep.summarise_outcomes(outcomes)
    causes = rep.root_cause_counts(outcomes)
    elapsed = time.monotonic() - start
    assert summary["failed"].sum() + summary["skipped"].sum() > 0
    # The tally counts one (row, cause) pair at a time, and a row failing two
    # chains at the same depth has two root causes: 1,200 failing rows out of
    # 2,000, some of them counted against more than one code.
    assert causes["rows"].sum() >= 1200
    assert elapsed < 15.0, f"summarising 2000 rows took {elapsed:.1f}s"
