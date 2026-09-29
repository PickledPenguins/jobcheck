# One job row, many run directories, each checked as a run of its own

A job's row names a base directory `base` and a run count `v`; its run directories are `base`, `base2`, ... `base{v}`, and how many there are is known only from the data. The script expands the frame to one row per run before `validate`, keyed `J2#3`, so each run gets its own report lines, its own dependency chain (INPUT_EXISTS on run 3 depends on RUN_DIR_EXISTS on run 3 only) and its own rule matches. Nothing in the library does the expanding.

The checks on `base` and `v` hold for the whole job. The expansion gives a job with an unusable `base` or `v` one row, so their failures appear once (J4, J5). OWNER_PRESENT also holds for the whole job, and would repeat on every run: a rule on the `instance` column turns it off past run 1. A second rule turns off one run of one job by its key (J3#2), which skips that run's INPUT_EXISTS too; the summary counts it as disabled.

Level:    complex
Input:    `validate_runs.py` over `jobs.csv` (five jobs, nine runs), `rules.yaml` and the `runs/` tree beside them: one run directory missing, one run without its input, one owner blank, one count of 0, one base blank, one run switched off by a rule
Expected: a report keyed by job and run, one line per run problem, and the summary; exit 0
