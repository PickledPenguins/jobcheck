# Columns beside the key

`--data-columns` copies columns from the file into the report, next to the row
key, so a reader does not have to go back to the data to know what failed.

Level:    simple
Input:    `examples/data/customers.csv`
Expected: the failure table with `name` and `region` after `row`; exit 0
