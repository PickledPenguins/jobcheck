"""Cross-column date checks."""

from __future__ import annotations

from typing import Any

import pandas as pd

from jobcheck import PASS, Status, CheckResult, is_null, register_check


def _date(row: "pd.Series[Any]", column: str) -> pd.Timestamp | None:
    """A column as a timestamp, or ``None`` when absent, missing or unparseable."""

    if column not in row.index:
        return None
    value = row[column]
    if is_null(value):
        return None
    # pd.Timestamp, not pd.to_datetime: the scalar to_datetime carries the
    # frame-level machinery and costs ~300x more per cell. Both accept the
    # same strings; this one raises where that one returned NaT.
    try:
        return pd.Timestamp(value)
    except (ValueError, TypeError):
        return None


@register_check(code="DATES_PRESENT", message="Both start_date and end_date are needed")
def dates_present(row: "pd.Series[Any]") -> CheckResult:
    """Pass when both dates are readable."""

    missing = [column for column in ("start_date", "end_date") if _date(row, column) is None]
    if missing:
        return CheckResult(Status.MISSING, {"columns": ", ".join(missing)})
    return PASS


@register_check(
    "DATES_OUT_OF_ORDER",
    "start_date is after end_date",
    depends_on=["DATES_PRESENT"],
)
def dates_in_order(row: "pd.Series[Any]") -> CheckResult:
    """Pass when start_date is not later than end_date."""

    start = _date(row, "start_date")
    end = _date(row, "end_date")
    if start is not None and end is not None and start > end:
        return CheckResult(Status.INVALID, {"start_date": start.date(), "end_date": end.date()})
    return PASS
