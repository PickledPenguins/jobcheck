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
from .rules import OverrideRule
from .results import DISABLED, ERRORED, FAILED, PASSED, SKIPPED, CheckOutcome, render_status
from .tables import format_table

REPORT_COLUMNS = ["row", "code", "status", "layer", "outcome", "message", "comments",
                  "is_root_cause"]

# A spreadsheet treats a cell starting with one of these as a formula, so a value
# taken from the data and written into a CSV can execute when someone opens the
# report. Escaping happens on the way out, not on the way in, so the outcomes and
# the table view keep the value the check actually saw.
FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")

def render_comments(comments: Mapping[str, Any]) -> str:
    """Render a check's comments as ``key=value; key=value``, sorted by key.

    Sorted so the same failure renders identically every run, which is what lets
    reports be diffed and byte-compared in checks.
    """

    return "; ".join(f"{key}={comments[key]}" for key in sorted(comments))


def _cell_value(value: Any) -> str:
    """Render a value copied from the data into a report column.

    Whole floats lose their ``.0`` and a missing value reads as empty, which is
    what a person expects of a data column -- unlike the row key, where a missing
    value is worth naming.
    """

    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _label_value(value: Any) -> str:
    """Render one key value for the report.

    Whole floats lose their ``.0`` -- an integer id column that pandas widened to
    float because one row is blank should still read as ``104``, not ``104.0``
    -- and a missing key reads as ``<no key>`` rather than ``nan``.
    """

    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return "<no key>"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


KEY_SEPARATOR = "|"


def _row_labels(df: pd.DataFrame, key_column: str | list[str] | None) -> list[str]:
    """One label per row: the key column(s) if given, else the frame's index.

    Several key columns are joined with ``|``. A value carrying that separator
    is refused rather than joined, because ``("a|b", "c")`` and ``("a", "b|c")``
    would otherwise render the same label and two different rows would be
    indistinguishable in the report -- which is the one thing a key column
    exists to prevent.
    """

    if key_column is None:
        return [_label_value(label) for label in df.index]

    columns = [key_column] if isinstance(key_column, str) else list(key_column)
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"key_column {missing} is not in the data. Available columns: "
            f"{', '.join(str(c) for c in df.columns)}."
        )
    if len(columns) == 1:
        return [_label_value(value) for value in df[columns[0]]]

    labels: list[str] = []
    for position, (_, row) in enumerate(df.iterrows()):
        parts = [_label_value(row[column]) for column in columns]
        carrying = [column for column, part in zip(columns, parts) if KEY_SEPARATOR in part]
        if carrying:
            raise ValueError(
                f"Row {position}: key column(s) {carrying} hold the {KEY_SEPARATOR!r} "
                "that joins a multi-column key, so two different rows could produce "
                "the same label. Use a single key column, or a column whose values do "
                f"not contain {KEY_SEPARATOR!r}."
            )
        labels.append(KEY_SEPARATOR.join(parts))
    return labels


def _check_data_columns(df: pd.DataFrame | None, data_columns: list[str]) -> None:
    """Reject anything that would make the extra columns ambiguous or empty."""

    if not data_columns:
        return
    if df is None:
        raise ValueError("data_columns names columns in the frame; pass df as well.")

    # A name that is not there, or is there twice, would pair values with the
    # wrong headings -- wrong data in a report, reported silently -- and a name
    # the report already uses would overwrite the report's own column.
    unusable = sorted(
        {column for column in data_columns
         if int((df.columns == column).sum()) != 1
         or data_columns.count(column) > 1
         or column in REPORT_COLUMNS}
    )
    if unusable:
        raise ValueError(
            f"data_columns {unusable} cannot be used. Each name must appear exactly once "
            f"in the frame, once in data_columns, and not be one of the report's own "
            f"columns {REPORT_COLUMNS}. Frame columns: "
            f"{', '.join(str(c) for c in df.columns)}."
        )


def build_report(
    outcomes_per_row: list[list[CheckOutcome]],
    df: pd.DataFrame | None = None,
    key_column: str | list[str] | None = None,
    data_columns: list[str] | None = None,
    include_skipped: bool = False,
    include_passed: bool = False,
) -> pd.DataFrame:
    """Build the long-format report: one row per failure.

    Columns are ``row``, ``code``, ``status`` (``INVALID (3)``), ``layer``,
    ``outcome``, ``message``, ``comments``, ``is_root_cause``. Lines
    keep evaluation order within each data row; the root cause is the line (or
    lines) flagged by ``is_root_cause``, which is not necessarily the first --
    an independent chain registered earlier can be printed above a shallower
    failure. ``is_root_cause`` is True for **every** failure at the shallowest
    failing layer, since two failures at the same depth are two root causes.

    ``key_column`` names the column (or columns) that identify a data row, which
    is what makes a report readable once the frame has been filtered; without it
    the frame's index is used, and *df* is then only needed for that index.

    ``data_columns`` copies further columns from the frame into the report, in the
    order given, immediately after ``row``. They carry the context a reader needs
    to judge a failure without going back to the source file -- the source system,
    the batch, the field the check was reading. A name that is not in the frame,
    named twice, or colliding with one of the report's own columns is refused
    rather than quietly dropped or overwritten.
    ``include_skipped`` adds the checks a failure blocked, each naming its
    blocking prerequisite -- useful when the question is "why did nothing fire?"
    rather than "what is wrong with this row?". ``include_passed`` adds
    everything else, which turns the report into a full audit trail.
    """

    if df is not None and len(df) != len(outcomes_per_row):
        raise ValueError(
            f"outcomes cover {len(outcomes_per_row)} row(s) but the frame has {len(df)}: "
            "pass the same frame the outcomes were collected from."
        )
    if key_column is not None and df is None:
        raise ValueError("key_column needs the frame it names columns in; pass df as well.")
    data_columns = list(data_columns or [])
    _check_data_columns(df, data_columns)

    labels = _row_labels(df, key_column) if df is not None else [
        str(index) for index in range(len(outcomes_per_row))
    ]

    wanted = {FAILED, ERRORED}
    if include_skipped:
        wanted |= {SKIPPED, DISABLED}
    if include_passed:
        wanted |= {PASSED, SKIPPED, DISABLED}

    extra = (
        [{column: _cell_value(value) for column, value in zip(data_columns, values)}
         for values in df[data_columns].itertuples(index=False, name=None)]
        if data_columns and df is not None
        else [{} for _ in outcomes_per_row]
    )

    rows: list[dict[str, Any]] = []
    for label, outcomes, context in zip(labels, outcomes_per_row, extra):
        causes = set(root_causes(outcomes))
        for outcome in outcomes:
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
                    "message": outcome.message or outcome.detail,
                    "comments": render_comments(outcome.comments) or outcome.detail,
                    "is_root_cause": outcome.code in causes,
                }
            )
    columns = ["row", *data_columns, *REPORT_COLUMNS[1:]]
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
    would execute on open. The apostrophe is the standard neutraliser: the cell
    displays as text. A negative number keeps its minus sign, since that is not
    a formula.
    """

    if not isinstance(value, str) or not value:
        return value
    if value[0] in FORMULA_PREFIXES or (value[0] == "-" and not _looks_numeric(value)):
        return "'" + value
    return value


def render_report(
    report: pd.DataFrame, fmt: str = "table", wrap: int = 48, escape_formulas: bool = True
) -> str:
    """Render a report as bordered text or as CSV.

    ``fmt="table"`` wraps ``message`` and ``comments`` at *wrap* characters so a
    long explanation stays inside its column; ``fmt="csv"`` emits the same
    columns unwrapped, for a spreadsheet or another tool.

    CSV cells that a spreadsheet would run as a formula are neutralised with a
    leading apostrophe -- see :func:`escape_for_spreadsheet` -- because comments
    carry values that came from the data. Pass ``escape_formulas=False`` when the
    CSV feeds another program rather than a person, and the exact bytes matter.
    """

    if fmt == "table":
        return format_table(report, wrap_columns={"message": wrap, "comments": wrap})
    if fmt == "csv":
        rendered = report.map(escape_for_spreadsheet) if escape_formulas else report
        return rendered.to_csv(index=False)
    raise ValueError(f"fmt must be 'table' or 'csv', got {fmt!r}.")


def write_report(
    report: pd.DataFrame, path: str, fmt: str = "csv", escape_formulas: bool = True
) -> None:
    """Write a rendered report to a file, creating or replacing it.

    The file is the thing a person opens in a spreadsheet, so formula escaping is
    on by default here too.
    """

    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(render_report(report, fmt=fmt, escape_formulas=escape_formulas))


def print_report(report: pd.DataFrame, fmt: str = "table", wrap: int = 48) -> None:
    """Print a rendered report, or a plain line when nothing failed."""

    if report.empty:
        print("No failures.")
        return
    print(render_report(report, fmt=fmt, wrap=wrap))


def row_explanation(outcomes: list[CheckOutcome], only_relevant: bool = False) -> pd.DataFrame:
    """One row per check, in evaluation order: what it did and why.

    ``only_relevant`` drops the checks that simply passed, which is usually what
    you want when hunting one bad row.
    """

    kept = [o for o in outcomes if not (only_relevant and o.outcome == PASSED)]
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


def print_row_explanation(outcomes: list[CheckOutcome], only_relevant: bool = False) -> pd.DataFrame:
    """Print what every check did on one row, then the row's root cause(s).

    Reading order is evaluation order, and every ``skipped`` line names the
    prerequisite that blocked it. The root cause is not always the first failing
    line: two chains that do not touch can both fail, and the deeper one may be
    evaluated first, so it is named explicitly at the end. Where two failures sit
    at the same depth, both are named.
    """

    table = row_explanation(outcomes, only_relevant=only_relevant)
    print(format_table(table, wrap_columns={"detail": 60}))
    causes = root_causes(outcomes)
    label = "root cause" if len(causes) == 1 else "root causes"
    print(f"{label}: {', '.join(causes)}" if causes else "root cause: none - the row passed")
    return table


def summarise_outcomes(outcomes_per_row: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """Count what happened to each check across many rows.

    ``skipped`` is the column that matters when tuning layered checks: a high
    count means a fundamental check is failing often and hiding everything below
    it. ``errored`` is kept separate from ``failed`` so a broken check can never
    be mistaken for bad data.
    """

    counts: dict[str, dict[str, int]] = {}
    layers: dict[str, int] = {}
    for outcomes in outcomes_per_row:
        for outcome in outcomes:
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


def root_cause_counts(outcomes_per_row: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """How many rows bottomed out at each code, worst first.

    A row failing two chains at the same depth counts once against each: the
    question this answers is "how many rows would this code explain", and both
    codes explain that row.
    """

    causes: dict[str, int] = {}
    for outcomes in outcomes_per_row:
        for cause in root_causes(outcomes):
            causes[cause] = causes.get(cause, 0) + 1
    ranked = sorted(causes.items(), key=lambda item: (-item[1], item[0]))
    return pd.DataFrame(
        [{"root_cause": code, "rows": count} for code, count in ranked],
        columns=["root_cause", "rows"],
    )


def print_summary(outcomes_per_row: list[list[CheckOutcome]]) -> pd.DataFrame:
    """Print the per-check summary, worst first, and the root-cause tally."""

    table = summarise_outcomes(outcomes_per_row)
    if table.empty:
        print("No checks ran.")
        return table
    print(format_table(table))

    causes = root_cause_counts(outcomes_per_row)
    print()
    if causes.empty:
        print("Root causes: none - every row passed.")
        return table
    print("Root cause of each failing row:")
    print(format_table(causes))
    return table
