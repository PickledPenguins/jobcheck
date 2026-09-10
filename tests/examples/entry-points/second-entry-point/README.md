# A second entry point choosing its own suites

`main_hard_only.py` hardcodes `load_suites(["hard_tests"])`, so no email check
is registered at all. The base suite still loads.

Level:    simple
Input:    `python3 examples/main_hard_only.py`
Expected: registry without EMAIL codes; row id=1 reports AGE_NOT_INTEGER; exit 0
