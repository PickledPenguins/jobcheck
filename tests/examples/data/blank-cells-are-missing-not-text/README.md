# Blank cells are missing, not text

An empty cell in a CSV is a missing value, not the string `nan`. The data
columns show it as empty, and the presence tests are what fire on it.

Level:    simple
Input:    `examples/data/customers.csv`
Expected: `AGE_PRESENT` and `EMAIL_PRESENT` failures with empty data cells; exit 0
