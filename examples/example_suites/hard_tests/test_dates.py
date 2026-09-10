"""Cross-column date tests."""

from __future__ import annotations

from typing import Any

import pandas as pd

from pandas_row_validation.registry import register_test, test_group
from pandas_row_validation.results import PASS, Status, TestResult


def _date(row: "pd.Series[Any]", column: str) -> pd.Timestamp | None:
    """A column as a timestamp, or ``None`` when absent, missing or unparseable."""

    if column not in row.index:
        return None
    value = row[column]
    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


@register_test(
    code="DATES_PRESENT",
    message="Both start_date and end_date are needed",
    description="The presence test the ordering test waits for.",
)
def dates_present(row: "pd.Series[Any]") -> TestResult:
    """Pass when both dates are readable."""

    missing = [column for column in ("start_date", "end_date") if _date(row, column) is None]
    if missing:
        return TestResult(Status.MISSING, {"columns": ", ".join(missing)})
    return PASS


dates = test_group(depends_on=["DATES_PRESENT"])


@dates(
    "DATES_OUT_OF_ORDER",
    "start_date is after end_date",
    description="A test weighing two columns together, which is why tests are given "
    "the whole row rather than one value.",
)
def dates_in_order(row: "pd.Series[Any]") -> TestResult:
    """Pass when start_date is not later than end_date."""

    start = _date(row, "start_date")
    end = _date(row, "end_date")
    if start is not None and end is not None and start > end:
        return TestResult(Status.INVALID, {"start_date": start.date(), "end_date": end.date()})
    return PASS
