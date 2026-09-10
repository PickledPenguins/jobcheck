"""Tests on the ``email`` column, including a dependent test."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from pandas_row_validation.registry import register_test, test_group
from pandas_row_validation.results import PASS, Status, TestResult

_DOMAIN = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def _text(row: "pd.Series[Any]", column: str = "email") -> str | None:
    """A column as text, or ``None`` when absent or missing."""

    if column not in row.index:
        return None
    value = row[column]
    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return None
    return str(value)


@register_test(
    code="EMAIL_PRESENT",
    message="Email is missing",
    description="The presence test the rest of the email tests wait for.",
)
def email_present(row: "pd.Series[Any]") -> TestResult:
    """Pass when the row carries an email at all."""

    text = _text(row)
    if text is None or not text.strip():
        return TestResult(Status.MISSING)
    return PASS


email = test_group(depends_on=["EMAIL_PRESENT"])


@email(
    "EMAIL_MISSING_AT",
    "Email has no '@'",
    description="The most basic email shape test; the domain test depends on it.",
)
def email_missing_at(row: "pd.Series[Any]") -> TestResult:
    """Pass when the email contains exactly one '@'."""

    text = _text(row) or ""
    count = text.count("@")
    if count != 1:
        return TestResult(Status.MALFORMED, {"at_signs": count, "value": text})
    return PASS


@email(
    "EMAIL_DOMAIN_INVALID",
    "Email domain looks malformed",
    depends_on=["EMAIL_MISSING_AT"],
    description="Only checked once EMAIL_MISSING_AT passed: reporting a malformed "
    "domain on a string with no '@' is redundant noise on top of a more "
    "fundamental problem already reported.",
)
def email_domain(row: "pd.Series[Any]") -> TestResult:
    """Pass when the part after '@' looks like a dotted hostname."""

    domain = (_text(row) or "").split("@", 1)[1]
    if not _DOMAIN.match(domain):
        return TestResult(Status.MALFORMED, {"domain": domain})
    return PASS
