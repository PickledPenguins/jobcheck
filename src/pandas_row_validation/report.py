"""Turning outcomes into a report: collection, the failure table, and rendering.

Everything a caller needs to produce and save a report lives here -- collecting
outcomes for a frame, building the long-format failure table, rendering it as
text or CSV, and writing it to a file. There is no command line: a pipeline
calls these functions and decides where the output goes.

The report is **long format**: one row per failed test per data row. That is the
diagnostic unit, it is the only shape that survives being written as CSV, and it
sorts and filters cleanly downstream.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

import pandas as pd

from .context import RowContext, build_context
from .registry import OverrideRule, explain_row, root_cause
from .results import DISABLED, ERRORED, FAILED, PASSED, SKIPPED, TestOutcome, render_status
from .tables import format_table

REPORT_COLUMNS = ["row", "code", "status", "layer", "suite", "outcome", "message", "comments",
                  "is_root_cause"]

# A spreadsheet treats a cell starting with one of these as a formula, so a value
# taken from the data and written into a CSV can execute when someone opens the
# report. Escaping happens on the way out, not on the way in, so the outcomes and
# the table view keep the value the test actually saw.
FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")

ContextBuilder = Callable[["pd.Series[Any]"], RowContext | None]


def collect_outcomes(
    df: pd.DataFrame,
    overrides: list[OverrideRule] | None = None,
    context_builder: ContextBuilder = build_context,
    on_error: str = "record",
) -> list[list[TestOutcome]]:
    """Run every test against every row and keep all the outcomes.

    Keeps the tests that did not run as well as the ones that did, because that
    is what the explanation and summary views are built from. For a frame large
    enough that the extra objects matter, use
    :func:`pandas_row_validation.validate_row` per row instead and skip the report.

    ``on_error`` is passed through to :func:`pandas_row_validation.explain_row`.
    """

    return [
        explain_row(row, ctx=context_builder(row), overrides=overrides, on_error=on_error)
        for _, row in df.iterrows()
    ]


def render_comments(comments: Mapping[str, Any]) -> str:
    """Render a test's comments as ``key=value; key=value``, sorted by key.

    Sorted so the same failure renders identically every run, which is what lets
    reports be diffed and byte-compared in tests.
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


def _row_labels(df: pd.DataFrame, key_column: str | list[str] | None) -> list[str]:
    """One label per row: the key column(s) if given, else the frame's index."""

    if key_column is None:
        return [_label_value(label) for label in df.index]

    columns = [key_column] if isinstance(key_column, str) else list(key_column)
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"key_column {missing} is not in the data. Available columns: "
            f"{', '.join(str(c) for c in df.columns)}."
        )
    return ["|".join(_label_value(row[column]) for column in columns) for _, row in df.iterrows()]


def _check_data_columns(df: pd.DataFrame | None, data_columns: list[str]) -> None:
    """Reject anything that would make the extra columns ambiguous or empty."""

    if not data_columns:
        return
    if df is None:
        raise ValueError("data_columns names columns in the frame; pass df as well.")

    missing = [column for column in data_columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"data_columns {missing} is not in the data. Available columns: "
            f"{', '.join(str(c) for c in df.columns)}."
        )
    repeated = sorted({column for column in data_columns if data_columns.count(column) > 1})
    if repeated:
        raise ValueError(f"data_columns names {repeated} more than once.")

    # A duplicated label makes df[data_columns] return more values than names, and
    # the values would then be paired with the wrong headings -- wrong data in a
    # report, reported silently. The per-row engine refuses duplicate labels for
    # the same reason.
    ambiguous = sorted({
        column for column in data_columns
        if int((df.columns == column).sum()) > 1
    })
    if ambiguous:
        raise ValueError(
            f"data_columns {ambiguous} appears more than once in the frame, so the report "
            "cannot tell which column you meant. Rename or drop the duplicates first."
        )
    clashing = sorted(set(data_columns) & set(REPORT_COLUMNS))
    if clashing:
        raise ValueError(
            f"data_columns {clashing} would collide with the report's own column(s) of the "
            "same name. Rename the column in the frame first, e.g. "
            "df.rename(columns={'code': 'source_code'})."
        )


def build_report(
    outcomes_per_row: list[list[TestOutcome]],
    df: pd.DataFrame | None = None,
    key_column: str | list[str] | None = None,
    data_columns: list[str] | None = None,
    include_skipped: bool = False,
    include_passed: bool = False,
) -> pd.DataFrame:
    """Build the long-format report: one row per failure.

    Columns are ``row``, ``code``, ``status`` (``INVALID (3)``), ``layer``,
    ``suite``, ``outcome``, ``message``, ``comments``, ``is_root_cause``. Rows
    keep evaluation order within each data row, so the root cause is the first
    line for that row.

    ``key_column`` names the column (or columns) that identify a data row, which
    is what makes a report readable once the frame has been filtered; without it
    the frame's index is used, and *df* is then only needed for that index.

    ``data_columns`` copies further columns from the frame into the report, in the
    order given, immediately after ``row``. They carry the context a reader needs
    to judge a failure without going back to the source file -- the source system,
    the batch, the field the test was reading. A name that is not in the frame,
    named twice, or colliding with one of the report's own columns is refused
    rather than quietly dropped or overwritten.
    ``include_skipped`` adds the tests a failure blocked, each naming its
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
        cause = root_cause(outcomes)
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
                    "suite": outcome.suite,
                    "outcome": outcome.outcome,
                    "message": outcome.message or outcome.detail,
                    "comments": render_comments(outcome.comments) or outcome.detail,
                    "is_root_cause": outcome.code == cause,
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


def row_explanation(outcomes: list[TestOutcome], only_relevant: bool = False) -> pd.DataFrame:
    """One row per test, in evaluation order: what it did and why.

    ``only_relevant`` drops the tests that simply passed, which is usually what
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


def print_row_explanation(outcomes: list[TestOutcome], only_relevant: bool = False) -> pd.DataFrame:
    """Print what every test did on one row, then the row's root cause.

    Reading order is evaluation order, so the first ``failed`` line is the root
    cause and every ``skipped`` line below it names the prerequisite that
    blocked it.
    """

    table = row_explanation(outcomes, only_relevant=only_relevant)
    print(format_table(table, wrap_columns={"detail": 60}))
    cause = root_cause(outcomes)
    print(f"root cause: {cause}" if cause else "root cause: none - the row passed")
    return table


def summarise_outcomes(outcomes_per_row: Iterable[list[TestOutcome]]) -> pd.DataFrame:
    """Count what happened to each test across many rows.

    ``skipped`` is the column that matters when tuning layered tests: a high
    count means a fundamental test is failing often and hiding everything below
    it. ``errored`` is kept separate from ``failed`` so a broken test can never
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


def root_cause_counts(outcomes_per_row: Iterable[list[TestOutcome]]) -> pd.DataFrame:
    """How many rows bottomed out at each code, worst first."""

    causes: dict[str, int] = {}
    for outcomes in outcomes_per_row:
        cause = root_cause(outcomes)
        if cause is not None:
            causes[cause] = causes.get(cause, 0) + 1
    ranked = sorted(causes.items(), key=lambda item: (-item[1], item[0]))
    return pd.DataFrame(
        [{"root_cause": code, "rows": count} for code, count in ranked],
        columns=["root_cause", "rows"],
    )


def print_summary(outcomes_per_row: list[list[TestOutcome]]) -> pd.DataFrame:
    """Print the per-test summary, worst first, and the root-cause tally."""

    table = summarise_outcomes(outcomes_per_row)
    if table.empty:
        print("No tests ran.")
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
