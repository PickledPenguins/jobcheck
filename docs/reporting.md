# Reporting

How to turn a validated frame into something a person can act on. Everything
here is library code — collection, the table, the formatting, and writing the
file. There is no command line to learn; a pipeline calls these functions and
decides where the output goes.

Back to the [README](../README.md). The value types are in
[interfaces.md](interfaces.md#data-types).

## The short version

```python
from pandas_row_validation import build_report, collect_outcomes, load_suites, print_report

load_suites(["hard_tests", "soft_tests"])
outcomes = collect_outcomes(df, overrides=overrides)
report = build_report(outcomes, df=df, key_column="id")
print_report(report)                       # or render_report / write_report
```

```
row | code             | status        | layer | suite      | outcome | message              | comments               | is_root_cause
----+------------------+---------------+-------+------------+---------+----------------------+------------------------+--------------
102 | AGE_NEGATIVE     | INVALID (3)   | 2     | hard_tests | failed  | Age is negative      | minimum=0; value=-5.0  | True
103 | EMAIL_MISSING_AT | MALFORMED (2) | 1     | soft_tests | failed  | Email has no '@'     | at_signs=0; value=nope | True
```

## Shape: one row per failure

The report is long format — one line per failed test per data row — not one line
per data row. That is the unit a person diagnoses, it is the only shape that
survives being written as CSV, and it filters and pivots cleanly downstream.

| Column | What it carries |
|---|---|
| `row` | The key of the data row: the `key_column` value(s), or the frame's index. |
| `code` | The permanent test code. |
| `status` | The failure kind, rendered as `INVALID (3)`. |
| `layer` | How deep the test sits in the dependency graph; 0 is fundamental. |
| `suite` | Which suite the test came from. |
| `outcome` | `failed`, `errored`, and `skipped`/`disabled`/`passed` when asked for. |
| `message` | The test's message — what a person reads first. |
| `comments` | What the test attached, rendered `key=value; key=value`, sorted. |
| `is_root_cause` | True for that row's shallowest failure — the lowest layer, evaluation order breaking a tie. |

## Identifying rows

`key_column="id"` names the column that identifies a data row; pass a list for a
composite key and the parts are joined with `|`. Without it the frame's index is
used, which is fine until the frame has been filtered and the index no longer
means anything.

Two conveniences: an integer key column that pandas widened to float still reads
as `102`, not `102.0`, and a row whose key is missing reads `<no key>` rather
than `nan`.

## Showing data alongside the failures

`data_columns` copies fields from the frame into the report, in the order given,
immediately after `row`:

```python
build_report(outcomes, df=df, key_column="id",
             data_columns=["source_system", "record_type", "age"])
```

```
row | source_system | record_type | age | code         | status      | ...
----+---------------+-------------+-----+--------------+-------------+----
102 | MODERN        | BATCH       | -5  | AGE_NEGATIVE | INVALID (3) | ...
```

They carry the context a reader needs to judge a failure without going back to
the source file -- which system sent the row, which batch it arrived in, the
field the test was reading. The value repeats on every failure of that row, which
is what makes the CSV pivot cleanly.

Values render like the row key: a whole float loses its `.0`, and a missing value
is blank. A name that is not in the frame, named twice, or colliding with one of
the report's own column names is refused rather than quietly dropped or
overwriting the report's own data.

## Diagnosing one row

```python
from pandas_row_validation import explain_row, print_row_explanation

print_row_explanation(explain_row(row, overrides=overrides))
```

```
layer | code                 | outcome  | status      | detail
------+----------------------+----------+-------------+-------------------------------------------
0     | AGE_PRESENT          | failed   | MISSING (1) | Age is missing
1     | AGE_NOT_A_NUMBER     | skipped  | PASS (0)    | prerequisite did not pass: AGE_PRESENT
2     | AGE_IN_RANGE         | skipped  | PASS (0)    | prerequisite did not pass: AGE_PRESENT, ...
2     | AGE_NOT_INTEGER      | disabled | PASS (0)    | disabled by rule 'whole_ages_for_legacy'
root cause: AGE_PRESENT
```

Reading order is evaluation order, so every `skipped` line names what blocked it.
The root cause printed at the end is the row's **shallowest** failure: every
failure shown is already the root of its own chain — a test only runs once its
prerequisites passed — so when a row breaks in two chains that never touch,
neither is upstream of the other and the shallower one is the one to read
first. `only_relevant=True` drops
the tests that simply passed.

## Diagnosing a whole file

```python
from pandas_row_validation import print_summary
print_summary(outcomes)
```

Per test: `failed`, `errored`, `skipped`, `disabled`, `passed`, worst first, then
a tally of what each failing row bottomed out at.

Read it this way: a high `failed` count is a data problem; a high `skipped` count
is a *layering* signal — some fundamental test is failing often and hiding
everything below it, so fix that code first; any `errored` count at all is a
broken test, not bad data.

## Opening the CSV in a spreadsheet

Comments carry values that came from the data, and a spreadsheet runs any cell
starting with `=`, `+`, `@`, a tab or a carriage return as a formula. CSV output
therefore prefixes such a cell with an apostrophe, which makes it display as
text — the standard neutraliser. A negative number keeps its minus sign.

Nothing is escaped in the table view, which cannot execute anything, and the
outcomes themselves always hold the value the test actually saw. Pass
`escape_formulas=False` to `render_report` or `write_report` when the CSV feeds
another program and the exact bytes matter.

## Formats and files

```python
render_report(report)                       # bordered text, message and comments wrapped
render_report(report, fmt="csv")            # same columns, unwrapped
write_report(report, "report.csv")          # csv by default
write_report(report, "report.txt", fmt="table")
```

`render_report` returns a string, so anything else — a log line, an email body, a
cell in a notebook — is the caller's choice. `fmt` is validated: anything but
`table` or `csv` raises.

## What to include

By default the report carries failures and errors only. Two switches widen it:

- `include_skipped=True` adds the tests a failure blocked, each naming its
  prerequisite in `comments`. Use it when the question is "why did nothing
  fire?".
- `include_passed=True` adds everything else, turning the report into a full
  audit trail of every test against every row.

## Cost

`collect_outcomes` keeps one object per test per row, because that is what the
explanation and summary views are built from. For a frame large enough that this
matters, call `validate_row` per row instead and skip the report: it returns only
the failures and allocates nothing for the tests that passed.
