# One suite and a rule file together

Suite selection and rule files are independent choices that interact: the rule
file names `AGE_NOT_INTEGER`, which only exists because `hard_checks` is loaded.
Naming a rule for a code from an unloaded suite is an error -- see the failure
catalog.

Level:    moderate
Input:    `examples/data/customers.csv`, `hard_checks`, the age rule file
Expected: age and date failures, with `AGE_NOT_INTEGER` enabled on legacy batch rows; exit 0
