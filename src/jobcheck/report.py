"""Turning outcomes into a report: the failure table, the summary, and rendering.

Everything a caller needs to produce and save a report lives here -- building
the long-format failure table from what :func:`jobcheck.validate` returned,
rendering it as text or CSV, and writing it to a file. There is no command
line: a pipeline calls these functions and decides where the output goes.

The report is **long format**: one row per failed check per data row. That is the
diagnostic unit, it is the only shape that survives being written as CSV, and it
sorts and filters cleanly downstream.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import pandas as pd

from .engine import root_causes
from .results import DISABLED, ERRORED, FAILED, PASSED, SKIPPED, CheckOutcome, render_status
from .tables import _check_extra_columns, format_table

REPORT_COLUMNS = ["row", "code", "status", "layer", "outcome", "message", "detail", "comments",
                  "is_root_cause"]

# Which outcomes reach a report or an explanation, worst-first. Every level
# contains the one before it, so the choice is how far down to go rather than a
# set of independent switches.
INCLUDE_LEVELS: dict[str, set[str]] = {
    "failures": {FAILED, ERRORED},
    "blocked": {FAILED, ERRORED, SKIPPED, DISABLED},
    "all": {FAILED, ERRORED, SKIPPED, DISABLED, PASSED},
}

# A spreadsheet treats a cell starting with one of these as a formula, so a value
# taken from the data and written into a CSV can execute when someone opens the
# report. Escaping happens on the way out, not on the way in, so the outcomes and
# the table view keep the value the check actually saw.
FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")

KEY_SEPARATOR = "|"


def _included(include: str) -> set[str]:
    """The outcomes an ``include`` level covers, or a ValueError naming the levels."""

    if include not in INCLUDE_LEVELS:
        raise ValueError(
            f"include must be one of {', '.join(INCLUDE_LEVELS)}, got {include!r}.")
    return INCLUDE_LEVELS[include]


def render_comments(comments: Mapping[str, Any]) -> str:
    """Render a check's comments as ``key=value; key=value``, sorted by key.

    Sorted so the same failure renders identically every run, which is what lets
    reports be diffed and byte-compared in checks.
    """

    return "; ".join(f"{key}={comments[key]}" for key in sorted(comments))


def _format_cell(value: Any, missing: str = "") -> str:
    """Render a value copied from the data into a report column.

    Whole floats lose their ``.0`` -- an integer id column that pandas widened to
    float because one row is blank should still read as ``104``, not ``104.0``.
    *missing* is what a null becomes: empty for a data column, where that is what
    a person expects, and ``<no key>`` for the row key, where a missing value is
    worth naming.
    """

    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return missing
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _row_labels(df: pd.DataFrame, key_column: str | None) -> list[str]:
    """One label per row: the key column if given, else the frame's index.

    One column, not several: two columns joined into one label are ambiguous
    whenever a value carries the separator, and a caller with a composite key
    can build the column it wants to be identified by.
    """

    if key_column is None:
        return [_format_cell(label, missing="<no key>") for label in df.index]
    if key_column not in df.columns:
        raise ValueError(
            f"key_column {key_column!r} is not in the data. Available columns: "
            f"{', '.join(str(c) for c in df.columns)}."
        )
    return [_format_cell(value, missing="<no key>") for value in df[key_column]]


def build_report(
    frame_outcomes: list[list[CheckOutcome]],
    df: pd.DataFrame,
    key_column: str | None = None,
    extra_columns: list[str] | None = None,
    include: str = "failures",
) -> pd.DataFrame:
    """Build the long-format report: one row per failure.

    Columns are ``row``, ``code``, ``status`` (``INVALID (3)``), ``layer``,
    ``outcome``, ``message``, ``detail``, ``comments``, ``is_root_cause``. Lines
    keep evaluation order within each data row; the root cause is the line (or
    lines) flagged by ``is_root_cause``, which is not necessarily the first --
    an independent chain registered earlier can be printed above a shallower
    failure. ``is_root_cause`` is True for **every** failure at the shallowest
    failing layer, since two failures at the same depth are two root causes.

    ``message`` is what the check says on failure, ``detail`` why a check did not
    evaluate the row (the rule that disabled it, the prerequisites that blocked
    it, the exception it raised) and ``comments`` the evidence it returned. Each
    says one thing, so a column heading can be trusted.

    ``key_column`` names the column that identifies a data row, which is what
    makes a report readable once the frame has been filtered; without it the
    frame's index is used.

    ``extra_columns`` copies further columns from the frame into the report, in
    the order given, immediately after ``row``. They carry the context a reader
    needs to judge a failure without going back to the source file -- the source
    system, the batch, the field the check was reading. A name that is not in the
    frame, is in it more than once, is asked for twice, or collides with one of
    the report's own columns is refused rather than quietly dropped.

    ``include`` says how far down to go: ``"failures"`` is what failed or
    errored, ``"blocked"`` adds the checks a failure or a rule stopped -- useful
    when the question is "why did nothing fire?" -- and ``"all"`` adds the passes,
    which turns the report into a full audit trail.
    """

    if len(df) != len(frame_outcomes):
        raise ValueError(
            f"outcomes cover {len(frame_outcomes)} row(s) but the frame has {len(df)}: "
            "pass the same frame the outcomes were collected from."
        )
    wanted = _included(include)
    extra_columns = list(extra_columns or [])
    labels = list(df.columns)
    _check_extra_columns(
        extra_columns,
        [str(c) for c in df.columns if labels.count(c) == 1 and c not in REPORT_COLUMNS],
        "the report",
    )

    row_labels = _row_labels(df, key_column)
    extra = (
        [{column: _format_cell(value) for column, value in zip(extra_columns, values)}
         for values in df[extra_columns].itertuples(index=False, name=None)]
        if extra_columns
        else [{} for _ in frame_outcomes]
    )

    rows: list[dict[str, Any]] = []
    for label, row_outcomes, context in zip(row_labels, frame_outcomes, extra):
        causes = set(root_causes(row_outcomes))
        for outcome in row_outcomes:
            if outcome.outcome not in wanted:
                continue
            rows.append(
                {
                    "row": label,
                    **context,
                    "code": outcome.code,
                    "status": render_status(outcome.status),
                    "layer": outcome.layer,
                    "outcome": outcome.outcome,
                    "message": outcome.message,
                    "detail": outcome.detail,
                    "comments": render_comments(outcome.comments),
                    "is_root_cause": outcome.code in causes,
                }
            )
    columns = ["row", *extra_columns, *REPORT_COLUMNS[1:]]
    return pd.DataFrame(rows, columns=columns)


def _looks_numeric(text: str) -> bool:
    """Whether a string is just a number, so a leading ``-`` is a minus sign."""

    try:
        float(text)
    except ValueError:
        return False
    return True


def escape_for_spreadsheet(value: Any) -> Any:
    """Prefix a cell a spreadsheet would run as a formula with an apostrophe.

    Comments carry values taken from the data, and a report is meant to be opened
    in a spreadsheet, so a field such as ``=cmd|'/c calc'!A1`` arriving in a row
    would execute on open. The apostrophe is the standard neutralizer: the cell
    displays as text. A negative number keeps its minus sign, since that is not
    a formula.
    """

    if not isinstance(value, str) or not value:
        return value
    if value[0] in FORMULA_PREFIXES or (value[0] == "-" and not _looks_numeric(value)):
        return "'" + value
    return value


def render_report(report: pd.DataFrame, fmt: str = "table", wrap_width: int = 48) -> str:
    """Render a report as bordered text or as CSV.

    ``fmt="table"`` wraps ``message``, ``detail`` and ``comments`` at *wrap_width*
    characters so a long explanation stays inside its column; ``fmt="csv"`` emits
    the same columns unwrapped, for a spreadsheet or another tool.

    CSV cells that a spreadsheet would run as a formula are neutralized with a
    leading apostrophe -- see :func:`escape_for_spreadsheet` -- because comments
    carry values that came from the data. That is not optional: a report is
    written to be opened by a person.
    """

    if fmt == "table":
        return format_table(
            report,
            wrap_columns={"message": wrap_width, "detail": wrap_width,
                          "comments": wrap_width},
        )
    if fmt == "csv":
        return report.map(escape_for_spreadsheet).to_csv(index=False)
    raise ValueError(f"fmt must be 'table' or 'csv', got {fmt!r}.")


def write_report(report: pd.DataFrame, path: str, fmt: str = "csv") -> None:
    """Write a rendered report to a file, creating or replacing it."""

    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(render_report(report, fmt=fmt))


def print_report(report: pd.DataFrame, fmt: str = "table", wrap_width: int = 48) -> None:
    """Print a rendered report, or a plain line when nothing failed."""

    if report.empty:
        print("No failures.")
        return
    print(render_report(report, fmt=fmt, wrap_width=wrap_width))


def row_explanation(row_outcomes: list[CheckOutcome], include: str = "all") -> pd.DataFrame:
    """One row per check, in evaluation order: what it did and why.

    ``include`` is the same three levels the report takes: ``"all"`` is every
    check, ``"blocked"`` drops the ones that simply passed -- usually what you
    want when hunting one bad row -- and ``"failures"`` keeps only what failed or
    errored.
    """

    wanted = _included(include)
    kept = [outcome for outcome in row_outcomes if outcome.outcome in wanted]
    return pd.DataFrame(
        [
            {
                "layer": outcome.layer,
                "code": outcome.code,
                "outcome": outcome.outcome,
                "status": render_status(outcome.status),
                "detail": outcome.detail
                or render_comments(outcome.comments)
                or outcome.message
                or "-",
            }
            for outcome in kept
        ],
        columns=["layer", "code", "outcome", "status", "detail"],
    )


def print_row_explanation(row_outcomes: list[CheckOutcome], include: str = "all") -> pd.DataFrame:
    """Print what every check did on one row, then the row's root cause(s).

    Reading order is evaluation order, and every ``skipped`` line names the
    prerequisite that blocked it. The root cause is not always the first failing
    line: two chains that do not touch can both fail, and the deeper one may be
    evaluated first, so it is named explicitly at the end. Where two failures sit
    at the same depth, both are named.
    """

    table = row_explanation(row_outcomes, include=include)
    print(format_table(table, wrap_columns={"detail": 60}))
    causes = root_causes(row_outcomes)
    label = "root cause" if len(causes) == 1 else "root causes"
    print(f"{label}: {', '.join(causes)}" if causes else "root cause: none - the row passed")
    return table


def summarize_outcomes(frame_outcomes: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """Count what happened to each check across many rows.

    ``skipped`` is the column that matters when tuning layered checks: a high
    count means a fundamental check is failing often and hiding everything below
    it. ``errored`` is kept separate from ``failed`` so a broken check can never
    be mistaken for bad data.
    """

    counts: dict[str, dict[str, int]] = {}
    layers: dict[str, int] = {}
    for row_outcomes in frame_outcomes:
        for outcome in row_outcomes:
            entry = counts.setdefault(
                outcome.code, {PASSED: 0, FAILED: 0, ERRORED: 0, SKIPPED: 0, DISABLED: 0}
            )
            entry[outcome.outcome] += 1
            layers[outcome.code] = outcome.layer

    columns = ["code", "layer", "failed", "errored", "skipped", "disabled", "passed"]
    rows = [
        {
            "code": code,
            "layer": layers[code],
            "failed": entry[FAILED],
            "errored": entry[ERRORED],
            "skipped": entry[SKIPPED],
            "disabled": entry[DISABLED],
            "passed": entry[PASSED],
        }
        for code, entry in counts.items()
    ]
    if not rows:
        return pd.DataFrame(rows, columns=columns)
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["failed", "errored", "skipped", "code"], ascending=[False, False, False, True])
        .reset_index(drop=True)
    )


def root_cause_counts(frame_outcomes: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """How many rows bottomed out at each code, worst first.

    A row failing two chains at the same depth counts once against each: the
    question this answers is "how many rows would this code explain", and both
    codes explain that row.
    """

    causes: dict[str, int] = {}
    for row_outcomes in frame_outcomes:
        for cause in root_causes(row_outcomes):
            causes[cause] = causes.get(cause, 0) + 1
    ranked = sorted(causes.items(), key=lambda item: (-item[1], item[0]))
    return pd.DataFrame(
        [{"root_cause": code, "rows": count} for code, count in ranked],
        columns=["root_cause", "rows"],
    )


def print_summary(frame_outcomes: list[list[CheckOutcome]]) -> pd.DataFrame:
    """Print the per-check summary, worst first, and the root-cause tally."""

    table = summarize_outcomes(frame_outcomes)
    if table.empty:
        print("No checks ran.")
        return table
    print(format_table(table))

    causes = root_cause_counts(frame_outcomes)
    print()
    if causes.empty:
        print("Root causes: none - every row passed.")
        return table
    print("Root cause of each failing row:")
    print(format_table(causes))
    return table
