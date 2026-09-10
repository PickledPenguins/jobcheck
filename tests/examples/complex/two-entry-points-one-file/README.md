# Two entry points, one registry

The second entry point loads only `hard_tests` and validates its own frame. Run
it after any of the `main.py` cases: nothing from those runs is registered here,
because the registry is per process and each entry point chooses its own suites.

Level:    complex
Input:    no options; `main_hard_only.py` builds its own two-row frame
Expected: a registry holding only base and hard_tests tests, and two rows' results; exit 0

Why this combination:

Every other case exercises one entry point. This one exercises the boundary
between two: a shared library with process-global state, where the guarantee is
that loading suites in one program says nothing about another.
