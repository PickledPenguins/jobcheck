# Label rows by a different column

`--key-column` chooses what identifies a row in the report. Anything in the
file will do: a name reads better than a number when a person is chasing it.

Level:    simple
Input:    `examples/data/customers.csv`, keyed by `name`
Expected: the same failures, labelled `Alan Turing` rather than `1004`; exit 0
