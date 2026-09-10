# jobcheck

Validate rows of a pandas DataFrame with many small, independently named checks.

## What it does

- Each check is a function under a permanent code, reading whatever columns it needs.
- Checks depend on each other, so a blank field produces **one** error, not one from
  every check that reads it, and the shallowest failure is flagged as the root cause.
- Checks return a status and comments, which the report carries: the value seen, the
  limit breached, the count that was wrong.
- Output is a failure table — print it, write it as CSV, or explain one row at a time.
- Adding a check is a function in an existing file: no central list, no renumbering.
- Non-developers switch individual checks on or off for chosen rows with YAML rule files.

Not in scope, deliberately:

- It does not fix, coerce, or drop rows.
- No scheduler, server, or persistence.
- Rule files only switch existing checks on and off; they cannot define new ones.

## Install

- Python 3.10+ (`X | None` syntax throughout).
- pandas 2.1+ (the CSV report uses `DataFrame.map`) and PyYAML.

```sh
git clone <this repo> && cd jobcheck
pip install -e .
```

- Then `import jobcheck`. Running from a clone without installing works
  too: the package lives in `src/`, so put that directory on `PYTHONPATH`.
- To work on it: `pip install -e ".[dev]"`, `./scripts/install-hooks.sh`, then
  `./run-tests.sh fast`.

## Writing a check

```python
from jobcheck import PASS, Status, CheckResult, check_group

age = check_group(depends_on=["AGE_PRESENT"])     # everything here waits for that

@age("AGE_ABOVE_LIMIT", "Age is above the limit for this product")
def age_above_limit(row):                         # or (row, ctx)
    if row["age"] > 130:
        return CheckResult(Status.INVALID, {"maximum": 130, "actual": row["age"]})
    return PASS
```

- That is the whole change: a function in any `check_*.py` file under a suite directory
  of your own package.
- The check reads whatever columns it needs from the row.
- It returns `PASS` or a `CheckResult`; a bare `True`/`False` works too.
- The comments it attaches appear in the report.

## Validating and reporting

```python
import pandas as pd
from jobcheck import build_report, collect_outcomes, load_suites, print_report

# Your checks live in your package; this one ships none.
load_suites(["hard_checks", "soft_checks"], package="example_suites")

df = pd.DataFrame([
    {"id": 102, "age": -5, "email": "a@b.com", "start_date": "2024-01-01", "end_date": "2024-02-01"},
    {"id": 103, "age": 30, "email": "nope", "start_date": "2024-01-01", "end_date": "2024-02-01"},
    {"id": 104, "age": None, "email": "c@d.com", "start_date": "2024-01-01", "end_date": "2024-02-01"},
])
outcomes = collect_outcomes(df)              # add overrides=... to apply rule files
print_report(build_report(outcomes, df=df, key_column="id"))
```

```
row | code             | status        | layer | suite       | outcome | message          | comments               | is_root_cause
----+------------------+---------------+-------+-------------+---------+------------------+------------------------+--------------
102 | AGE_NEGATIVE     | INVALID (3)   | 2     | hard_checks | failed  | Age is negative  | minimum=0; value=-5.0  | True         
103 | EMAIL_MISSING_AT | MALFORMED (2) | 1     | soft_checks | failed  | Email has no '@' | at_signs=0; value=nope | True         
104 | AGE_PRESENT      | MISSING (1)   | 0     | hard_checks | failed  | Age is missing   |                        | True         
```

- One line per failure, not one per row.
- `write_report(report, "report.csv")` saves it; `render_report(report, fmt="csv")`
  returns the text.
- `data_columns=[...]` adds columns from the frame next to the row key.

Row 104 reports only `AGE_PRESENT` — the four age checks below it never ran. To see
why a check did not fire, ask about the row:

```python
from jobcheck import explain_row, print_row_explanation

print_row_explanation(explain_row(df.loc[2]), only_relevant=True)
```

```
layer | code             | outcome  | status      | detail                                                  
------+------------------+----------+-------------+---------------------------------------------------------
0     | AGE_PRESENT      | failed   | MISSING (1) | Age is missing                                          
1     | AGE_NOT_A_NUMBER | skipped  | PASS (0)    | prerequisite did not pass: AGE_PRESENT                  
2     | AGE_NEGATIVE     | skipped  | PASS (0)    | prerequisite did not pass: AGE_PRESENT, AGE_NOT_A_NUMBER
2     | AGE_TOO_HIGH     | skipped  | PASS (0)    | prerequisite did not pass: AGE_PRESENT, AGE_NOT_A_NUMBER
2     | AGE_NOT_INTEGER  | disabled | PASS (0)    | disabled by off by default                              
root cause: AGE_PRESENT
```

`only_relevant=True` drops the checks that passed; without it every check appears,
which is the full audit view.

## The whole frame at once

`validate` runs the frame and hands back one object holding the outcomes, the
frame they came from, and the rules that produced them — so the reporting views
need no second argument.

```python
from jobcheck import validate

run = validate(df)                     # the same arguments as collect_outcomes
print(f"{len(run)} rows, {len(run.failed_rows)} failed, {run.errors} errored")
print(run.root_causes)
```

```
3 rows, 3 failed, 0 errored
['AGE_NEGATIVE', 'EMAIL_MISSING_AT', 'AGE_PRESENT']
```

- `run.report(key_column="id")` and `run.summary()` are the tables above.
- `run.explain(0)` is one row's trace: `.failures`, `.root_cause`, `.records`.
- `iter_traces(df)` yields the same traces one at a time, for a frame whose
  outcomes will not fit in memory.

Checks do not have to live in an importable package. `load_checks(paths)`
imports named `.py` files by path — what a pipeline that writes check files into a
run directory needs — and their checks join the base suite.

## Documentation

- [docs/writing-checks.md](docs/writing-checks.md) — the check function, statuses,
  comments, groups, suites, and how checks depend on each other. Start here.
- [docs/reporting.md](docs/reporting.md) — the report, explanations, summaries,
  formats and files.
- [docs/configuration.md](docs/configuration.md) — override rules: switching
  checks on or off for specific rows.
- [docs/interfaces.md](docs/interfaces.md) — the Python API: every exported name,
  signature, return shape, and error raised.
- [docs/cli.md](docs/cli.md) — the demo entry points and their flags, including
  `--data` for validating a CSV file of your own.
- [docs/architecture.md](docs/architecture.md) — module responsibilities, design
  decisions, and how to extend.
- [docs/testing.md](docs/testing.md) — the suites, the gates, coverage, mutation,
  the performance baseline, and the 66-case example and failure catalogs.
- [docs/contributing.md](docs/contributing.md) — where a change goes, and which
  check enforces which rule.
- [docs/future-work.md](docs/future-work.md) — known gaps, and what was
  considered and deliberately not done.
