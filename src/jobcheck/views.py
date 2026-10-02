"""Views of what `validate` returned, and of the configuration it ran: each a
DataFrame carrying its own title in `attrs["title"]`, built from data already
collected. Nothing here runs a check.

`validate` keeps every check's outcome on every row; a view picks what it
shows. The report is **long format** -- one line per check per data row,
indexed by the row so its lines hang together -- which is the diagnostic unit,
survives being written as CSV, and sorts and filters cleanly downstream. There
is no command line; a pipeline decides where output goes.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import pandas as pd

from .registry import _CHECKS, _get_topo_order
from .results import CheckOutcome, Outcome, _render_status
from .rules import Rule
from .tables import _format_cell, _reject_unknown_columns

_REPORT_COLUMNS = ("row", "code", "status", "layer", "outcome", "message", "detail", "comments",
                  "is_root_cause")
_REGISTRY_COLUMNS = ["code", "layer", "default", "repeat", "message", "depends_on",
                     "source_file", "could_be_overridden_by"]
_RULES_COLUMNS = ["name", "action", "codes_hit_count", "codes", "match", "message",
                  "source_file"]

# Which outcomes reach a report, worst-first. Every level contains the one
# before it, so the choice is how far down to go rather than a set of
# independent switches. "root_causes" is the failures level narrowed further,
# to each row's root causes.
INCLUDE_LEVELS: dict[str, set[Outcome]] = {
    "root_causes": {Outcome.FAILED, Outcome.ERRORED},
    "failures": {Outcome.FAILED, Outcome.ERRORED},
    "blocked": {Outcome.FAILED, Outcome.ERRORED, Outcome.SKIPPED, Outcome.DISABLED},
    "all": set(Outcome),
}


def _included(include: str) -> set[Outcome]:
    """The outcomes an ``include`` level covers, or a ValueError naming the levels."""

    if include not in INCLUDE_LEVELS:
        raise ValueError(
            f"include must be one of {', '.join(INCLUDE_LEVELS)}, got {include!r}.")
    return INCLUDE_LEVELS[include]


def _root_causes(row_outcomes: list[CheckOutcome]) -> list[str]:
    """Every failure at the shallowest failing layer, in evaluation order.

    Every one, not the first: two failures in the same layer are two causes.
    Deeper failures are left out. They are never downstream of these -- a check
    runs only once its prerequisites passed, so each failure is the root of its
    own chain -- they are the ones to read after.

    Data failures come first: an `errored` check counts only on a row with no
    `failed` one, so a broken check never takes the flag from a real failure,
    and a row whose only problem is a broken check is still flagged.
    """

    failures = [outcome for outcome in row_outcomes if outcome.outcome is Outcome.FAILED]
    if not failures:
        failures = [outcome for outcome in row_outcomes if outcome.failed]
    if not failures:
        return []
    shallowest = min(outcome.layer for outcome in failures)
    return [outcome.code for outcome in failures if outcome.layer == shallowest]


def _render_comments(comments: Mapping[Any, Any]) -> str:
    """Render a check's comments as `key=value; key=value`, in the order the check
    wrote them. Not sorted: a key of any type renders, and a dict's order is
    already the same every run."""

    return "; ".join(f"{key}={value}" for key, value in comments.items())


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
    """Build the long-format report: one line per included outcome, in
    evaluation order, indexed by the row key, the `add_columns` and `code`. The
    key level is named after `key_column`, or `row` when the frame's index is the
    key, so a CSV reader can tell an id from a position.

    The index is what makes a row's lines hang together: printed, a repeated
    `row` and added value show once, on the row's first line. Two data rows
    with the same label print as one; label them with a unique `key_column`.

    `message`, `detail` and `comments` each say one thing -- what the check says
    on failure, why a check did not evaluate the row, and the evidence it
    returned -- so a column heading can be trusted.

    `is_root_cause` flags **every** failure at the shallowest failing layer, and
    is not always the first line: an independent chain registered earlier can be
    printed above a shallower failure. The columns, the `include` levels and what
    `add_columns` refuses are in `reporting.md`.
    """

    if len(df) != len(frame_outcomes):
        raise ValueError(
            f"outcomes cover {len(frame_outcomes)} row(s) but the frame has {len(df)}: "
            "pass the same frame the outcomes were collected from."
        )
    wanted = _included(include)
    add_columns = list(add_columns or [])
    row_labels = _row_labels(df, key_column)
    key = "row" if key_column is None else key_column
    if key in _REPORT_COLUMNS[1:]:
        raise ValueError(
            f"key_column {key_column!r} would head the report's key, but the report "
            f"already has a column of that name ({', '.join(_REPORT_COLUMNS[1:])}). "
            "Copy the column under another name and pass that.")

    # A column is on offer when its name appears exactly once -- a duplicated
    # label would hand back a table rather than a column -- and would not collide
    # with one the report writes itself, the key included. It is asked for by name
    # as text and read by the frame's own label, which may be a number.
    names = [str(column) for column in df.columns]
    taken = {*_REPORT_COLUMNS, str(key)}
    available = {name: column for name, column in zip(names, df.columns)
                 if names.count(name) == 1 and name not in taken}
    _reject_unknown_columns(add_columns, list(available), "the report")
    added = _added_values(df, [available[name] for name in add_columns], add_columns,
                          len(frame_outcomes))

    rows: list[dict[str, Any]] = []
    for label, row_outcomes, context in zip(row_labels, frame_outcomes, added):
        causes = set(_root_causes(row_outcomes))
        for outcome in row_outcomes:
            if outcome.outcome not in wanted:
                continue
            if include == "root_causes" and outcome.code not in causes:
                continue
            rows.append(
                {
                    key: label,
                    **context,
                    "code": outcome.code,
                    "status": _render_status(outcome.status),
                    "layer": outcome.layer,
                    "outcome": outcome.outcome.value,
                    "message": outcome.message,
                    "detail": outcome.detail,
                    "comments": _render_comments(outcome.comments),
                    "is_root_cause": outcome.code in causes,
                }
            )
    # The key first and the added columns straight after it, so a reader meets
    # the identity and its context before the outcome.
    index = [key, *add_columns, "code"]
    report = pd.DataFrame(rows, columns=[*index, *_REPORT_COLUMNS[2:]]).set_index(index)
    report.attrs["title"] = "Report"
    return report


def explain_row(frame_outcomes: list[list[CheckOutcome]], position: int) -> pd.DataFrame:
    """What every check did to the row at *position* -- counted from 0, as in
    `validate`'s result -- and why: one line per check, in evaluation order.

    `detail` is the one column that says why: the reason a check did not
    evaluate the row, else the evidence it returned, else its message.
    """

    if not 0 <= position < len(frame_outcomes):
        raise ValueError(
            f"position {position} is not a row: outcomes cover {len(frame_outcomes)} "
            "row(s), numbered from 0.")
    table = pd.DataFrame(
        [
            {
                "layer": outcome.layer,
                "code": outcome.code,
                "outcome": outcome.outcome.value,
                "status": _render_status(outcome.status),
                "detail": outcome.detail
                or _render_comments(outcome.comments)
                or outcome.message
                or "-",
            }
            for outcome in frame_outcomes[position]
        ],
        columns=["layer", "code", "outcome", "status", "detail"],
    )
    table.attrs["title"] = "Row explanation"
    return table


def summarize_outcomes(frame_outcomes: Iterable[list[CheckOutcome]]) -> pd.DataFrame:
    """Count what happened to each check across many rows, worst first: by
    `failed`, then `root_cause_rows`, then shallowest layer, then code.

    `skipped` is the column that matters when tuning layered checks -- a high
    count means a fundamental check is failing often and hiding what is below it.
    `errored` stays separate from `failed` so a broken check is never mistaken
    for bad data. `root_cause_rows` counts the rows whose root cause the check
    is; a row failing two chains at the same depth counts against both. An
    errored check counts only on a row with no data failure, where it is the
    one thing to read; that is how `root_cause_rows` can exceed `failed`.
    `shared` counts the copies under `validate(repeat_key=...)` that reused the
    first copy's result; `failed` and `passed` count only the calls made.
    """

    counts: dict[str, dict[Outcome, int]] = {}
    layers: dict[str, int] = {}
    causes: dict[str, int] = {}
    for row_outcomes in frame_outcomes:
        for outcome in row_outcomes:
            entry = counts.get(outcome.code)
            if entry is None:   # built once per code, not per outcome
                entry = counts[outcome.code] = dict.fromkeys(Outcome, 0)
            entry[outcome.outcome] += 1
            layers[outcome.code] = outcome.layer
        for cause in _root_causes(row_outcomes):
            causes[cause] = causes.get(cause, 0) + 1

    columns = ["code", "layer", "failed", "root_cause_rows", "errored", "skipped",
               "disabled", "shared", "passed"]
    rows = [
        {
            "code": code,
            "layer": layers[code],
            "failed": entry[Outcome.FAILED],
            "root_cause_rows": causes.get(code, 0),
            "errored": entry[Outcome.ERRORED],
            "skipped": entry[Outcome.SKIPPED],
            "disabled": entry[Outcome.DISABLED],
            "shared": entry[Outcome.SHARED],
            "passed": entry[Outcome.PASSED],
        }
        for code, entry in counts.items()
    ]
    table = pd.DataFrame(rows, columns=columns)
    if rows:
        # Ties on failures put the root cause, the check to read first, on top.
        table = (table.sort_values(["failed", "root_cause_rows", "layer", "code"],
                                   ascending=[False, False, True, True])
                 .reset_index(drop=True))
    table.attrs["title"] = "Summary"
    return table


def _rules_for_code(code: str, rules: list[Rule]) -> list[Rule]:
    """Rules that reference *code*, in load order."""

    return [rule for rule in rules if code in rule.codes]


def _render_match(rule: Rule) -> str:
    """Compact one-cell rendering of a rule's match criteria."""

    if rule.match_all:
        return "all"
    return "; ".join(f"{criterion.column}~=/{criterion.pattern}/"
                     for criterion in rule.criteria)


def registry_table(rules: list[Rule] | None = None) -> pd.DataFrame:
    """One row per registered check, ordered layer then code, so the fundamental
    checks read first.

    `could_be_overridden_by` is the one column that reads `rules`, and `rules`
    feeds nothing else. It is not "was overridden by": whether a rule fires
    depends on the row it is matched against, and this table has no row.
    """

    # Layers are computed with the evaluation order; a check registered outside
    # load_checks has none until something asks for it.
    _get_topo_order()
    # Read once per check, so a generator is made a list first.
    rules = list(rules or [])

    rows: list[dict[str, Any]] = []
    for check in _CHECKS:
        matching = _rules_for_code(check.code, rules)
        state = "ON" if check.default_enabled else "OFF"
        rows.append({
            "code": check.code,
            "layer": check.layer,
            "default": state,
            "repeat": ("declared" if check.repeat
                       else "inherited" if check.repeats else "-"),
            "message": check.message,
            "depends_on": "; ".join(check.depends_on) if check.depends_on else "-",
            "source_file": check.source_file,
            "could_be_overridden_by":
                "; ".join(f"{rule.name} ({rule.action})" for rule in matching) or "-",
        })

    # Columns are named so an empty registry still has them to sort by.
    table = (pd.DataFrame(rows, columns=_REGISTRY_COLUMNS)
             .sort_values(["layer", "code"]).reset_index(drop=True))
    table.attrs["title"] = "Registry"
    return table


def rules_table(rules: list[Rule]) -> pd.DataFrame:
    """One row per rule, rather than per code.

    `codes_hit_count` is a count beside the code list, so a caller can drop
    `codes` and keep a rule touching many codes from blowing the table apart.
    """

    rows: list[dict[str, Any]] = []
    for rule in rules:
        rows.append({
            "name": rule.name,
            "action": rule.action,
            "codes_hit_count": len(rule.codes),
            "codes": ", ".join(rule.codes),
            "match": _render_match(rule),
            "message": rule.message,
            "source_file": rule.source_file,
        })

    table = pd.DataFrame(rows, columns=_RULES_COLUMNS)
    table.attrs["title"] = "Rules"
    return table
