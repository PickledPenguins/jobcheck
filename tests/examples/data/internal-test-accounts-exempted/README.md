# Internal test accounts exempted

The shipped rule file switches the email tests off for `@internal.test`
addresses. Two rows in the file are QA accounts, and the summary shows the
exemption as `disabled` rather than as a pass.

Level:    moderate
Input:    `examples/data/customers.csv` with `examples/rules/error_overrides.yaml`
Expected: `EMAIL_MISSING_AT` and `EMAIL_DOMAIN_INVALID` disabled on 2 rows; exit 0
