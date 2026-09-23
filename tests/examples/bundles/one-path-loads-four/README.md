# One path loads four check files

A bundle is a check file that loads check files. The entry point names `examples/checks/all_checks.py` and nothing else; the four it collects are loaded files in their own right, and they finish before it.

Level:    simple
Input:    `examples/checks/all_checks.py`, the shipped bundle
Expected: the four members then the bundle in the loaded list, and the registry they built; exit 0
