"""Carrier checks -- one of them with the bug every check author writes once.

`CARRIER_KNOWN` calls `.upper()` on the cell without asking whether it is blank.
A blank cell arrives as `NaN`, a float, which has no `.upper()`: the check raises
`AttributeError` on exactly the rows it should have reported as missing.
"""

from jobcheck import OK, Status, Verdict, register_check

KNOWN_CARRIERS = {"DHL", "UPS", "FEDEX"}


@register_check("CARRIER_KNOWN", "Carrier is not one we ship with")
def carrier_known(row):
    carrier = row["carrier"].upper()
    if carrier not in KNOWN_CARRIERS:
        return Verdict(Status.INVALID, {"carrier": row["carrier"]})
    return OK


@register_check("TRACKING_MATCHES_CARRIER", "Tracking number does not fit the carrier",
                depends_on=["CARRIER_KNOWN"])
def tracking_matches_carrier(row):
    prefix = {"DHL": "JD", "UPS": "1Z", "FEDEX": "FX"}[row["carrier"].upper()]
    if not str(row["tracking"]).startswith(prefix):
        return Verdict(Status.INVALID, {"expected_prefix": prefix, "tracking": row["tracking"]})
    return OK
