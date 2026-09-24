# No rule files at all

The baseline every rule file is a deviation from: the checks as their authors wrote them, with nothing switched on or off for anybody.

Level:    simple
Input:    `examples/data/customers.csv` with `--rules` and no paths
Expected: every check at its default state; `AGE_NOT_INTEGER`, off by default, never
          reported; row 1018 reported for `EMAIL_MISSING_AT`, which the shipped rule file
          would have exempted (`rules/internal-test-accounts-exempted` is the same run
          with it); exit 0
