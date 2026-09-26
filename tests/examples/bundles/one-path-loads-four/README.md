# One path loads four check files

A bundle is a check file that loads check files. The entry point names `examples/checks/all_checks.py` and nothing else; the four it collects are loaded files in their own right, so each check's `source_file` names its member rather than the bundle.

Level:    simple
Input:    `examples/checks/all_checks.py`, the shipped bundle
Expected: the registry they built, each check's `source_file` naming its member file; exit 0
