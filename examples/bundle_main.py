"""Second demonstration entry point: one bundle file loads the check files.

`examples/main.py` names its four check files itself. This one names a single
path -- a bundle -- and the four arrive behind it. What it prints is the loaded
file list and the registry, because the list is the part a bundle changes: the
members are loaded files in their own right, and they finish before the bundle
that pulled them in.

An argument names a different bundle, which is how the catalog drives it; with
none it loads the shipped `examples/checks/all_checks.py`.
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from jobcheck import load_checks, loaded_check_files, print_registry  # noqa: E402

#: The bundle loaded when the command line names none.
DEFAULT_BUNDLE = os.path.join(PROJECT_ROOT, "examples/checks/all_checks.py")


def main(argv: list[str] | None = None) -> None:
    """Load one bundle and show what came of it."""

    arguments = sys.argv[1:] if argv is None else argv
    bundle = arguments[0] if arguments else DEFAULT_BUNDLE

    load_checks([bundle])

    print("== Loaded ==")
    for path in loaded_check_files():
        print(path)

    print("\n== Registry ==")
    print_registry()


if __name__ == "__main__":
    main()
