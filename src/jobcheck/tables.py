"""Plain-text table rendering, shared by the registry and the report.

`DataFrame.to_string()` is cramped and unbordered for auditing, and a table
library would be a runtime dependency for formatting alone.
"""

from __future__ import annotations

import textwrap
from typing import Any

import pandas as pd


def is_null(value: Any) -> bool:
    """Whether a single cell is null. Non-scalars are never null here: `pd.isna`
    returns an *array* for them, and `bool()` on that raises."""

    if not pd.api.types.is_scalar(value):
        return False
    return bool(pd.isna(value))


def _check_extra_columns(requested: list[str], available: list[str], subject: str) -> None:
    """Reject `extra_columns` names that are not on offer, or asked for twice.

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
            f"extra_columns {unusable} cannot be used for {subject}. Each name must be "
            f"asked for once and be one of: {', '.join(available) or '(none available)'}."
        )


def _cell_lines(value: Any, width: int | None) -> list[str]:
    """One cell as the lines it occupies. Wrapping never breaks inside a word, so
    a long code or rule name overflows its width rather than being mangled."""

    text = "" if value is None or is_null(value) else str(value)
    if width is None:
        return [text]
    return textwrap.wrap(text, width, break_long_words=False, break_on_hyphens=False) or [""]


def _padded_line(texts: list[str], widths: list[int]) -> str:
    """One rendered line: every text padded out to its own column's width."""

    return " | ".join(text.ljust(width) for text, width in zip(texts, widths))


def format_table(table: pd.DataFrame, wrap_columns: dict[str, int] | None = None) -> str:
    """Render a DataFrame as a bordered plain-text table using only the stdlib.

    ``|``-separated columns, a ``-+-`` divider, left-aligned, widths sized to the
    content. *wrap_columns* maps a column name to a target width; long free text
    wraps onto extra lines within the same table row. An empty frame renders as
    ``(empty)``.

    Rendering is two passes, because a column's width is not known until every
    cell in it has been wrapped.
    """

    if table.empty:
        return "(empty)"

    wrap = wrap_columns or {}
    headers = [str(column) for column in table.columns]

    # First pass: wrap every cell. rows[r][c] is the list of lines that column c
    # occupies in row r -- one line for most cells, several for a wrapped one.
    rows: list[list[list[str]]] = []
    for _, row in table.iterrows():
        rows.append([_cell_lines(row[column], wrap.get(str(column))) for column in table.columns])

    # A column is as wide as its heading, or as its widest wrapped line.
    widths = []
    for index, header in enumerate(headers):
        width = len(header)
        for row_lines in rows:
            for line in row_lines[index]:
                width = max(width, len(line))
        widths.append(width)

    # Second pass: print. A row is as tall as its tallest cell, and a cell with
    # fewer lines than that is blank on the rest of them.
    out = [_padded_line(headers, widths)]
    out.append("-+-".join("-" * width for width in widths))
    for row_lines in rows:
        height = max(len(lines) for lines in row_lines)
        for line_index in range(height):
            texts = []
            for lines in row_lines:
                texts.append(lines[line_index] if line_index < len(lines) else "")
            out.append(_padded_line(texts, widths))
    return "\n".join(out)
