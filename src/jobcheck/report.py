"""Turning outcomes into tables: the failure report, a row's explanation, and the
summary. Each is a DataFrame carrying its own title; `render` makes it text.

The report is **long format** -- one line per failed check per data row -- which
is the diagnostic unit, survives being written as CSV, and sorts and filters
cleanly downstream. There is no command line; a pipeline decides where output
goes.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import pandas as pd

from .engine import root_causes
from .results import DISABLED, ERRORED, FAILED, PASSED, SKIPPED, CheckOutcome, _render_status
from .tables import _DEFAULT_COLUMNS, _format_cell, _reject_unknown_columns, _shown

_REPORT_COLUMNS = ("row", "code", "status", "layer", "outcome", "message", "detail", "comments",
                  "is_root_cause")

# Which outcomes reach a report or an explanation, worst-first. Every level
# contains the one before it, so the choice is how far down to go rather than a
# set of independent switches.
INCLUDE_LEVELS: dict[str, set[str]] = {
    "failures": {FAILED, ERRORED},
    "blocked": {FAILED, ERRORED, SKIPPED, DISABLED},
    "all": {FAILED, ERRORED, SKIPPED, DISABLED, PASSED},
}

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
            "be labeled with the column name. Rename or drop the duplicate columns."
        )
    return [_format_cell(value, missing="<no key>") for value in df[key_column]]


def _added_values(df: pd.DataFrame, labels: list[Any], add_columns: list[str],
                  rows: int) -> list[dict[str, str]]:
    """One dict per row, holding the added columns' values rendered as text,
    keyed by the names in *add_columns* and read from the frame's *labels*.

    Empty dicts when nothing was asked for, so the caller can merge the dict into
    every report line either way rather than branching per line.
    """

    if not add_columns:
        return [{} for _ in range(rows)]

    values = []
    for row in df[labels].itertuples(index=False, name=None):
        values.append({column: _format_cell(value)
                       for column, value in zip(add_columns, row)})
    return values


def build_report(
    frame_outcomes: list[list[CheckOutcome]],
    df: pd.DataFrame,
    key_column: str | None = None,
    add_columns: list[str] | None = None,
    include: str = "failures",
) -> pd.DataFrame:
    """Build the long-format report: one line per failure, in evaluation order.

    `message`, `detail` and `comments` each say one thing -- what the check says
    on failure, why a check did not evaluate the row, and the evidence it
    returned -- so a column heading can be trusted.

    `is_root_cause` flags **every** failure at the shallowest failing layer, and
    is not always the first line: an independent chain registered earlier can be
    printed above a shallower failure. The columns, the `include` levels and what
    `add_columns` refuses are in `reporting.md`.

    The report's own columns shown are `tables._DEFAULT_COLUMNS["Report"]`, from
    `_REPORT_COLUMNS`. `add_columns` copies columns of *df* in, straight after `row`.
    """

    if len(df) != len(frame_outcomes):
        raise ValueError(
            f"outcomes cover {len(frame_outcomes)} row(s) but the frame has {len(df)}: "
            "pass the same frame the outcomes were collected from."
        )
    wanted = _included(include)
    add_columns = list(add_columns or [])

    # A column is on offer when its name appears exactly once -- a duplicated
    # label would hand back a table rather than a column -- and would not collide
    # with one the report writes itself. It is asked for by name as text and read
    # by the frame's own label, which may be a number.
    names = [str(column) for column in df.columns]
    available = {name: column for name, column in zip(names, df.columns)
                 if names.count(name) == 1 and name not in _REPORT_COLUMNS}
    _reject_unknown_columns(add_columns, list(available), "the report")

    row_labels = _row_labels(df, key_column)
    added = _added_values(df, [available[name] for name in add_columns], add_columns,
                          len(frame_outcomes))

    rows: list[dict[str, Any]] = []
    for label, row_outcomes, context in zip(row_labels, frame_outcomes, added):
        causes = set(root_causes(row_outcomes))
        for outcome in row_outcomes:
            if outcome.outcome not in wanted:
                continue
            rows.append(
                {
                    "row": label,
                    **context,
                    "code": outcome.code,
                    "status": _render_status(outcome.status),
                    "layer": outcome.layer,
                    "outcome": outcome.outcome,
                    "message": outcome.message,
                    "detail": outcome.detail,
                    "comments": render_comments(outcome.comments),
                    "is_root_cause": outcome.code in causes,
                }
            )
    # `row` first and the added columns straight after it, so a reader meets the
    # identity and its context before the outcome.
    shown = _DEFAULT_COLUMNS["Report"]
    rest = [name for name in shown if name != "row"]
    columns = ["row", *add_columns, *rest] if "row" in shown else [*add_columns, *rest]
    report = pd.DataFrame(rows, columns=[*_REPORT_COLUMNS, *add_columns])[columns]
    report.attrs["title"] = "Report"
    return report


def row_explanation(row_outcomes: list[CheckOutcome], include: str = "all") -> pd.DataFrame:
    """One row per check, in evaluation order: what it did and why.

    `include` is the three levels the report takes; `"blocked"` drops the checks
    that simply passed, which is usually what you want hunting one bad row.
    """

    wanted = _included(include)
    kept = [outcome for outcome in row_outcomes if outcome.outcome in wanted]
    table = pd.DataFrame(
        [
            {
                "layer": outcome.layer,
                "code": outcome.code,
                "outcome": outcome.outcome,
                "status": _render_status(outcome.status),
                "detail": outcome.detail
                or render_comments(outcome.comments)
                or outcome.message
                or "-",
            }
            for outcome in kept
        ],
        columns=["layer", "code", "outcome", "status", "detail"],
    )
    return _shown(table, "Row explanation")


def summarize_outcomes(frame_outcomes: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """Count what happened to each check across many rows, worst first.

    `skipped` is the column that matters when tuning layered checks -- a high
    count means a fundamental check is failing often and hiding what is below it.
    `errored` stays separate from `failed` so a broken check is never mistaken
    for bad data. `root_cause_rows` counts the rows whose root cause the check
    is; a row failing two chains at the same depth counts against both.
    """

    counts: dict[str, dict[str, int]] = {}
    layers: dict[str, int] = {}
    causes: dict[str, int] = {}
    for row_outcomes in frame_outcomes:
        for outcome in row_outcomes:
            entry = counts.setdefault(
                outcome.code, {PASSED: 0, FAILED: 0, ERRORED: 0, SKIPPED: 0, DISABLED: 0}
            )
            entry[outcome.outcome] += 1
            layers[outcome.code] = outcome.layer
        for cause in root_causes(row_outcomes):
            causes[cause] = causes.get(cause, 0) + 1

    columns = ["code", "layer", "failed", "root_cause_rows", "errored", "skipped",
               "disabled", "passed"]
    rows = [
        {
            "code": code,
            "layer": layers[code],
            "failed": entry[FAILED],
            "root_cause_rows": causes.get(code, 0),
            "errored": entry[ERRORED],
            "skipped": entry[SKIPPED],
            "disabled": entry[DISABLED],
            "passed": entry[PASSED],
        }
        for code, entry in counts.items()
    ]
    table = pd.DataFrame(rows, columns=columns)
    if rows:
        table = (table.sort_values(["failed", "errored", "skipped", "code"],
                                   ascending=[False, False, False, True])
                 .reset_index(drop=True))
    return _shown(table, "Summary")
