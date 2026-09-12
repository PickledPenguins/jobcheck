"""Turning outcomes into a report: the failure table, the summary, and rendering.

The report is **long format** -- one line per failed check per data row -- which
is the diagnostic unit, survives being written as CSV, and sorts and filters
cleanly downstream. There is no command line; a pipeline decides where output
goes.
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


def _included(include: str) -> set[str]:
    """The outcomes an ``include`` level covers, or a ValueError naming the levels."""

    if include not in INCLUDE_LEVELS:
        raise ValueError(
            f"include must be one of {', '.join(INCLUDE_LEVELS)}, got {include!r}.")
    return INCLUDE_LEVELS[include]


def render_comments(comments: Mapping[str, Any]) -> str:
    """Render a check's comments as `key=value; key=value`, sorted by key so the
    same failure renders identically every run and reports can be diffed."""

    return "; ".join(f"{key}={comments[key]}" for key in sorted(comments))


def _format_cell(value: Any, missing: str = "") -> str:
    """Render a value from the data into a report column: whole floats lose their
    `.0`, and a null becomes *missing* -- empty, or `<no key>` for a row key."""

    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return missing
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _row_labels(df: pd.DataFrame, key_column: str | None) -> list[str]:
    """One label per row: the key column if given, else the frame's index.

    One column, not several -- joined labels are ambiguous as soon as a value
    carries the separator, so a composite key is a column the caller builds.
    """

    if key_column is None:
        return [_format_cell(label, missing="<no key>") for label in df.index]
    if key_column not in df.columns:
        raise ValueError(
            f"key_column {key_column!r} is not in the data. Available columns: "
            f"{', '.join(str(c) for c in df.columns)}."
        )
    repeated = list(df.columns).count(key_column)
    if repeated > 1:
        raise ValueError(
            f"key_column {key_column!r} appears {repeated} times in the data: "
            "df[key_column] is then a table rather than a column, and every row would "
            "be labelled with the column name. Rename or drop the duplicate columns."
        )
    return [_format_cell(value, missing="<no key>") for value in df[key_column]]


def _extra_values(df: pd.DataFrame, extra_columns: list[str], rows: int) -> list[dict[str, str]]:
    """One dict per row, holding the extra columns' values rendered as text.

    Empty dicts when nothing was asked for, so the caller can merge the dict into
    every report line either way rather than branching per line.
    """

    if not extra_columns:
        return [{} for _ in range(rows)]

    values = []
    for row in df[extra_columns].itertuples(index=False, name=None):
        values.append({column: _format_cell(value)
                       for column, value in zip(extra_columns, row)})
    return values


def build_report(
    frame_outcomes: list[list[CheckOutcome]],
    df: pd.DataFrame,
    key_column: str | None = None,
    extra_columns: list[str] | None = None,
    include: str = "failures",
) -> pd.DataFrame:
    """Build the long-format report: one line per failure, in evaluation order.

    `message`, `detail` and `comments` each say one thing -- what the check says
    on failure, why a check did not evaluate the row, and the evidence it
    returned -- so a column heading can be trusted.

    `is_root_cause` flags **every** failure at the shallowest failing layer, and
    is not always the first line: an independent chain registered earlier can be
    printed above a shallower failure. The columns, the `include` levels and what
    `extra_columns` refuses are in `reporting.md`.
    """

    if len(df) != len(frame_outcomes):
        raise ValueError(
            f"outcomes cover {len(frame_outcomes)} row(s) but the frame has {len(df)}: "
            "pass the same frame the outcomes were collected from."
        )
    wanted = _included(include)
    extra_columns = list(extra_columns or [])

    # A column is on offer when the frame holds it exactly once -- a duplicated
    # label would hand back a table rather than a column -- and when its name
    # would not collide with one the report writes itself.
    labels = list(df.columns)
    available = [str(column) for column in labels
                 if labels.count(column) == 1 and column not in REPORT_COLUMNS]
    _check_extra_columns(extra_columns, available, "the report")

    row_labels = _row_labels(df, key_column)
    extra = _extra_values(df, extra_columns, len(frame_outcomes))

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
    """Prefix a cell a spreadsheet would run as a formula with an apostrophe, so
    a value from the data such as `=cmd|'/c calc'!A1` displays as text instead of
    executing. A negative number keeps its minus sign."""

    if not isinstance(value, str) or not value:
        return value
    if value[0] in FORMULA_PREFIXES or (value[0] == "-" and not _looks_numeric(value)):
        return "'" + value
    return value


def render_report(report: pd.DataFrame, fmt: str = "table", wrap_width: int = 48) -> str:
    """Render a report as bordered text, wrapped at *wrap_width*, or as CSV.

    CSV cells a spreadsheet would run as a formula are neutralized on the way
    out, and that is not optional: a report is written to be opened by a person.
    A *wrap_width* of zero or less is refused -- there is no spelling of "do not
    wrap".
    """

    if wrap_width <= 0:
        raise ValueError(f"wrap_width must be greater than 0, got {wrap_width!r}.")
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

    `include` is the three levels the report takes; `"blocked"` drops the checks
    that simply passed, which is usually what you want hunting one bad row.
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

    The cause is named at the end rather than left to the reader: it is not
    always the first failing line, since two chains that do not touch can both
    fail and the deeper one may be evaluated first.
    """

    table = row_explanation(row_outcomes, include=include)
    print(format_table(table, wrap_columns={"detail": 60}))
    causes = root_causes(row_outcomes)
    label = "root cause" if len(causes) == 1 else "root causes"
    print(f"{label}: {', '.join(causes)}" if causes else "root cause: none - the row passed")
    return table


def summarize_outcomes(frame_outcomes: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """Count what happened to each check across many rows.

    `skipped` is the column that matters when tuning layered checks -- a high
    count means a fundamental check is failing often and hiding what is below it.
    `errored` stays separate from `failed` so a broken check is never mistaken
    for bad data.
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


def _by_rows_then_code(entry: tuple[str, int]) -> tuple[int, str]:
    """Sort key: most rows first, then code, so the tally reads worst-first and
    two runs over the same data order it the same way."""

    code, rows = entry
    return (-rows, code)


def root_cause_counts(frame_outcomes: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """How many rows bottomed out at each code, worst first.

    A row failing two chains at the same depth counts against each: the question
    is "how many rows would this code explain", and both explain that row.
    """

    causes: dict[str, int] = {}
    for row_outcomes in frame_outcomes:
        for cause in root_causes(row_outcomes):
            causes[cause] = causes.get(cause, 0) + 1
    ranked = sorted(causes.items(), key=_by_rows_then_code)
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
