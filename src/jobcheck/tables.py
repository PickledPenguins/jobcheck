"""Plain-text table rendering, shared by the registry and the report.

``DataFrame.to_string()`` is cramped and unbordered for auditing, and a table
library would be a runtime dependency for output formatting alone, so this small
renderer lives here instead.
"""

from __future__ import annotations

import textwrap
from typing import Any

import pandas as pd


def is_null(value: Any) -> bool:
    """Whether a single cell is null.

    Non-scalars (lists, dicts, arrays, Series) are never null here: ``pd.isna``
    returns an *array* for them, and calling ``bool()`` on that raises the opaque
    "truth value of an array is ambiguous" error.
    """

    if not pd.api.types.is_scalar(value):
        return False
    return bool(pd.isna(value))


def _check_extra_columns(requested: list[str], available: list[str], subject: str) -> None:
    """Reject ``extra_columns`` names that are not on offer, or asked for twice.

    Shared by every table that takes an ``extra_columns`` argument -- the report,
    the registry, the override rules -- so one mistake is reported the same way
    whichever table it was made against. Refusing is deliberate: a name that is
    quietly dropped is a column the caller believes is there.
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


def format_table(table: pd.DataFrame, wrap_columns: dict[str, int] | None = None) -> str:
    """Render a DataFrame as a bordered plain-text table using only the stdlib.

    ``|``-separated columns, a ``-+-`` divider, left-aligned, widths sized to the
    content. *wrap_columns* maps a column name to a target width; long free text
    wraps onto extra lines within the same table row. Wrapping never breaks
    inside a word, so a long code or rule name overflows its target width rather
    than being mangled. An empty frame renders as ``(empty)``.
    """

    if table.empty:
        return "(empty)"

    wrap = wrap_columns or {}
    headers = [str(c) for c in table.columns]
    cells: list[list[list[str]]] = []
    for _, row in table.iterrows():
        rendered: list[list[str]] = []
        for column in table.columns:
            cell = row[column]
            text = "" if cell is None or is_null(cell) else str(cell)
            width = wrap.get(str(column))
            if width:
                lines = textwrap.wrap(text, width, break_long_words=False, break_on_hyphens=False) or [""]
            else:
                lines = [text]
            rendered.append(lines)
        cells.append(rendered)

    widths = [
        max([len(headers[i])] + [len(line) for row_cells in cells for line in row_cells[i]])
        for i in range(len(headers))
    ]

    out = [" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    out.append("-+-".join("-" * w for w in widths))
    for row_cells in cells:
        height = max(len(lines) for lines in row_cells)
        for line_index in range(height):
            parts = []
            for i, lines in enumerate(row_cells):
                text = lines[line_index] if line_index < len(lines) else ""
                parts.append(text.ljust(widths[i]))
            out.append(" | ".join(parts))
    return "\n".join(out)
