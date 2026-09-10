# Several suites in one `-e`

Same result as the default run: the default is exactly these two suites.

Level:    simple
Input:    `python3 examples/main.py -e hard_checks soft_checks`
Expected: base, hard_checks and soft_checks loaded; exit 0
