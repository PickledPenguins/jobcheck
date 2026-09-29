"""What every table the package builds shares: its default columns, its title,
and how a cell reads as text.

The tables are plain DataFrames; turning one into text is the caller's, with
pandas (`to_string(index=False)`, `to_csv(index=False)`). `is_null` is the public
part. The underscored helpers are shared with `report.py`, `rules.py` and
`registry_tables.py` -- how every table reads a cell and rejects a bad column
name the same way -- and are not for callers.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def is_null(value: Any) -> bool:
    """Whether a single cell is null. Non-scalars are never null here: `pd.isna`
    returns an *array* for them, and `bool()` on that raises."""

    if not pd.api.types.is_scalar(value):
        return False
    return bool(pd.isna(value))


def _format_cell(value: Any, missing: str = "") -> str:
    """Render one data cell as text: whole floats lose their `.0`, and a null
    becomes *missing*.

    Shared by the report and by rule matching so both see the same text. pandas
    holds an integer column as float as soon as one cell is blank, and
    `iterrows` upcasts a whole row to float when every column is numeric; a
    rule written against what the report prints (`41`) must match that cell
    (`41.0`).
    """

    if value is None or is_null(value):
        return missing
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _reject_unknown_columns(requested: list[str], available: list[str], subject: str) -> None:
    """Reject `add_columns` names that are not on offer, or asked for twice.

    Shared by every table that takes the argument, so one mistake is reported the
    same way whichever table it was made against. A name quietly dropped is a
    column the caller believes is there.
    """

    unusable = sorted(
        {name for name in requested
         if name not in available or requested.count(name) > 1}
    )
    if unusable:
        raise ValueError(
            f"add_columns {unusable} cannot be used for {subject}. Each name must be "
            f"asked for once and be one of: {', '.join(available) or '(none available)'}."
        )


#: The columns each table shows, in order. Edit here to change what every entry
#: point sees: a column left out is still built, and a table taking add_columns
#: can still ask for it by name. Keyed by the table's title.
_DEFAULT_COLUMNS = {
    "Report": ["row", "code", "status", "layer", "outcome", "message", "detail",
               "comments", "is_root_cause"],
    "Registry": ["code", "layer", "default", "message", "depends_on"],
    "Rules": ["name", "action", "codes_hit_count", "match", "message"],
    "Row explanation": ["layer", "code", "outcome", "status", "detail"],
    "Summary": ["code", "layer", "failed", "root_cause_rows", "errored", "skipped",
                "disabled", "passed"],
}


def _shown(table: pd.DataFrame, title: str,
           add_columns: list[str] | None = None) -> pd.DataFrame:
    """*table* narrowed to its default columns plus *add_columns*, and titled.

    `add_columns` may name any column the table built but does not show by
    default; anything else is refused, since a name quietly dropped is a column
    the caller believes is there.
    """

    shown = _DEFAULT_COLUMNS[title]
    add_columns = list(add_columns or [])
    hidden = [str(name) for name in table.columns if name not in shown]
    _reject_unknown_columns(add_columns, hidden, f"the {title.lower()} table")
    narrowed = table[[*shown, *add_columns]]
    narrowed.attrs["title"] = title
    return narrowed
