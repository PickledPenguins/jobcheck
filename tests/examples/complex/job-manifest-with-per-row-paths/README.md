# A job manifest checked through per-row paths and a cross-row count

Checks that take `(row, context)`. The builder takes `(row, args)`: it derives each row's run directory and input file once, for every check on that row, and `context_args` carries what the whole run shares -- which jobs write each output, counted once before any row. Neither shipped entry point passes a context builder, so the case carries its own script.

Level:    complex
Input:    `validate_jobs.py` over `jobs.csv` (six jobs) and the `runs/` tree beside it: one run directory missing, one empty input, one input absent, two jobs sharing an output, one output blank
Expected: a report keyed by `id` with `run_dir` beside it, one line per job problem, and the summary; exit 0
