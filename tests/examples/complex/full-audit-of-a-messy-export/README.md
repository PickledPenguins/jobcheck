# Full audit of a messy export

Everything the entry point can print for the messiest shipped file, under every
rule file at once: the registry, every failure, and the counts. This is the run
an audit actually makes, and the one where no single feature is under test --
the rules interact, and the summary is what shows the result of the interaction.

Level:    complex
Input:    `examples/data/customers.csv` (49 rows, one problem of each kind) under all four rule files
Expected: the registry, one line per failure, then per-check counts and the root
          cause of each failing row; exit 0
