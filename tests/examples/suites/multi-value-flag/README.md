# Several suites in one `-e`

Same result as the default run: the default is exactly these two suites.

Input:    `python3 examples/main.py -e hard_tests soft_tests`
Expected: base, hard_tests and soft_tests loaded; exit 0
