# Explain a row under rules

A `disabled` line says which rule decided it, which is what makes a rule file auditable.

Level:    moderate
Input:    row 16 (`1017`, `qa@internal.test`) of `examples/data/customers.csv` under the shipped rule file
Expected: the two email checks `disabled by rule 'suppress_email_checks_for_test_accounts'` and `AGE_NOT_INTEGER` `disabled by rule 'disable_age_integer_check_globally'`; `root cause: none - the row passed`
