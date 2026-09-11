# Reporting

How to turn a validated frame into something a person can act on. Everything
here is library code — collection, the table, the formatting, and writing the
file. There is no command line to learn; a pipeline calls these functions and
decides where the output goes.

Back to the [README](../README.md). The value types are in
[interfaces.md](interfaces.md#data-types).

## The short version

```python
from jobcheck import build_report, load_checks, print_report, validate

load_checks(["examples/checks/check_age.py", "examples/checks/check_email.py"])
outcomes = validate(df, overrides=overrides)
report = build_report(outcomes, df=df, key_column="id")
print_report(report)                       # or render_report / write_report
```

```
row | code             | status        | layer | outcome | message          | detail | comments               | is_root_cause
----+------------------+---------------+-------+---------+------------------+--------+------------------------+--------------
102 | AGE_NEGATIVE     | INVALID (3)   | 2     | failed  | Age is negative  |        | minimum=0; value=-5.0  | True
103 | EMAIL_MISSING_AT | MALFORMED (2) | 1     | failed  | Email has no '@' |        | at_signs=0; value=nope | True
```

## Shape: one row per failure

The report is long format — one line per failed check per data row — not one line
per data row. That is the unit a person diagnoses, it is the only shape that
survives being written as CSV, and it filters and pivots cleanly downstream.

| Column | What it carries |
|---|---|
| `row` | The key of the data row: the `key_column` value, or the frame's index. |
| `code` | The permanent check code. |
| `status` | The failure kind, rendered as `INVALID (3)`. |
| `layer` | How deep the check sits in the dependency graph; 0 is fundamental. |
| `outcome` | `failed`, `errored`, and `skipped`/`disabled`/`passed` when asked for. |
| `message` | The check's message — what a person reads first. Empty for a check that did not evaluate the row. |
| `detail` | Why a check did not evaluate the row: the rule that disabled it, the prerequisites that blocked it, or the exception it raised. Empty for a check that ran. |
| `comments` | What the check attached, rendered `key=value; key=value`, sorted. |
| `is_root_cause` | True for **every** failure at that row's shallowest failing layer. Two failures at the same depth are two root causes: neither is upstream of the other. |

## Identifying rows

`key_column="id"` names the column that identifies a data row — one column, so a
composite key is a column you build first, where you decide how the parts join.
Without it the frame's index is
used, which is fine until the frame has been filtered and the index no longer
means anything.

Two conveniences: an integer key column that pandas widened to float still reads
as `102`, not `102.0`, and a row whose key is missing reads `<no key>` rather
than `nan`.

## Showing data alongside the failures

`extra_columns` copies fields from the frame into the report, in the order given,
immediately after `row`:

```python
build_report(outcomes, df=df, key_column="id",
             extra_columns=["source_system", "record_type", "age"])
```

```
row | source_system | record_type | age | code         | status      | ...
----+---------------+-------------+-----+--------------+-------------+----
102 | MODERN        | BATCH       | -5  | AGE_NEGATIVE | INVALID (3) | ...
```

They carry the context a reader needs to judge a failure without going back to
the source file -- which system sent the row, which batch it arrived in, the
field the check was reading. The value repeats on every failure of that row, which
is what makes the CSV pivot cleanly.

Values render like the row key: a whole float loses its `.0`, and a missing value
is blank. A name that is not in the frame, named twice, or colliding with one of
the report's own column names is refused rather than quietly dropped or
overwriting the report's own data.

## Diagnosing one row

```python
from jobcheck import explain_row, print_row_explanation

print_row_explanation(explain_row(row, overrides=overrides))
```

```
layer | code                 | outcome  | status      | detail
------+----------------------+----------+-------------+-------------------------------------------
0     | AGE_PRESENT          | failed   | MISSING (1) | Age is missing
1     | AGE_NOT_A_NUMBER     | skipped  | PASS (0)    | prerequisite did not pass: AGE_PRESENT
2     | AGE_NEGATIVE         | skipped  | PASS (0)    | prerequisite did not pass: AGE_NOT_A_NUMBER
2     | AGE_NOT_INTEGER      | disabled | PASS (0)    | disabled by rule 'whole_ages_for_legacy'
root cause: AGE_PRESENT
```

Reading order is evaluation order, so every `skipped` line names what blocked it.
The root cause printed at the end is the row's **shallowest** failure, and there
may be more than one — the line reads `root causes:` when a row failed two
chains at the same depth. Every
failure shown is already the root of its own chain — a check only runs once its
prerequisites passed — so when a row breaks in two chains that never touch,
neither is upstream of the other and the shallower one is the one to read
first. `include="blocked"` drops
the checks that simply passed.

## Diagnosing a whole file

```python
from jobcheck import print_summary
print_summary(outcomes)
```

Per check: `failed`, `errored`, `skipped`, `disabled`, `passed`, worst first, then
a tally of what each failing row bottomed out at.

Read it this way: a high `failed` count is a data problem; a high `skipped` count
is a *layering* signal — some fundamental check is failing often and hiding
everything below it, so fix that code first; any `errored` count at all is a
broken check, not bad data.

## Opening the CSV in a spreadsheet

Comments carry values that came from the data, and a spreadsheet runs any cell
starting with `=`, `+`, `@`, a tab or a carriage return as a formula. CSV output
therefore prefixes such a cell with an apostrophe, which makes it display as
text — the standard neutralizer. A negative number keeps its minus sign.

Nothing is escaped in the table view, which cannot execute anything, and the
outcomes themselves always hold the value the check actually saw. There is no
switch for it: a report is written to be opened by a person, and a CSV that can
execute on open is not one.

## Formats and files

```python
render_report(report)                       # bordered text; message, detail and comments wrapped
render_report(report, fmt="csv")            # same columns, unwrapped
write_report(report, "report.csv")          # csv by default
write_report(report, "report.txt", fmt="table")
```

`render_report` returns a string, so anything else — a log line, an email body, a
cell in a notebook — is the caller's choice. `fmt` is validated: anything but
`table` or `csv` raises, and so does a `wrap_width` of zero or less — there is no
spelling of "do not wrap", since a column no wider than its heading is unreadable.

## What to include

`include` says how far down to go. Each level contains the one before it, so the
choice is a depth rather than a set of switches:

- `include="failures"` (the default) — what failed or errored.
- `include="blocked"` adds the checks a failure or a rule stopped, each naming its
  prerequisite in `detail`. Use it when the question is "why did nothing fire?".
- `include="all"` adds the passes, turning the report into a full audit trail of
  every check against every row.

`row_explanation` and `print_row_explanation` take the same three levels, with
`"all"` as their default.

## Cost

`validate` keeps one object per check per row, because that is what the
explanation and summary views are built from. For a frame large enough that this
matters, call `validate_row` per row instead and skip the report: it returns only
the failures and allocates nothing for the checks that passed.
