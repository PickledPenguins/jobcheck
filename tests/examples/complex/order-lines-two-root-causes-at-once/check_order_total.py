"""Layer 2: the line total agrees with quantity times price.

Three prerequisites, all three in `check_order_numbers.py`, which the setup
names *after* this one: the graph is checked once the whole load returns, so the
order of the files does not matter.
"""

from jobcheck import OK, Status, Verdict, register_check


@register_check("TOTAL_MISMATCH", "Line total is not quantity times unit price",
                depends_on=["QTY_NOT_A_NUMBER", "PRICE_NOT_A_NUMBER", "TOTAL_NOT_A_NUMBER"])
def total_matches(row):
    expected = round(float(row["qty"]) * float(row["price"]), 2)
    actual = round(float(row["total"]), 2)
    if expected != actual:
        return Verdict(Status.INVALID, {"expected": expected, "actual": actual})
    return OK
