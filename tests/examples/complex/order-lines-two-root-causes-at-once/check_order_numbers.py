"""Layer 1 and below: each field reads as a number, and a quantity is positive."""

from jobcheck import OK, Status, Verdict, register_check


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@register_check("QTY_NOT_A_NUMBER", "Quantity is not a number", depends_on=["QTY_PRESENT"])
def qty_is_a_number(row):
    if _number(row["qty"]) is None:
        return Verdict(Status.MALFORMED, {"value": row["qty"]})
    return OK


@register_check("PRICE_NOT_A_NUMBER", "Unit price is not a number",
                depends_on=["PRICE_PRESENT"])
def price_is_a_number(row):
    if _number(row["price"]) is None:
        return Verdict(Status.MALFORMED, {"value": row["price"]})
    return OK


@register_check("TOTAL_NOT_A_NUMBER", "Line total is not a number",
                depends_on=["TOTAL_PRESENT"])
def total_is_a_number(row):
    if _number(row["total"]) is None:
        return Verdict(Status.MALFORMED, {"value": row["total"]})
    return OK


@register_check("QTY_NOT_POSITIVE", "Quantity is zero or negative",
                depends_on=["QTY_NOT_A_NUMBER"])
def qty_positive(row):
    qty = float(row["qty"])
    return OK if qty > 0 else Verdict(Status.INVALID, {"value": qty, "minimum": 1})
