# A bundle naming a member that is not there

One mistake, one message. The bundle resolves its members against its own
directory, so the error names the absolute path it looked at rather than the
`check_absent.py` the bundle wrote.

Nothing of the bundle is left behind: `check_line_items.py` loaded first and keeps
its check, the bundle itself is not recorded as loaded, and fixing the name and
running again loads it.

Input:    `tests/failures/bundle-member-missing/bundle_with_missing_member.py`, whose second member does not exist
Expected: exit 1 with a `ValueError` naming the missing member's resolved path
