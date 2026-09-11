# A clean file under every rule file

Every rule file at once against a file with nothing wrong.

Level:    moderate
Input:    `examples/data/customers_clean.csv` with all four rule files
Expected: still no failures: rules change which checks run, never whether the data is good
