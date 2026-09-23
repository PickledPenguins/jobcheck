"""A bundle naming a member that is not there -- the mistake this case records.

`check_line_items.py` sits beside it; `check_absent.py` never existed.
"""

import os

from jobcheck import load_checks

load_checks(["check_line_items.py", "check_absent.py"],
            base_dir=os.path.dirname(os.path.abspath(__file__)))
