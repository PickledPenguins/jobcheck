"""A bundle: the four example check files, behind one path.

An entry point that wants all of them names this file instead of listing them,
and a file added here reaches every entry point that already loads it. The
members are loaded files in their own right -- each check's `source_file` is its
member, not this bundle -- so nothing about the registry changes.

`examples/main.py` deliberately does not use it: naming the four is the shape a
first reader should meet. `examples/bundle_main.py` loads this and nothing else.
"""

from __future__ import annotations

import os

from jobcheck import load_checks

HERE = os.path.dirname(os.path.abspath(__file__))

load_checks(
    ["check_row_shape.py", "check_age.py", "check_dates.py", "check_email.py"],
    base_dir=HERE,
)
