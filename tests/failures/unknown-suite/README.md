# Flavor subpackage does not exist

Input:    `python3 examples/main.py -e nope_tests`
Expected: stderr `ValueError: Unknown suite 'nope_tests': expected a subpackage 'validation.nope_tests' (directory validation/nope_tests/ containing an __init__.py)`; exit 1
