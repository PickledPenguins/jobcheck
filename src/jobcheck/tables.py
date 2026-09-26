"""Plain-text and CSV rendering, shared by every table the package builds.

`DataFrame.to_string()` is cramped and unbordered for auditing, and a table
library would be a runtime dependency for formatting alone.

`render` and `is_null` are the public part. The underscored helpers are shared
with `report.py`, `rules.py` and `registry_tables.py` -- how every table renders a
cell and rejects a bad column name the same way -- and are not for callers.
"""

from __future__ import annotations

import re
import textwrap
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


def _keep_columns(base: list[str], drop_columns: list[str] | None, subject: str) -> list[str]:
    """`base` without the names `drop_columns` asks to remove.

    The inverse of `add_columns`, and validated the same way: a name that is not
    there, or asked for twice, is refused rather than ignored, because a caller
    dropping `comment` and getting `comments` anyway would read the table as
    proof the column is empty.

    Only the table's own columns can be dropped. Dropping one that `add_columns`
    put there is spelled by not adding it, and a caller who does both has said two
    things about one column.
    """

    requested = list(drop_columns or [])
    unusable = sorted(
        {name for name in requested if name not in base or requested.count(name) > 1}
    )
    if unusable:
        raise ValueError(
            f"drop_columns {unusable} cannot be used for {subject}. Each name must be "
            f"asked for once and be one of: {', '.join(base) or '(none to drop)'}."
        )
    return [name for name in base if name not in requested]


# The breaks a terminal acts on. Not `str.splitlines`, which also splits on
# \x0b, \x1c and   -- characters that draw as nothing, so a cell would go
# tall for no visible reason.
_LINE_BREAKS = re.compile(r"\r\n|[\r\n\f]")


def _cell_lines(value: Any, width: int | None) -> list[str]:
    """One cell as the lines it occupies. Wrapping never breaks inside a word, so
    a long code or rule name overflows its width rather than being mangled.

    A value holding its own line breaks renders as a tall cell rather than
    breaking the row: the renderer pads with `len()`, so a cell that emits a
    newline of its own slides every column after it. Tabs are expanded for the
    same reason -- `len()` counts one character where a terminal draws eight.
    """

    text = "" if value is None or is_null(value) else str(value)
    segments = [segment.expandtabs() for segment in _LINE_BREAKS.split(text)]
    if width is None:
        return segments
    return [
        line
        for segment in segments
        for line in (textwrap.wrap(segment, width, break_long_words=False,
                                   break_on_hyphens=False) or [""])
    ]


def _padded_line(texts: list[str], widths: list[int]) -> str:
    """One rendered line: every text padded out to its own column's width."""

    return " | ".join(text.ljust(width) for text, width in zip(texts, widths))


def _format_table(table: pd.DataFrame, wrap_columns: dict[str, int] | None = None) -> str:
    """Render a DataFrame as a bordered plain-text table using only the stdlib.

    ``|``-separated columns, a ``-+-`` divider, left-aligned, widths sized to the
    content. *wrap_columns* maps a column name to a target width; long free text
    wraps onto extra lines within the same table row. An empty frame renders as
    ``(empty)``.

    Rendering is two passes, because a column's width is not known until every
    cell in it has been wrapped.
    """

    wrap = wrap_columns or {}
    if table.empty:
        return "(empty)"

    headers = [str(column) for column in table.columns]

    # First pass: wrap every cell. rows[r][c] is the list of lines that column c
    # occupies in row r -- one line for most cells, several for a wrapped one.
    # Read by position, not label: a duplicated label would hand back a Series
    # and print its repr in every cell. And not through iterrows, which upcasts a
    # whole row to float when every column is numeric, printing `1` as `1.0`.
    rows: list[list[list[str]]] = []
    for values in table.itertuples(index=False, name=None):
        rows.append([_cell_lines(value, wrap.get(header))
                     for value, header in zip(values, headers)])

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


# A spreadsheet treats a cell starting with one of these as a formula, so a value
# taken from the data and written into a CSV can execute when someone opens it.
# Escaping happens on the way out, so the tables keep the value the check saw.
_FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")

#: How wide each long free-text column wraps, by name, whichever table holds it.
_WRAP_WIDTHS = {"message": 40, "detail": 48, "comments": 48, "match": 44, "codes": 40,
                "could_be_overridden_by": 34, "effective_state": 34}


def _looks_numeric(text: str) -> bool:
    """Whether a string is just a number, so a leading ``-`` is a minus sign."""

    try:
        float(text)
    except ValueError:
        return False
    return True


def _escape_for_spreadsheet(value: Any) -> Any:
    """Prefix a cell a spreadsheet would run as a formula with an apostrophe, so
    a value such as `=cmd|'/c calc'!A1` displays as text instead of executing. A
    negative number keeps its minus sign."""

    if not isinstance(value, str) or not value:
        return value
    if value[0] in _FORMULA_PREFIXES or (value[0] == "-" and not _looks_numeric(value)):
        return "'" + value
    return value


def render(table: pd.DataFrame, fmt: str = "table") -> str:
    """Any table as text: bordered for a terminal (`"table"`) or CSV (`"csv"`).

    Every table this package builds carries its title in `table.attrs["title"]`,
    and the bordered form opens with it as `== Title ==`, so tables printed one
    after another stay apart. A frame of your own gets one by setting that key.
    CSV gets no heading -- a line above it would break the file -- and any cell
    or column name a spreadsheet would run as a formula is escaped.
    """

    if fmt == "table":
        body = _format_table(table, wrap_columns=_WRAP_WIDTHS)
        title = table.attrs.get("title")
        return f"== {title} ==\n{body}" if title else body
    if fmt == "csv":
        # Headings too: an add_columns name comes from the data's own columns.
        escaped = table.map(_escape_for_spreadsheet)
        escaped.columns = [_escape_for_spreadsheet(str(name)) for name in escaped.columns]
        return escaped.to_csv(index=False)
    raise ValueError(f"fmt must be 'table' or 'csv', got {fmt!r}.")
