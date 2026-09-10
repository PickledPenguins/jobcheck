"""Always-on tests.

This file sits directly in the ``validation`` package rather than in a suite
subpackage, so it belongs to the base suite and is loaded by every
``load_suites(...)`` call, whatever suites were requested.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pandas_row_validation.results import PASS, Status, TestResult
from pandas_row_validation.registry import register_test


@register_test(
    code="ROW_ALL_NULL",
    message="Row is entirely empty",
    description="A row with no populated field at all is never valid input.",
)
def row_not_all_null(row: "pd.Series[Any]") -> TestResult:
    """Pass when at least one field in the row holds a value."""

    if row.notna().any():
        return PASS
    return TestResult(Status.MISSING, {"columns": len(row.index)})
