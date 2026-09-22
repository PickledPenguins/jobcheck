# Internal accounts exempted

One rule, on its own, applied to a real export: the rows it exempts simply stop being
reported. Row 1018's address is `load-test@@internal.test`, two `@` signs, so
`EMAIL_MISSING_AT` fails on it — and the rule matching `@internal\.test$` switches that
check off for the row. The email rule file is used rather than the shipped
`error_overrides.yaml` so that the exemption is the only thing in force: diff this output
against `data/no-rules-at-all`, which runs the same file with `--rules` and no paths, and
row 1018's failure is the one line that differs.

Level:    simple
Input:    `examples/data/customers.csv` with `examples/rules/split_by_topic/02_email_rules.yaml`
Expected: no email failures for the `internal.test` rows — row 1018's `EMAIL_MISSING_AT`,
          reported without the rule file, is absent here; exit 0
