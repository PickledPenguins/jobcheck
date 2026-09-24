"""One check, in the first bundle's own directory."""

from jobcheck import OK, Verdict, Status, register_check


@register_check("TOTAL_PRESENT", "Total is missing")
def total_present(row):
    return OK if row.get("total") is not None else Verdict(Status.MISSING)
