"""A check whose prerequisite lives in the other bundle."""

from jobcheck import OK, Verdict, Status, register_check


@register_check("TOTAL_IS_A_NUMBER", "Total is not a number",
                depends_on=["TOTAL_PRESENT"])
def total_is_a_number(row):
    try:
        float(row["total"])
    except (TypeError, ValueError):
        return Verdict(Status.MALFORMED, {"total": row.get("total")})
    return OK
