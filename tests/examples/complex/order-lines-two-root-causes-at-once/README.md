# Order lines: a chain of checks across three files

A case with its own checks: presence, then shape, then a line total that waits on three shape checks, all three in a file the setup names after it -- the graph is checked once the whole load returns. One row has two blank fields and two root causes at the same layer; another has an unrelated deeper failure that is not a root cause, because root cause means the shallowest failing layer of the row. A rule excuses promotional lines from the total check.

Level:    complex
Input:    `run.yaml` naming `setup.yaml` (three check files and `promo_rules.yaml`) and `orders.csv` (nine lines)
Expected: the registry with `TOTAL_MISMATCH` on layer 2 under three prerequisites, a report keyed by `id` with `sku` beside it, and the summary; exit 0
