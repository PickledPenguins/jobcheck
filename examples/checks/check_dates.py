"""Cross-column date checks."""

from __future__ import annotations

from typing import Any

import pandas as pd

from jobcheck import OK, Status, Verdict, is_null, register_check

_COLUMNS = ("start_date", "end_date")


def _date(value: Any) -> pd.Timestamp | None:
    """Value as a timestamp, or `None` when it is not a date.

    No missing-value guard: its one caller depends on DATES_PRESENT, so it only
    ever runs on a row that has both dates.
    """
    # pd.Timestamp, not pd.to_datetime: the scalar to_datetime carries the
    # frame-level machinery and costs ~300x more per cell. Both accept the
    # same strings; this one raises where that one returned NaT.
    try:
        return pd.Timestamp(value)
    except (ValueError, TypeError):
        return None


@register_check(code="DATES_PRESENT", message="Both start_date and end_date are needed")
def dates_present(row: "pd.Series[Any]") -> Verdict:
    """Pass when the row carries both dates at all."""
    missing = [column for column in _COLUMNS if column not in row.index or is_null(row[column])]
    if missing:
        return Verdict(Status.MISSING, {"columns": ", ".join(missing)})
    return OK


@register_check("DATES_NOT_A_DATE", "A date cannot be read", depends_on=["DATES_PRESENT"])
def dates_are_dates(row: "pd.Series[Any]") -> Verdict:
    """Pass when both dates can be read as dates."""
    unreadable = {column: row[column] for column in _COLUMNS if _date(row[column]) is None}
    if unreadable:
        return Verdict(Status.MALFORMED, unreadable)
    return OK


@register_check(
    "DATES_OUT_OF_ORDER",
    "start_date is after end_date",
    depends_on=["DATES_NOT_A_DATE"],
)
def dates_in_order(row: "pd.Series[Any]") -> Verdict:
    """Pass when start_date is not later than end_date."""
    start = pd.Timestamp(row["start_date"])
    end = pd.Timestamp(row["end_date"])
    if start > end:
        return Verdict(Status.INVALID, {"start_date": start.date(), "end_date": end.date()})
    return OK
