"""A bundle loaded by another bundle: nesting is not limited to one level."""

import os

from jobcheck import load_checks

load_checks(["check_total_is_a_number.py"],
            base_dir=os.path.dirname(os.path.abspath(__file__)))
