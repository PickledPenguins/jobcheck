"""Checks on the ``age`` column."""

from __future__ import annotations

from typing import Any

import pandas as pd

from jobcheck.registry import register_check
from jobcheck.results import PASS, Status, CheckResult


def _number(value: Any) -> float | None:
    """Value as a float, or ``None`` when it is missing or not numeric."""

    if value is None or not pd.api.types.is_scalar(value) or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@register_check(code="AGE_PRESENT", message="Age is missing")
def age_present(row: "pd.Series[Any]") -> CheckResult:
    """Pass when the row carries an age at all."""

    if "age" not in row.index:
        return CheckResult(Status.MISSING, {"reason": "no age column"})
    value = row["age"]
    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return CheckResult(Status.MISSING)
    return PASS


# Everything below waits for an age to be there: one complaint about a blank
# field instead of one from every check that reads it.
@register_check("AGE_NOT_A_NUMBER", "Age is not a number", depends_on=["AGE_PRESENT"])
def age_is_a_number(row: "pd.Series[Any]") -> CheckResult:
    """Pass when the age can be read as a number."""

    if _number(row["age"]) is None:
        return CheckResult(Status.MALFORMED, {"value": row["age"]})
    return PASS


@register_check("AGE_NEGATIVE", "Age is negative", depends_on=["AGE_NOT_A_NUMBER"])
def age_negative(row: "pd.Series[Any]") -> CheckResult:
    """Pass unless the age is below zero."""

    value = _number(row["age"])
    if value is not None and value < 0:
        return CheckResult(Status.INVALID, {"value": value, "minimum": 0})
    return PASS


@register_check(
    "AGE_TOO_HIGH",
    "Age is implausibly high (over 130)",
    depends_on=["AGE_NOT_A_NUMBER"],
)
def age_too_high(row: "pd.Series[Any]") -> CheckResult:
    """Pass unless the age exceeds 130."""

    value = _number(row["age"])
    if value is not None and value > 130:
        return CheckResult(Status.INVALID, {"value": value, "maximum": 130})
    return PASS


@register_check(
    "AGE_NOT_INTEGER",
    "Age is not a whole number",
    default_enabled=False,
    depends_on=["AGE_NOT_A_NUMBER"],
)
def age_not_integer(row: "pd.Series[Any]") -> CheckResult:
    """Pass unless the age has a fractional part."""

    value = _number(row["age"])
    if value is not None and not value.is_integer():
        return CheckResult(Status.INVALID, {"value": value})
    return PASS
