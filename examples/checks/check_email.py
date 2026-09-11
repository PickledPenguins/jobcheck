"""Checks on the ``email`` column, including a dependent check."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from jobcheck.registry import register_check
from jobcheck.results import PASS, Status, CheckResult

_DOMAIN = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def _text(row: "pd.Series[Any]", column: str = "email") -> str | None:
    """A column as text, or ``None`` when absent or missing."""

    if column not in row.index:
        return None
    value = row[column]
    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return None
    return str(value)


@register_check(code="EMAIL_PRESENT", message="Email is missing")
def email_present(row: "pd.Series[Any]") -> CheckResult:
    """Pass when the row carries an email at all."""

    text = _text(row)
    if text is None or not text.strip():
        return CheckResult(Status.MISSING)
    return PASS


@register_check("EMAIL_MISSING_AT", "Email has no '@'", depends_on=["EMAIL_PRESENT"])
def email_missing_at(row: "pd.Series[Any]") -> CheckResult:
    """Pass when the email contains exactly one '@'."""

    text = _text(row) or ""
    count = text.count("@")
    if count != 1:
        return CheckResult(Status.MALFORMED, {"at_signs": count, "value": text})
    return PASS


@register_check(
    "EMAIL_DOMAIN_INVALID",
    "Email domain looks malformed",
    depends_on=["EMAIL_MISSING_AT"],
)
def email_domain(row: "pd.Series[Any]") -> CheckResult:
    """Pass when the part after '@' looks like a dotted hostname."""

    domain = (_text(row) or "").split("@", 1)[1]
    if not _DOMAIN.match(domain):
        return CheckResult(Status.MALFORMED, {"domain": domain})
    return PASS
