"""The outer bundle: one check file of its own, then another bundle.

TOTAL_IS_A_NUMBER, in the inner bundle, depends on TOTAL_PRESENT, in the file
loaded here. Neither bundle validates on its own -- the outermost load_checks
call does, once every file is in -- so the two may be named in either order.
"""

import os

from jobcheck import load_checks

HERE = os.path.dirname(os.path.abspath(__file__))

load_checks(["check_totals.py", "inner_bundle.py"], base_dir=HERE)
