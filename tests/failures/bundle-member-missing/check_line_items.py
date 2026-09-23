"""The member that does exist, loaded before the one that does not."""

from jobcheck import PASS, CheckResult, Status, register_check


@register_check("LINE_ITEMS_PRESENT", "Line items are missing")
def line_items_present(row):
    return PASS if row.get("line_items") is not None else CheckResult(Status.MISSING)
