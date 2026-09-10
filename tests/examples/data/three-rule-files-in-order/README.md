# Three rule files, in order

Precedence is positional: the last rule that matches a row wins. The global
disable is listed last, so it beats the legacy enable in the first file.

Level:    moderate
Input:    `examples/data/customers.csv` with three rule files from two directories
Expected: `AGE_NOT_INTEGER` disabled on every row despite the earlier enable; exit 0
