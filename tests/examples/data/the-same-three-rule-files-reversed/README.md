# The same three files, reversed

The same three files in the opposite order. The legacy enable now comes last,
so it wins on the rows it matches and the global disable holds everywhere else.
Read this beside `three-rule-files-in-order`: one flag order changed the answer.

Level:    moderate
Input:    `examples/data/customers.csv` with the three rule files reversed
Expected: `AGE_NOT_INTEGER` enabled on the legacy batch rows only; exit 0
