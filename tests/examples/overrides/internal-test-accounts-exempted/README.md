# Internal accounts exempted

The shipped rule file, applied to a real export: the rows a rule exempts simply stop being
reported. Row 1018's address is `load-test@@internal.test`, two `@` signs, so
`EMAIL_MISSING_AT` fails on it — and the rule matching `@internal\.test$` switches that
check off for the row. Diff this case's output against `data/no-rules-at-all`, which runs
the same file with `--rules` and no paths: the one line that differs is row 1018's
failure. (`--rules` defaults to this very file, so the flag here is explicit rather than
necessary.)

Level:    simple
Input:    `examples/data/customers.csv` with `examples/rules/error_overrides.yaml`
Expected: no email failures for the `internal.test` rows — row 1018's `EMAIL_MISSING_AT`,
          reported without the rule file, is absent here; exit 0
