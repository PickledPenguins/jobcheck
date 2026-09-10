# Skipped tests on a real file

`--include-skipped` adds the tests a failure blocked, each naming the
prerequisite that stopped it. This is the layering made visible.

Level:    simple
Input:    `examples/data/customers.csv`
Expected: failures plus `skipped` lines naming their prerequisite; exit 0
