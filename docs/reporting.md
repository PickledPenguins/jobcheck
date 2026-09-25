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
outcomes = validate(df, rules=rules)
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

A column the frame holds more than once is refused, naming how often it appears:
`df[key_column]` is a table rather than a column then, and every line of the
report would be labeled with the column's *name* instead of the row's key.

## Showing data alongside the failures

`add_columns` copies fields from the frame into the report, in the order given,
immediately after `row`:

```python
build_report(outcomes, df=df, key_column="id",
             add_columns=["source_system", "record_type", "age"])
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

print_row_explanation(explain_row(row, rules=rules), include="blocked")
```

For a row with no age, against the shipped age checks and no rules:

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

A check a rule switched off reads `disabled by rule '<name>'` instead.

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

## The data without the printing

Every `print_*` has a function that returns the frame it prints, for a run that files,
filters or asserts on the result instead of reading it:

```python
from jobcheck import root_cause_counts, row_explanation, summarize_outcomes

summary = summarize_outcomes(outcomes)          # the table print_summary prints
hidden = summary.loc[summary["skipped"] > 0, "code"].tolist()   # checks a failure hid
causes = root_cause_counts(outcomes)            # root_cause, rows -- most rows first
story = row_explanation(outcomes[4], include="blocked")   # print_row_explanation's frame
```

The outcome constants are what `outcome.outcome` is compared against, so a question the
tables do not ask is a comprehension over `outcomes`:

```python
from jobcheck import DISABLED, PASSED, SKIPPED

# Rows where a failing prerequisite hid other checks: fixing the one value may
# surface more, so these are the rows worth a second run.
hidden_rows = [position for position, row_outcomes in enumerate(outcomes)
               if any(o.outcome == SKIPPED for o in row_outcomes)]
# Rows every enabled check was happy with -- a switched-off check is not a failure.
clean_rows = [position for position, row_outcomes in enumerate(outcomes)
              if all(o.outcome in (PASSED, DISABLED) for o in row_outcomes)]
```

The registry and the rules the same way, for a run that keeps what it checked beside
what it found:

```python
from jobcheck import get_registry_table, get_rules_table, load_checks

load_checks(["my_checks/check_age.py", "my_checks/check_email.py"])
registry = get_registry_table(add_columns=["source_file"])
registry.to_csv("registry.csv", index=False)   # the checks this run had
off_by_default = registry.loc[registry["default"] == "OFF", "code"].tolist()
broad_rules = get_rules_table(rules, add_columns=["codes"]).query("codes_hit_count > 1")
```

And the renderer's pieces, for output of your own that should read like the tables:

```python
from jobcheck import FAILED, format_table, render_status

# One line per failure in your own log, the status spelled as the report spells it.
for position, row_outcomes in enumerate(outcomes):
    for o in row_outcomes:
        if o.outcome == FAILED:
            print(f"row {position}: {o.code} {render_status(o.status)}")

# Any frame of your own, bordered like every table here.
print(format_table(df.groupby("source_system").size().reset_index(name="rows")))
```

## Opening the CSV in a spreadsheet

Comments carry values that came from the data, and a spreadsheet runs any cell
starting with `=`, `+`, `@`, a tab or a carriage return as a formula. CSV output
therefore prefixes such a cell with an apostrophe, which makes it display as
text — the standard neutralizer. A negative number keeps its minus sign. Column
*headings* are neutralized the same way: an `add_columns` name is one of the
data's own column names, so it can carry a formula as easily as a value can.

Nothing is escaped in the table view, which cannot execute anything, and the
outcomes themselves always hold the value the check actually saw. There is no
switch for it: a report is written to be opened by a person, and a CSV that can
execute on open is not one.

The same guard is exported for a CSV of your own — the data, say, with a column
flagging the rows that failed:

```python
from jobcheck import FAILED, escape_for_spreadsheet

failed = [any(o.outcome == FAILED for o in row_outcomes) for row_outcomes in outcomes]
df.assign(failed=failed).map(escape_for_spreadsheet).to_csv("flagged.csv", index=False)
```

## Leaving columns out

`add_columns` copies frame columns in; `drop_columns` takes the report's own
columns out. That is the pair a run needs when some columns are for whoever is
debugging and not for what ships:

```python
debug = False                       # your run's own flag
debug_only = ["comments", "detail", "layer"]
report = build_report(outcomes, df=df, key_column="id",
                      drop_columns=[] if debug else debug_only)
print_report(report, key_column="id")
```
```
row | code         | status      | outcome | message         | is_root_cause
----+--------------+-------------+---------+-----------------+--------------
1   | AGE_NEGATIVE | INVALID (3) | failed  | Age is negative | True
```

The remaining columns keep the report's order, not the caller's, and added columns
still land straight after `row`. A dropped column is gone from the CSV too, since
both formats render the frame they are given.

`REPORT_COLUMNS` is the report's own column names, in order, as a tuple. Read it to
say which columns a run *keeps* rather than which it drops:

```python
keep = ("row", "code", "message")
report = build_report(outcomes, df=df, key_column="id",
                      drop_columns=[c for c in REPORT_COLUMNS if c not in keep])
```

A name that is not a report column, or asked for twice, is refused and the message
lists what can go — the same shape `add_columns` uses, because a column silently
still there reads as proof it is empty. `row` can be dropped like any other:
`drop_columns` is a choice about your own output, not a judgement about which
columns matter.

The same pair is on `get_registry_table`, `print_registry`, `get_rules_table` and
`print_rules`.

## Every table names itself

Each `print_*` writes its own heading first, so an entry point printing three
tables in a row does not label them by hand:

```
== Rules: 3 loaded ==
== Registry: 11 check(s), 3 rule(s) considered ==
== Report: 12 line(s), keyed by id ==
== Row explanation: row 5, 11 of 11 check(s), include=all ==
== Summary: 6 row(s), 11 check(s) ==
```

The heading carries what the call was given, because "which table is this" and
"what did I ask for" are the same question once two of them are on screen: a row
explanation is `include=blocked` or it is not the table you meant. Two facts the
functions cannot read off their arguments are passed in for the heading and nothing
else — `print_report(report, key_column="id")`, since the key column's name is not
a column, and `print_row_explanation(outcomes, row_key=5)`, since a list of
outcomes does not say which row it came from.

`title=False` turns it off. `print_report` writes no heading for `fmt="csv"` at
all: a line above CSV makes it unparseable, and CSV is the format a caller
redirects to a file. Print your own if you want one.

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
`write_report` renders before it opens the file, so a rejected `fmt` leaves the
file that is already there untouched rather than truncating it to nothing.

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
the failures and retains nothing for the checks that passed. It still evaluates
every check — it is `explain_row` filtered, not a second algorithm — so the saving
is what is held, not what is computed.
