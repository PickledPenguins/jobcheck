"""What a validation run produced, as one object rather than four loose values.

Running the tests over a frame yields an outcome per test per row. Everything
downstream -- the failure table, the summary, a single row's explanation --
needs those outcomes *and* the frame they came from, because a report that
identifies rows by frame index is unreadable the moment the frame has been
filtered.

Keeping them together is what :class:`ValidationRun` is for. The alternative,
passing a list of lists alongside the frame it belongs to into every reporting
function, made the caller responsible for keeping the two in step.

This module is the whole-frame entry point: :func:`validate` for a frame whose
outcomes fit in memory, :func:`iter_traces` for one that streams.
:func:`pandas_row_validation.collect_outcomes` remains the lower-level call that
returns the bare lists.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .context import RowContext, build_context
from .registry import OverrideRule, explain_row, root_cause
from .report import build_report, summarise_outcomes
from .results import ERRORED, FAILED, TestOutcome

ContextBuilder = Callable[["pd.Series[Any]"], RowContext | None]

#: How often :func:`validate` calls a progress callback, in rows. A callback per
#: row is its own performance problem on the frames big enough to want one.
DEFAULT_PROGRESS_EVERY = 1000


@dataclass(frozen=True)
class RunStats:
    """What a run did, as numbers a person or a dashboard can read.

    ``failures`` counts the outcomes whose outcome is *failed* only; a test that
    raised is counted in ``errors`` instead, so the two never double-count and a
    broken test is never read as bad data.
    """

    rows: int
    failures: int
    errors: int
    seconds: float

    @property
    def rows_per_second(self) -> float:
        """Throughput, or infinity for a run too fast to time."""

        return float("inf") if self.seconds <= 0 else self.rows / self.seconds


@dataclass
class RowTrace:
    """What every test did on one row, in evaluation order.

    A trace, not a list of failures: it keeps the tests that were disabled or
    blocked by a prerequisite as well as the ones that ran, because "why did
    nothing fire?" is answered by the tests that did not run.

    ``position`` is the row's position in the frame -- 0 for the first row --
    not its index label, so a filtered frame still explains itself.
    """

    position: int
    records: list[TestOutcome] = field(default_factory=list)

    @property
    def failures(self) -> list[TestOutcome]:
        """The failing outcomes, in evaluation order: the first is the root cause."""

        return [record for record in self.records if record.failed]

    @property
    def root_cause(self) -> str | None:
        """The shallowest failure's code, or ``None`` for a row that passed."""

        return root_cause(self.records)

    @property
    def passed(self) -> bool:
        """Whether nothing failed on this row."""

        return not any(record.failed for record in self.records)


@dataclass
class ValidationRun:
    """Every trace for a frame, with the frame and the rules that produced them.

    Built by :func:`validate`. Holding the frame is what lets the reporting
    methods label rows by a key column rather than by index, without the caller
    passing the frame back in.
    """

    df: pd.DataFrame
    traces: list[RowTrace]
    overrides: list[OverrideRule] = field(default_factory=list)
    stats: RunStats | None = None

    @classmethod
    def from_records(
        cls,
        df: pd.DataFrame,
        records: list[list[TestOutcome]],
        overrides: list[OverrideRule] | None = None,
        stats: RunStats | None = None,
    ) -> "ValidationRun":
        """Build a run from outcomes collected elsewhere.

        :func:`pandas_row_validation.collect_outcomes` produces the outcomes a
        frame's rows yielded without producing the run that owns them, and every
        reporting view here takes a run. This is the join: positions come from
        the order of *records*, which is frame order.

        Raises ``ValueError`` when there is not exactly one list of outcomes per
        row, since a silent mismatch would label every later row wrongly.
        """

        if len(records) != len(df):
            raise ValueError(
                f"{len(records)} row(s) of outcomes for a frame of {len(df)} row(s): "
                "from_records() needs one list per row, in frame order."
            )
        traces = [RowTrace(position=position, records=row_records)
                  for position, row_records in enumerate(records)]
        return cls(df=df, traces=traces, overrides=list(overrides or []), stats=stats)

    def __len__(self) -> int:
        """The number of rows validated."""

        return len(self.traces)

    def __iter__(self) -> Iterator[RowTrace]:
        """Iterate the traces, in frame order."""

        return iter(self.traces)

    @property
    def records(self) -> list[list[TestOutcome]]:
        """The raw outcomes, one list per row, for a caller that wants them."""

        return [trace.records for trace in self.traces]

    @property
    def errors(self) -> int:
        """How many tests raised across the whole run.

        Taken from :attr:`stats` when the run was timed, and counted otherwise,
        so a run assembled by :meth:`from_records` still answers the question.
        """

        if self.stats is not None:
            return self.stats.errors
        return sum(record.outcome == ERRORED
                   for trace in self.traces for record in trace.records)

    @property
    def failed_rows(self) -> list[RowTrace]:
        """Traces for the rows that failed something."""

        return [trace for trace in self.traces if not trace.passed]

    @property
    def root_causes(self) -> list[str | None]:
        """Each row's root cause, in frame order; ``None`` where it passed."""

        return [trace.root_cause for trace in self.traces]

    def report(
        self,
        key_column: str | list[str] | None = None,
        data_columns: list[str] | None = None,
        include_skipped: bool = False,
        include_passed: bool = False,
    ) -> pd.DataFrame:
        """The long-format failure table. See :func:`report.build_report`."""

        return build_report(
            self.records,
            df=self.df,
            key_column=key_column,
            data_columns=data_columns,
            include_skipped=include_skipped,
            include_passed=include_passed,
        )

    def summary(self) -> pd.DataFrame:
        """Per-test counts, worst first. See :func:`report.summarise_outcomes`."""

        return summarise_outcomes(self.records)

    def explain(self, position: int) -> RowTrace:
        """One row's trace, by position in the frame.

        Raises ``IndexError`` naming the frame's size rather than letting a
        negative index quietly wrap round to the wrong row.
        """

        if not 0 <= position < len(self.traces):
            raise IndexError(
                f"No row at position {position}: the frame has {len(self.traces)} row(s), "
                f"so positions run 0..{max(len(self.traces) - 1, 0)}."
            )
        return self.traces[position]


def iter_traces(
    df: pd.DataFrame,
    overrides: list[OverrideRule] | None = None,
    context_builder: ContextBuilder = build_context,
    on_error: str = "record",
    progress: Callable[[int, int], None] | None = None,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
) -> Iterator[RowTrace]:
    """Yield one :class:`RowTrace` at a time, holding no more than one at once.

    The streaming half of :func:`validate`, for a frame whose outcomes will not
    fit in memory: a run keeps one outcome per test per row, so two hundred
    tests over a million rows is two hundred million objects. Consume these one
    at a time -- writing failures out as they appear -- and peak memory becomes
    proportional to the *failures* rather than to tests times rows.
    """

    if progress_every < 1:
        raise ValueError(f"progress_every must be at least 1, got {progress_every}.")

    total = len(df)
    for position, (_, row) in enumerate(df.iterrows()):
        yield RowTrace(
            position=position,
            records=explain_row(row, ctx=context_builder(row), overrides=overrides,
                                on_error=on_error),
        )
        done = position + 1
        if progress is not None and (done % progress_every == 0 or done == total):
            progress(done, total)
    if progress is not None and total == 0:
        progress(0, 0)


def validate(
    df: pd.DataFrame,
    overrides: list[OverrideRule] | None = None,
    context_builder: ContextBuilder = build_context,
    on_error: str = "record",
    progress: Callable[[int, int], None] | None = None,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
) -> ValidationRun:
    """Run every test against every row of *df*.

    The entry point for validating a frame. Keeps the tests that did not run as
    well as the ones that did, because that is what the explanation and summary
    views are built from.

    Two ways to spend less memory than this does. For a gate that only needs to
    know which rows are bad, :func:`pandas_row_validation.validate_row` per row
    returns the failures and allocates nothing for the rest. For a report over a
    frame too large to hold every outcome, stream :func:`iter_traces`.

    ``on_error`` is passed through to :func:`pandas_row_validation.explain_row`.

    *progress*, when given, is called as ``progress(done, total)`` every
    *progress_every* rows and once at the end. Called every N rows rather than
    every row because a callback per row is its own performance problem on the
    frames big enough to want one.
    """

    started = time.perf_counter()
    traces: list[RowTrace] = []
    failures = 0
    errors = 0
    for trace in iter_traces(df, overrides, context_builder, on_error,
                             progress, progress_every):
        traces.append(trace)
        for record in trace.records:
            if record.outcome == FAILED:
                failures += 1
            elif record.outcome == ERRORED:
                errors += 1
    elapsed = time.perf_counter() - started
    return ValidationRun(
        df=df,
        traces=traces,
        overrides=list(overrides or []),
        stats=RunStats(rows=len(traces), failures=failures, errors=errors, seconds=elapsed),
    )
