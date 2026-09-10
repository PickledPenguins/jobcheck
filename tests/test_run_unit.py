"""Unit checks: the whole-frame entry point and the run object it returns.

``validate`` is the call a pipeline makes when it has a DataFrame rather than a
row, so what is pinned here is the trace shape (position, records, failures,
root cause), the counts, and the reporting views the run exposes.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import (
    ERRORED,
    RowTrace,
    RunStats,
    ValidationRun,
    collect_outcomes,
    iter_traces,
    validate,
)

pytestmark = pytest.mark.fast

FRAME = pd.DataFrame([{"value": 1}, {"value": 2}, {"value": 3}])


def fail_on_even() -> None:
    """One registered check that fails the middle row of FRAME and no other."""

    from jobcheck import PASS, Status, CheckResult
    from jobcheck import registry as reg

    @reg.register_check(code="EVEN", message="value is even")
    def check(row: "pd.Series[Any]") -> CheckResult:
        return PASS if row["value"] % 2 else CheckResult(Status.INVALID, {"value": row["value"]})


def test_validate_returns_one_trace_per_row(fresh_registry: None) -> None:
    make_check("PASSES")
    run = validate(FRAME)
    assert len(run) == 3


def test_traces_are_in_frame_order_with_positions(fresh_registry: None) -> None:
    make_check("PASSES")
    assert [trace.position for trace in validate(FRAME)] == [0, 1, 2]


def test_positions_are_frame_positions_not_index_labels(fresh_registry: None) -> None:
    make_check("PASSES")
    frame = FRAME.set_index(pd.Index([10, 20, 30]))
    assert [trace.position for trace in validate(frame)] == [0, 1, 2]


def test_a_row_that_passed_has_no_failures_and_no_root_cause(fresh_registry: None) -> None:
    make_check("PASSES")
    trace = validate(FRAME).explain(0)
    assert (trace.passed, trace.failures, trace.root_cause) == (True, [], None)


def test_a_failing_row_reports_its_root_cause(fresh_registry: None) -> None:
    make_check("FUNDAMENTAL", passes=False)
    make_check("DEPENDENT", passes=False, depends_on=["FUNDAMENTAL"])
    trace = validate(FRAME).explain(0)
    assert trace.root_cause == "FUNDAMENTAL"


def test_failures_keep_evaluation_order(fresh_registry: None) -> None:
    make_check("FIRST", passes=False)
    make_check("SECOND", passes=False)
    trace = validate(FRAME).explain(0)
    assert [failure.code for failure in trace.failures] == ["FIRST", "SECOND"]


def test_records_keep_the_tests_that_did_not_run(fresh_registry: None) -> None:
    make_check("FUNDAMENTAL", passes=False)
    make_check("BLOCKED", depends_on=["FUNDAMENTAL"])
    trace = validate(FRAME).explain(0)
    assert [record.code for record in trace.records] == ["FUNDAMENTAL", "BLOCKED"]


def test_stats_count_rows_failures_and_errors_separately(fresh_registry: None) -> None:
    make_check("FAILS", passes=False)
    make_check("RAISES", raises=RuntimeError("boom"))
    stats = validate(FRAME).stats
    assert stats is not None
    assert (stats.rows, stats.failures, stats.errors) == (3, 3, 3)


def test_errors_is_the_count_of_tests_that_raised(fresh_registry: None) -> None:
    make_check("RAISES", raises=RuntimeError("boom"))
    assert validate(FRAME).errors == 3


def test_errors_is_counted_when_a_run_was_not_timed(fresh_registry: None) -> None:
    make_check("RAISES", raises=RuntimeError("boom"))
    run = ValidationRun.from_records(FRAME, collect_outcomes(FRAME))
    assert run.errors == 3
    assert all(record.outcome == ERRORED
               for trace in run for record in trace.records)


def test_root_causes_are_none_where_the_row_passed(fresh_registry: None) -> None:
    fail_on_even()
    assert validate(FRAME).root_causes == [None, "EVEN", None]


def test_failed_rows_are_only_the_rows_that_failed_something(fresh_registry: None) -> None:
    fail_on_even()
    run = validate(FRAME)
    assert [trace.position for trace in run.failed_rows] == [1]


def test_records_property_matches_collect_outcomes(fresh_registry: None) -> None:
    fail_on_even()
    from_run = validate(FRAME).records
    assert [[r.code for r in row] for row in from_run] == [["EVEN"], ["EVEN"], ["EVEN"]]


def test_report_is_the_long_format_failure_table(fresh_registry: None) -> None:
    fail_on_even()
    report = validate(FRAME).report(key_column="value")
    assert list(report["code"]) == ["EVEN"]
    assert list(report["row"]) == ["2"]


def test_summary_counts_each_test(fresh_registry: None) -> None:
    fail_on_even()
    summary = validate(FRAME).summary()
    assert list(summary["code"]) == ["EVEN"]
    assert list(summary["failed"]) == [1]


def test_explain_returns_the_trace_at_that_position(fresh_registry: None) -> None:
    fail_on_even()
    assert validate(FRAME).explain(1).root_cause == "EVEN"


def test_explain_rejects_a_position_past_the_end(fresh_registry: None) -> None:
    fail_on_even()
    with pytest.raises(IndexError, match="the frame has 3 row"):
        validate(FRAME).explain(3)


def test_explain_rejects_a_negative_position_rather_than_wrapping(fresh_registry: None) -> None:
    fail_on_even()
    with pytest.raises(IndexError, match="positions run 0..2"):
        validate(FRAME).explain(-1)


def test_overrides_are_kept_on_the_run(fresh_registry: None) -> None:
    make_check("PASSES")
    assert validate(FRAME, overrides=[]).overrides == []


def test_an_empty_frame_produces_an_empty_run(fresh_registry: None) -> None:
    make_check("PASSES")
    run = validate(pd.DataFrame(columns=["value"]))
    assert (len(run), run.root_causes, run.failed_rows) == (0, [], [])


def test_from_records_rejects_a_length_mismatch(fresh_registry: None) -> None:
    make_check("PASSES")
    with pytest.raises(ValueError, match="from_records"):
        ValidationRun.from_records(FRAME, collect_outcomes(FRAME)[:2])


def test_from_records_numbers_rows_in_frame_order(fresh_registry: None) -> None:
    fail_on_even()
    run = ValidationRun.from_records(FRAME, collect_outcomes(FRAME))
    assert [trace.position for trace in run.failed_rows] == [1]


def test_from_records_copies_the_overrides_list(fresh_registry: None) -> None:
    make_check("PASSES")
    overrides: list[Any] = []
    run = ValidationRun.from_records(FRAME, collect_outcomes(FRAME), overrides=overrides)
    overrides.append("invented")
    assert run.overrides == []


def test_iter_traces_yields_the_same_traces_as_validate(fresh_registry: None) -> None:
    fail_on_even()
    streamed = [(trace.position, trace.root_cause) for trace in iter_traces(FRAME)]
    assert streamed == [(0, None), (1, "EVEN"), (2, None)]


def test_iter_traces_reports_progress_every_n_rows_and_at_the_end(fresh_registry: None) -> None:
    make_check("PASSES")
    seen: list[tuple[int, int]] = []
    list(iter_traces(FRAME, progress=lambda done, total: seen.append((done, total)),
                     progress_every=2))
    assert seen == [(2, 3), (3, 3)]


def test_progress_fires_once_for_an_empty_frame(fresh_registry: None) -> None:
    make_check("PASSES")
    seen: list[tuple[int, int]] = []
    list(iter_traces(pd.DataFrame(columns=["value"]),
                     progress=lambda done, total: seen.append((done, total))))
    assert seen == [(0, 0)]


def test_progress_every_below_one_is_rejected(fresh_registry: None) -> None:
    make_check("PASSES")
    with pytest.raises(ValueError, match="progress_every must be at least 1"):
        list(iter_traces(FRAME, progress_every=0))


def test_rows_per_second_is_infinite_for_an_untimed_run() -> None:
    assert RunStats(rows=1, failures=0, errors=0, seconds=0.0).rows_per_second == float("inf")


def test_rows_per_second_divides_rows_by_seconds() -> None:
    assert RunStats(rows=10, failures=0, errors=0, seconds=2.0).rows_per_second == 5.0


def test_a_trace_defaults_to_no_records() -> None:
    assert RowTrace(position=0).records == []


# --- what the arguments actually do -----------------------------------------
#
# Each of these was written against a surviving mutant: a change to run.py that
# no check noticed. Dropping `on_error` on the way to explain_row, dropping
# `progress`, and recording `seconds=None` all passed the suite before these.


def test_on_error_raise_propagates_a_tests_exception(fresh_registry: None) -> None:
    make_check("RAISES", raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        validate(FRAME, on_error="raise")


def test_on_error_defaults_to_recording_the_exception(fresh_registry: None) -> None:
    make_check("RAISES", raises=RuntimeError("boom"))
    trace = validate(FRAME).explain(0)
    assert [record.outcome for record in trace.records] == [ERRORED]
    assert "RuntimeError" in trace.records[0].detail


def test_iter_traces_passes_on_error_through(fresh_registry: None) -> None:
    make_check("RAISES", raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        list(iter_traces(FRAME, on_error="raise"))


def test_validate_reports_progress_through_to_the_callback(fresh_registry: None) -> None:
    make_check("PASSES")
    seen: list[tuple[int, int]] = []
    validate(FRAME, progress=lambda done, total: seen.append((done, total)), progress_every=1)
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_validate_passes_progress_every_through(fresh_registry: None) -> None:
    make_check("PASSES")
    seen: list[tuple[int, int]] = []
    validate(FRAME, progress=lambda done, total: seen.append((done, total)), progress_every=2)
    assert seen == [(2, 3), (3, 3)]


def test_validate_rejects_a_progress_interval_below_one(fresh_registry: None) -> None:
    make_check("PASSES")
    with pytest.raises(ValueError, match="progress_every must be at least 1"):
        validate(FRAME, progress_every=0)


def test_stats_record_the_time_the_run_took(fresh_registry: None) -> None:
    make_check("PASSES")
    stats = validate(FRAME).stats
    assert stats is not None
    assert isinstance(stats.seconds, float)
    assert stats.seconds >= 0.0
    assert stats.rows_per_second > 0.0


def test_the_overrides_given_are_the_ones_the_run_carries(fresh_registry: None) -> None:
    make_check("SWITCHABLE", passes=False)
    from jobcheck import MatchCriterion, OverrideRule

    rule = OverrideRule(name="off", action="disable", codes=["SWITCHABLE"],
                        criteria=[MatchCriterion(column="value", pattern="^2$",
                                                 regex=re.compile("^2$"))],
                        match_all=False, source_file="<check>")
    run = validate(FRAME, overrides=[rule])
    assert [override.name for override in run.overrides] == ["off"]
    # And they were applied, not merely stored.
    assert run.explain(1).failures == []
    assert [failure.code for failure in run.explain(0).failures] == ["SWITCHABLE"]


def test_the_run_copies_the_overrides_list_it_was_given(fresh_registry: None) -> None:
    make_check("PASSES")
    given: list[Any] = []
    run = validate(FRAME, overrides=given)
    given.append("invented")
    assert run.overrides == []


def test_the_recorded_duration_is_the_time_the_run_actually_took(
    fresh_registry: None,
) -> None:
    """Bounded above as well as below.

    Written against a surviving mutant that computed ``perf_counter() + started``
    rather than ``- started``: the result is still a positive float, so an
    assertion that it is non-negative says nothing.
    """

    import time

    make_check("PASSES")
    before = time.perf_counter()
    run = validate(FRAME)
    wall_clock = time.perf_counter() - before

    stats = run.stats
    assert stats is not None
    assert 0.0 <= stats.seconds <= wall_clock + 0.01
    assert stats.rows_per_second >= len(FRAME) / (wall_clock + 0.01)
