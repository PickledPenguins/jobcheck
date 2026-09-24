"""The member that does exist, loaded before the one that does not."""

from jobcheck import OK, Verdict, Status, register_check


@register_check("LINE_ITEMS_PRESENT", "Line items are missing")
def line_items_present(row):
    return OK if row.get("line_items") is not None else Verdict(Status.MISSING)
