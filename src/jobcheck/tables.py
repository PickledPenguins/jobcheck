"""What every table the package builds shares: how a cell reads as text, and how
a bad `add_columns` name or key column is refused.

The tables are plain DataFrames carrying every column they build, titled in
`attrs["title"]`; choosing columns and turning a table into text is the caller's,
with pandas (`drop(columns=...)`, `to_string()`, `to_csv()`).
`is_null` is the public part. The underscored helpers are shared with `views.py`
and `rules.py` and are not for callers.
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
    """Render one data cell as text: whole floats lose their `.0`, and a null becomes *missing*.

    Shared by the report and by rule matching so both see the same text. pandas
    holds an integer column as float as soon as one cell is blank, and
    `iterrows` upcasts a whole row to float when every column is numeric.
    A rule written against what the report prints (`41`) must match that cell (`41.0`).
    """
    if is_null(value):
        return missing
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _reject_unknown_columns(requested: list[str], available: list[str], subject: str) -> None:
    """Reject `add_columns` names that are not on offer, or asked for twice."""
    unusable = sorted(
        {name for name in requested
         if name not in available or requested.count(name) > 1}
    )
    if unusable:
        raise ValueError(
            f"add_columns {unusable} cannot be used for {subject}. Each name must be "
            f"asked for once and be one of: {', '.join(available) or '(none available)'}."
        )


def _require_one_column(df: pd.DataFrame, parameter: str, column: Any) -> None:
    """Refuse a *column*, passed as *parameter*, that is not exactly one column of *df*."""
    if column not in df.columns:
        raise ValueError(
            f"{parameter} {column!r} is not in the data. Available columns: "
            f"{', '.join(str(c) for c in df.columns)}.")
    repeated = list(df.columns).count(column)
    if repeated > 1:
        raise ValueError(
            f"{parameter} {column!r} appears {repeated} times in the data. "
            "Rename or drop the duplicate columns.")
