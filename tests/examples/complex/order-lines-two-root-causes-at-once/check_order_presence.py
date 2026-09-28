"""Layer 0 for order lines: is each field there at all."""

from jobcheck import OK, Status, Verdict, is_null, register_check


@register_check("QTY_PRESENT", "Quantity is missing")
def qty_present(row):
    return Verdict(Status.MISSING) if is_null(row["qty"]) else OK


@register_check("PRICE_PRESENT", "Unit price is missing")
def price_present(row):
    return Verdict(Status.MISSING) if is_null(row["price"]) else OK


@register_check("TOTAL_PRESENT", "Line total is missing")
def total_present(row):
    return Verdict(Status.MISSING) if is_null(row["total"]) else OK
