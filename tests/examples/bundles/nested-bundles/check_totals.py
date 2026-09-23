"""One check, in the first bundle's own directory."""

from jobcheck import PASS, CheckResult, Status, register_check


@register_check("TOTAL_PRESENT", "Total is missing")
def total_present(row):
    return PASS if row.get("total") is not None else CheckResult(Status.MISSING)
