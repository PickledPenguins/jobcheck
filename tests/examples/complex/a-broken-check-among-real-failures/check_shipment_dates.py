"""Date checks: present, parseable, and delivered no earlier than shipped."""

from datetime import date

from jobcheck import OK, Status, Verdict, is_null, register_check


def _date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@register_check("SHIPPED_PRESENT", "Ship date is missing")
def shipped_present(row):
    return Verdict(Status.MISSING) if is_null(row["shipped"]) else OK


@register_check("SHIPPED_NOT_A_DATE", "Ship date is not a YYYY-MM-DD date",
                depends_on=["SHIPPED_PRESENT"])
def shipped_is_a_date(row):
    return OK if _date(row["shipped"]) else Verdict(Status.MALFORMED, {"value": row["shipped"]})


@register_check("DELIVERED_BEFORE_SHIPPED", "Delivered before it was shipped",
                depends_on=["SHIPPED_NOT_A_DATE"])
def delivered_after_shipped(row):
    delivered = _date(row["delivered"])
    if delivered is not None and delivered < _date(row["shipped"]):
        return Verdict(Status.INVALID, {"shipped": row["shipped"], "delivered": row["delivered"]})
    return OK
