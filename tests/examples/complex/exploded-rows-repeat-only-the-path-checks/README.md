# Exploded rows: repeat only the path checks, share the rest

A job's `basedirname` lists its run directories, `alpha,alpha,beta`, and how many there are is known only from the data. The script explodes the list to one row per name, every other column copied, and numbers a repeated name in `dirname` (`alpha`, `alpha2`, `beta`). `validate(repeat_key="id")` treats rows sharing an `id` as copies of one job.

BASE_EXISTS is registered with `repeat=True`, so it runs on every copy, and CHILD_EXISTS repeats because it depends on it: each directory's child is checked only when that directory exists (J2's `gamma2`). NAMES_PRESENT and VAL_IN_RANGE are about the job, so they run on its first copy and the other copies record them as `shared`: J2's out-of-range `val` is one failure, not two. A rule matching `dirname` turns off BASE_EXISTS on one copy of one job (J5's `eps2`), which skips its CHILD_EXISTS too. The last table explains J2's second copy: what ran there, and what it shares.

Level:    complex
Input:    `validate_runs.py` over `jobs.csv` (five jobs, nine copies), `rules.yaml` and the `runs/` tree beside them: one run directory missing, one child missing, one `val` out of range, one job listing no directories, one copy switched off by a rule
Expected: a report keyed by `id` with `dirname` beside it, one line per failure where the check ran, the summary with its `shared` column, and one copy's explanation; exit 0
