# One suite on a real file

Loading only `hard_tests`: the email tests never register, so nothing in the
report mentions them. The rule file has to change with the suite -- the default
`error_overrides.yaml` names `EMAIL_*` codes, and a rule naming a code from an
unloaded suite is an error rather than a no-op (see `../../failures/`).

Level:    simple
Input:    `examples/data/customers.csv`, `hard_tests`, the age rule file
Expected: age and date failures only, no `EMAIL_*` codes; exit 0
