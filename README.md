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
  `./tests/run-tests.sh fast`.

## Writing a check

```python
from jobcheck import PASS, Status, CheckResult, register_check

@register_check("AGE_ABOVE_LIMIT", "Age is above the limit for this product",
                depends_on=["AGE_PRESENT"])       # waits for that check to pass
def age_above_limit(row):                         # or (row, ctx)
    if row["age"] > 130:
        return CheckResult(Status.INVALID, {"maximum": 130, "actual": row["age"]})
    return PASS
```

- That is the whole change: a function in any `check_*.py` file of your own.
- The check reads whatever columns it needs from the row.
- It returns `PASS` or a `CheckResult`; `CheckResult(condition)` wraps a bare comparison.
- The comments it attaches appear in the report.

## Validating and reporting

```python
import pandas as pd
from jobcheck import build_report, load_checks, print_report, validate

# Your checks live in your own files; this package ships none.
load_checks(["examples/checks/check_age.py", "examples/checks/check_email.py"])

df = pd.DataFrame([
    {"id": 102, "age": -5, "email": "a@b.com", "start_date": "2024-01-01", "end_date": "2024-02-01"},
    {"id": 103, "age": 30, "email": "nope", "start_date": "2024-01-01", "end_date": "2024-02-01"},
    {"id": 104, "age": None, "email": "c@d.com", "start_date": "2024-01-01", "end_date": "2024-02-01"},
])
outcomes = validate(df)                      # add overrides=... to apply rule files
print_report(build_report(outcomes, df=df, key_column="id"))
```

```
row | code             | status        | layer | outcome | message          | detail | comments               | is_root_cause
----+------------------+---------------+-------+---------+------------------+--------+------------------------+--------------
102 | AGE_NEGATIVE     | INVALID (3)   | 2     | failed  | Age is negative  |        | minimum=0; value=-5.0  | True         
103 | EMAIL_MISSING_AT | MALFORMED (2) | 1     | failed  | Email has no '@' |        | at_signs=0; value=nope | True         
104 | AGE_PRESENT      | MISSING (1)   | 0     | failed  | Age is missing   |        |                        | True         
```

- One line per failure, not one per row.
- `write_report(report, "report.csv")` saves it; `render_report(report, fmt="csv")`
  returns the text.
- `extra_columns=[...]` adds columns from the frame next to the row key.

Row 104 reports only `AGE_PRESENT` — the four age checks below it never ran. To see
why a check did not fire, ask about the row:

```python
from jobcheck import explain_row, print_row_explanation

print_row_explanation(explain_row(df.loc[2]), include="blocked")
```

```
layer | code             | outcome  | status      | detail                                     
------+------------------+----------+-------------+--------------------------------------------
0     | AGE_PRESENT      | failed   | MISSING (1) | Age is missing                             
1     | AGE_NOT_A_NUMBER | skipped  | PASS (0)    | prerequisite did not pass: AGE_PRESENT     
2     | AGE_NEGATIVE     | skipped  | PASS (0)    | prerequisite did not pass: AGE_NOT_A_NUMBER
2     | AGE_TOO_HIGH     | skipped  | PASS (0)    | prerequisite did not pass: AGE_NOT_A_NUMBER
2     | AGE_NOT_INTEGER  | disabled | PASS (0)    | disabled by off by default                 
root cause: AGE_PRESENT
```

`include="blocked"` drops the checks that passed; the default `"all"` shows every one,
which is the full audit view.

## Counting what happened

`summarize_outcomes` counts what each check did across every row, and
`print_summary` prints that together with the root cause of each failing row.

```python
from jobcheck import print_summary

print_summary(outcomes)
```

```
code                 | layer | failed | errored | skipped | disabled | passed
---------------------+-------+--------+---------+---------+----------+-------
AGE_NEGATIVE         | 2     | 1      | 0       | 1       | 0        | 1     
AGE_PRESENT          | 0     | 1      | 0       | 0       | 0        | 2     
EMAIL_MISSING_AT     | 1     | 1      | 0       | 0       | 0        | 2     
AGE_NOT_A_NUMBER     | 1     | 0      | 0       | 1       | 0        | 2     
AGE_TOO_HIGH         | 2     | 0      | 0       | 1       | 0        | 2     
EMAIL_DOMAIN_INVALID | 2     | 0      | 0       | 1       | 0        | 2     
AGE_NOT_INTEGER      | 2     | 0      | 0       | 0       | 3        | 0     
EMAIL_PRESENT        | 0     | 0      | 0       | 0       | 0        | 3     

Root cause of each failing row:
root_cause       | rows
-----------------+-----
AGE_NEGATIVE     | 1   
AGE_PRESENT      | 1   
EMAIL_MISSING_AT | 1   
```

Checks are loaded by path: `load_checks(paths)` imports the named `.py` files —
what a pipeline that writes check files into a run directory needs — and nothing
is discovered. `load_overrides(paths)` reads the rule files the same way, in the
order given, so the last matching rule wins.

For a frame too large to keep every outcome, call `validate_row(row)` per row
instead: it returns that row's failures and allocates nothing for the rest.

## Documentation

- [docs/writing-checks.md](docs/writing-checks.md) — the check function, statuses,
  comments, and how checks depend on each other. Start here.
- [docs/reporting.md](docs/reporting.md) — the report, explanations, summaries,
  formats and files.
- [docs/configuration.md](docs/configuration.md) — override rules: switching
  checks on or off for specific rows.
- [docs/interfaces.md](docs/interfaces.md) — the Python API: every exported name,
  signature, return shape, and error raised.
- [docs/cli.md](docs/cli.md) — the demo entry point and its flags, including
  `--data` for validating a CSV file of your own.
- [docs/architecture.md](docs/architecture.md) — module responsibilities, design
  decisions, and how to extend.
- [docs/testing.md](docs/testing.md) — the suites, the gates, coverage, mutation,
  the performance baseline, and the 59-case example and failure catalogs.
- [docs/contributing.md](docs/contributing.md) — where a change goes, and which
  check enforces which rule.
- [docs/future-work.md](docs/future-work.md) — known gaps, and what was
  considered and deliberately not done.
