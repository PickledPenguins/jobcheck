# Reporting

How to turn a validated frame into something a person can act on. Every view is
a function that returns a DataFrame carrying its own title, and pandas turns any of
them into text: `to_string(index=False)` for a terminal, `to_csv(index=False)` for a
file. There is no command line to learn; a pipeline calls these functions and decides
where the output goes.

Back to the [README](../README.md). The value types are in
[interfaces.md](interfaces.md#data-types).

## The short version

Here, and in every example below, `df` is the demo frame `examples/main.py` validates
when `--data` names no file, `rules` is the shipped `examples/rules/error_rules.yaml`,
and `outcomes` is that frame validated against the age and email checks under those
rules. Each shown output is what the block prints; a test runs every one.

```python
from jobcheck import build_report, load_checks, validate

load_checks(["examples/checks/check_age.py", "examples/checks/check_email.py"])
outcomes = validate(df, rules=rules)
report = build_report(outcomes, df=df, key_column="id")
print(report.to_string(index=False))    # report.to_csv(index=False) for a file
```

```
     row                 code        status  layer outcome                            message detail                       comments  is_root_cause
       2         AGE_NEGATIVE   INVALID (3)      2  failed                    Age is negative                 minimum=0; value=-5.0          False
       2     EMAIL_MISSING_AT MALFORMED (2)      1  failed                   Email has no '@'        at_signs=0; value=broken-email           True
       3         AGE_TOO_HIGH   INVALID (3)      2  failed Age is implausibly high (over 130)              maximum=130; value=200.0           True
       3 EMAIL_DOMAIN_INVALID MALFORMED (2)      2  failed       Email domain looks malformed                    domain=nodotdomain           True
       5          AGE_PRESENT   MISSING (1)      0  failed                     Age is missing                                                 True
       5        EMAIL_PRESENT   MISSING (1)      0  failed                   Email is missing                                                 True
<no key>          AGE_PRESENT   MISSING (1)      0  failed                     Age is missing                                                 True
<no key>        EMAIL_PRESENT   MISSING (1)      0  failed                   Email is missing                                                 True
```

## Shape: one row per failure

The report is long format — one line per failed check per data row — not one line
per data row. That is the unit a person diagnoses, it is the only shape that
survives being written as CSV, and it filters and pivots cleanly downstream.

| Column | What it carries |
|---|---|
| `row` | The key of the data row: the `key_column` value, or the frame's index. |
| `code` | The permanent check code.<sup>[1](writing-checks.md#codes-are-permanent)</sup> |
| `status` | The failure kind, rendered as `INVALID (3)`; `PASS (0)` on a line that did not fail, including one that never ran.<sup>[2](concepts.md#what-a-check-says-and-what-the-engine-records)</sup> |
| `layer` | How deep the check sits in the dependency graph; 0 is fundamental.<sup>[3](writing-checks.md#layering-one-problem-one-error)</sup> |
| `outcome` | `failed`, `errored`, and `skipped`/`disabled`/`shared`/`passed` when asked for.<sup>[4](interfaces.md#outcome)</sup> |
| `message` | The check's message — what a person reads first — for a check that failed or errored. Empty for one that passed, was skipped or was disabled. |
| `detail` | Why a check gave no verdict: the rule that disabled it, the prerequisites that blocked it, the exception it raised, or, on a copy under `repeat_key`, what it did on the first copy and where. Empty for a check that passed or failed. |
| `comments` | What the check attached, rendered `key=value; key=value`, sorted. |
| `is_root_cause` | True for **every** failure at that row's shallowest failing layer. Two failures at the same depth are two root causes: neither is upstream of the other. Not always the row's first line: lines are in evaluation order, so an independent chain registered earlier prints above a shallower failure.<sup>[5](interfaces.md#root_causesrow_outcomes---liststr)</sup> |

## Identifying rows

`key_column="id"` names the column that identifies a data row — one column, so a
composite key is a column you build first, where you decide how the parts join.
Without it the frame's index is
used, which is fine until the frame has been filtered and the index no longer
means anything.

Two conveniences: an integer key column that pandas widened to float still reads
as `102`, not `102.0`, and a row whose key is missing reads `<no key>` rather
than `nan`.

A column the frame holds more than once is refused, naming how often it appears:<sup>[6](interfaces.md#error-messages)</sup>
`df[key_column]` is a table rather than a column then, and every line of the
report would be labeled with the column's *name* instead of the row's key.

## Showing data alongside the failures

`add_columns` copies fields from the frame into the report, in the order given,
immediately after `row`:

```python
report = build_report(outcomes, df=df, key_column="id",
                      add_columns=["source_system", "record_type", "age"])
print(report[["row", "source_system", "record_type", "age", "code", "status"]].to_string(index=False))
```

```
     row source_system record_type age                 code        status
       2        MODERN      STREAM  -5         AGE_NEGATIVE   INVALID (3)
       2        MODERN      STREAM  -5     EMAIL_MISSING_AT MALFORMED (2)
       3        MODERN      STREAM 200         AGE_TOO_HIGH   INVALID (3)
       3        MODERN      STREAM 200 EMAIL_DOMAIN_INVALID MALFORMED (2)
       5                                        AGE_PRESENT   MISSING (1)
       5                                      EMAIL_PRESENT   MISSING (1)
<no key>                                        AGE_PRESENT   MISSING (1)
<no key>                                      EMAIL_PRESENT   MISSING (1)
```

They carry the context a reader needs to judge a failure without going back to
the source file -- which system sent the row, which batch it arrived in, the
field the check was reading. The value repeats on every failure of that row, which
is what makes the CSV pivot cleanly.

Values read like the row key: a whole float loses its `.0`, and a missing value
is blank. A name that is not in the frame, named twice, or colliding with one of
the report's own column names is refused rather than quietly dropped or
overwriting the report's own data.

## Diagnosing one row

The demo frame's fifth row holds nothing but its `id`. In a fresh process, against the
shipped age checks and no rules:

```python
from jobcheck import explain_row, load_checks, root_causes, row_explanation

load_checks(["examples/checks/check_age.py"])
row_outcomes = explain_row(df.iloc[4])
print(row_explanation(row_outcomes, include="blocked").to_string(index=False))
print("root cause:", ", ".join(root_causes(row_outcomes)))
```

```
 layer             code  outcome      status                                      detail
     0      AGE_PRESENT   failed MISSING (1)                              Age is missing
     1 AGE_NOT_A_NUMBER  skipped    PASS (0)      prerequisite did not pass: AGE_PRESENT
     2     AGE_NEGATIVE  skipped    PASS (0) prerequisite did not pass: AGE_NOT_A_NUMBER
     2     AGE_TOO_HIGH  skipped    PASS (0) prerequisite did not pass: AGE_NOT_A_NUMBER
     2  AGE_NOT_INTEGER disabled    PASS (0)                  disabled by off by default
root cause: AGE_PRESENT
```

Passed `rules=rules`, a check a rule switched off reads `disabled by rule '<name>'`
instead.<sup>[7](configuration.md#precedence-last-rule-wins)</sup>

Reading order is evaluation order, so every `skipped` line names what blocked it.
`root_causes` gives the row's **shallowest** failures, and there may be more than
one when a row failed two chains at the same depth. Every failure shown is already
the root of its own chain — a check only runs once its prerequisites passed — so
when a row breaks in two chains that never touch, neither is upstream of the other
and the shallower one is the one to read first. `include="blocked"` drops the
checks that simply passed.

## Diagnosing a whole file

```python
from jobcheck import summarize_outcomes

print(summarize_outcomes(outcomes).to_string(index=False))
```

Per check: `failed`, `root_cause_rows`, `errored`, `skipped`, `disabled`, `shared`,
`passed`, worst first. `shared` counts the copies, under `validate(repeat_key=...)`,
that reused the first copy's result instead of running the check, so `failed` and
`passed` count calls, not rows. `root_cause_rows` counts the rows the check was a root cause of; a row
failing two chains at the same depth counts against both. Data failures come first: an
errored check is a root cause only on a row with no data failure, where it is the one
thing to read. A broken shallow check therefore never takes the flag from a real
failure, and `root_cause_rows` can exceed `failed` by the rows where it stood alone.

Every row's list must be complete: `validate`'s result, or `explain_row` per row
streamed as a generator. `validate_row` keeps only the failures, so a list of its
results would count too few passes and skips; one whose rows differ in length is
refused with a `ValueError`: `summarize_outcomes needs every check's outcome on every
row, but the list for row 1 holds 1 and the one before it 0: pass validate's result, or
explain_row's per row. validate_row keeps only the failures.`

Read it this way: a high `failed` count is a data problem; a high `skipped` count
is a *layering* signal — some fundamental check is failing often and hiding
everything below it, so fix that code first; any `errored` count at all is a
broken check, not bad data.<sup>[8](writing-checks.md#when-a-check-raises)</sup>

## Working with the tables

Every table is an ordinary DataFrame, for a run that files, filters or asserts on
the result instead of reading it:

```python
from jobcheck import row_explanation, summarize_outcomes

summary = summarize_outcomes(outcomes)
hidden = summary.loc[summary["skipped"] > 0, "code"].tolist()   # checks a failure hid
causes = summary.loc[summary["root_cause_rows"] > 0, ["code", "root_cause_rows"]]
story = row_explanation(outcomes[4], include="blocked")
```

`Outcome` is what `outcome.outcome` is compared against, so a question the
tables do not ask is a comprehension over `outcomes`:

```python
from jobcheck import Outcome

# Rows where a failing prerequisite hid other checks: fixing the one value may
# surface more, so these are the rows worth a second run.
hidden_rows = [position for position, row_outcomes in enumerate(outcomes)
               if any(o.outcome == Outcome.SKIPPED for o in row_outcomes)]
# Rows every enabled check was happy with -- a switched-off check is not a failure.
clean_rows = [position for position, row_outcomes in enumerate(outcomes)
              if all(o.outcome in (Outcome.PASSED, Outcome.DISABLED)
                     for o in row_outcomes)]
```

The registry and the rules the same way, for a run that keeps what it checked beside
what it found:

```python
from jobcheck import load_checks, registry_table, rules_table

load_checks(["my_checks/check_age.py", "my_checks/check_email.py"])
registry = registry_table()
registry.to_csv("registry.csv", index=False)   # the checks this run had
off_by_default = registry.loc[registry["default"] == "OFF", "code"].tolist()
broad_rules = rules_table(rules).query("codes_hit_count > 1")
```

And for output of your own that should read like the tables:

```python
from jobcheck import Outcome

# One line per failure in your own log, the status spelled as the report spells it.
for position, row_outcomes in enumerate(outcomes):
    for o in row_outcomes:
        if o.outcome == Outcome.FAILED:
            print(f"row {position}: {o.code} {o.status_label}")

# Any frame of your own, printed like every table here, under a title you set.
per_source = df.groupby("source_system").size().reset_index(name="rows")
per_source.attrs["title"] = "Rows per source"
print(per_source.to_string(index=False))
```

## Opening the CSV in a spreadsheet

The tables hold the values the checks saw, unchanged, and `to_csv` writes them as
they are. Comments and added columns carry values from the data, and a spreadsheet
runs any cell starting with `=`, `+`, `@`, a tab or a carriage return as a formula.
jobcheck does not escape them. A CSV of data you do not trust belongs in a viewer that
executes nothing, such as `csvlook`, or behind an escape of your own before a
spreadsheet opens it.

The same holds for a frame of your own -- the data, say, with a column flagging the
rows that failed:

```python
from pathlib import Path

from jobcheck import Outcome

failed = [any(o.outcome == Outcome.FAILED for o in row_outcomes) for row_outcomes in outcomes]
Path("flagged.csv").write_text(df.assign(failed=failed).to_csv(index=False))
```

## Which columns a table shows

Every table carries every column it builds; the library chooses none. The report's
are `row`, `code`, `status`, `layer`, `outcome`, `message`, `detail`, `comments` and
`is_root_cause`, and `build_report`'s `add_columns` copies columns of the data in,
straight after `row`. The registry table carries `source_file` and
`could_be_overridden_by`, and the rules table both `codes` and its count.

For a run that wants fewer columns, drop them with pandas; the title survives:

```python
debug = False                       # your run's own flag
report = build_report(outcomes, df=df, key_column="id")
if not debug:
    report = report.drop(columns=["comments", "detail", "layer"])
print(report.to_string(index=False))
```
```
     row                 code        status outcome                            message  is_root_cause
       2         AGE_NEGATIVE   INVALID (3)  failed                    Age is negative          False
       2     EMAIL_MISSING_AT MALFORMED (2)  failed                   Email has no '@'           True
       3         AGE_TOO_HIGH   INVALID (3)  failed Age is implausibly high (over 130)           True
       3 EMAIL_DOMAIN_INVALID MALFORMED (2)  failed       Email domain looks malformed           True
       5          AGE_PRESENT   MISSING (1)  failed                     Age is missing           True
       5        EMAIL_PRESENT   MISSING (1)  failed                   Email is missing           True
<no key>          AGE_PRESENT   MISSING (1)  failed                     Age is missing           True
<no key>        EMAIL_PRESENT   MISSING (1)  failed                   Email is missing           True
```

A dropped column is gone from the CSV too, since both formats write the frame they
are given.

## Every table names itself

Every table carries its title in `table.attrs["title"]` -- `Report`, `Row
explanation`, `Summary`, `Registry` or `Rules` -- so a caller printing several can
head each without naming it. The example entry points print it as a bar, `== Report
==`, above the table.

The title survives selecting columns, filtering rows, sorting and `head`; merging
or concatenating with an untitled frame drops it. Set `frame.attrs["title"]` on a
frame of your own to give it one. Keep it out of a CSV: a line above CSV makes it
unparseable.

## Formats and files

```python
from pathlib import Path

report.to_string(index=False)                   # aligned text for a terminal
report.to_csv(index=False)                      # the same columns as CSV
Path("report.csv").write_text(report.to_csv(index=False))
```

Both return a string, so where it goes — the terminal, a file, a log line, an email
body — is the caller's choice. Any other pandas writer works the same way.

- **Use `to_string()`, not `print(report)`.** Printing a frame directly shows only the
  first and last rows of a long one, so most of a report's failures would be hidden.
- **Nothing is escaped.** A cell holding a terminal control sequence acts on the
  terminal it is printed to, and a line break inside a cell shows as `\n` in
  `to_string`. Pipe the CSV through `csvlook` or `cat -v` when the data is not yours.
- **Long text is not wrapped.** A report line with a long message or comments runs
  past the terminal's width; `to_csv` piped into `csvlook` or a spreadsheet reads
  better for wide reports.
- An empty table prints pandas' `Empty DataFrame` notice from `to_string`, or the
  header row alone from `to_csv`.

## What to include

`include` says how far down to go. Each level contains the one before it, so the
choice is a depth rather than a set of switches:

- `include="failures"` (the default) — what failed or errored.
- `include="blocked"` adds the checks a failure or a rule stopped, each naming its
  prerequisite in `detail`. Use it when the question is "why did nothing fire?".
- `include="all"` adds the passes, and the `shared` lines of copies under
  `repeat_key`, turning the report into a full audit trail of every check against
  every row.

`row_explanation` takes the same three levels, with `"all"` as its default.

## Cost

`validate` keeps one object per check per row, because that is what the
explanation and summary views are built from. For a frame large enough that this
matters, call `validate_row` per row instead and skip the report: it returns only
the failures and retains nothing for the checks that passed. It still evaluates
every check — it is `explain_row` filtered, not a second algorithm — so the saving
is what is held, not what is computed.

## References

| # | Section | What it covers |
|---|---|---|
| 1 | [writing-checks.md: Codes are permanent](writing-checks.md#codes-are-permanent) | what a reused code would break |
| 2 | [concepts.md: What a check says](concepts.md#what-a-check-says-and-what-the-engine-records) | status against outcome, and why a line that never ran shows `PASS (0)` |
| 3 | [writing-checks.md: Layering](writing-checks.md#layering-one-problem-one-error) | how layers come from `depends_on` |
| 4 | [interfaces.md: Outcome](interfaces.md#outcome) | the five outcomes as values |
| 5 | [interfaces.md: root_causes](interfaces.md#root_causesrow_outcomes---liststr) | the rule in full, errored checks included |
| 6 | [interfaces.md: Error messages](interfaces.md#error-messages) | the report's refusals, quoted |
| 7 | [configuration.md: Precedence](configuration.md#precedence-last-rule-wins) | which rule decides for a row |
| 8 | [writing-checks.md: When a check raises](writing-checks.md#when-a-check-raises) | what an errored check records |
