# Writing checks

Back to the [README](../README.md). For what happens to the results, see
[reporting.md](reporting.md).

## The shape of a check

```python
from jobcheck import PASS, Status, CheckResult, register_check

@register_check("AGE_NEGATIVE", "Age is negative")
def age_negative(row):
    if row["age"] < 0:
        return CheckResult(Status.INVALID, {"value": row["age"], "minimum": 0})
    return PASS
```

A check takes `(row)` or `(row, ctx)` — nothing else; any other signature is
rejected when the module imports. It reads whatever columns it needs from the
row itself, which is why there is no `column` argument: these rules are
row-scoped, and many of them weigh several fields together.

Add one by putting a function in any `check_*.py` file the entry point loads.
There is no central list to update.

### Codes are permanent

`code` is a permanent identifier. Never renumber one, and never reuse a retired
one: override rule files, saved reports and downstream tooling all refer to
codes, so a reused code silently changes the meaning of data already written.

### What to return

| Return | Meaning |
|---|---|
| `PASS` | The check is happy with the row. |
| `CheckResult(Status.X, {...})` | Failed, with a kind and comments for the report. |
| `True` / `False` | Passed / failed as `Status.INVALID`. Fine for a one-liner. |
| `Status.MISSING` (etc.) | Failed with that kind and no comments. |

Anything else — including falling off the end of the function and returning
`None` — raises, naming the check. A check that forgets to return must never be
read as a pass.

`CheckResult` is truthy when the check **passed**, so `if result:` reads as "if the
test was happy". Do not lean on the raw `code` for truthiness: `0` is a pass but
is falsy as an integer, which is the opposite meaning.

### Reading a value safely

A missing value arrives from pandas as `NaN`, and **`NaN` is truthy**:
`if row["email"]:` is `True` for a blank field, so the obvious check silently
passes on exactly the rows it exists to catch. The library exports the check it
uses internally:

```python
from jobcheck import is_null

@group("EMAIL_PRESENT", "Email is missing")
def email_present(row):
    return CheckResult(Status.MISSING) if is_null(row["email"]) else PASS
```

`is_null` is `None`-and-`NaN` aware and never raises on a list or an array, where
`pd.isna` returns an array and `bool()` of that is an error.

### Statuses

Five built-ins, values 0–9 reserved:

| Status | Use it for |
|---|---|
| `PASS` (0) | The row is fine. |
| `MISSING` (1) | The field is absent or empty. |
| `MALFORMED` (2) | Present, but the wrong shape: unparseable, bad format. |
| `INVALID` (3) | Right shape, wrong content: out of range, unknown value. |
| `ERROR` (9) | The check raised. Recorded by the engine; a check **returning** it is refused, since that would report as a failure while claiming to be a broken check. |

The vocabulary is fixed: these five are the whole of it, and a `CheckResult`
carrying anything else is refused at construction. What varies between projects is
the *codes*, not the kinds — a check says which of these five happened, and its
comments say the rest.

### Comments

The dict a check attaches is what turns "Age is out of range" into something
actionable. It renders as `key=value; key=value`, sorted by key, in the report's
`comments` column. Put the numbers a reader would otherwise have to go and look
up: the value seen, the limit breached, the count that was wrong.

Keep them small and scalar. They end up in a CSV cell — one that is neutralised
against spreadsheet formula injection on the way out, since the values come from
the data ([reporting.md](reporting.md#opening-the-csv-in-a-spreadsheet)).

## Which checks an entry point loads

**Your checks live in your files, not in this package.** This package ships no
checks at all: importing `jobcheck` registers nothing, so every entry point says
what it wants, and two scripts in one codebase run different sets without
interfering.

```python
from jobcheck import load_checks, loaded_files

load_checks(["my_checks/check_age.py", "my_checks/check_email.py"])
loaded_files()           # the two resolved paths, in load order
```

Files are named explicitly and **nothing is discovered** — no directory scan, no
package convention, no import of anything that was not asked for. A file listed
twice, or already loaded, is skipped; prerequisites may live in any file of one
call, since the dependency graph is validated once the whole call has been
imported.

That is also what a pipeline writing check files into a run directory needs:

```python
load_checks(["runs/2026-09-10/inputs/checks.py"])
```

Each file gets a unique module name, so two run directories that each hold a
`checks.py` both load. No `__pycache__` is written beside the caller's file: that
directory is a record of what the run read, not somewhere to write to.

`examples/checks/` is the worked example — four files outside the library, loaded
by `examples/main.py` from the list it names in `CHECK_FILES`.

## Layering: one problem, one error

`depends_on` names codes that must **pass on the same row** before a check runs.
Prerequisites are all-or-nothing — every one must pass, there is no "or" — and a
check whose prerequisites did not all pass is skipped entirely: not a pass, not a
failure, absent from the row's errors.

A workable three-layer shape, which the shipped checks follow:

1. **Presence** (layer 0) — is the field there at all? `AGE_PRESENT`,
   `EMAIL_PRESENT`, `DATES_PRESENT`.
2. **Shape** — `AGE_NOT_A_NUMBER` waits on `AGE_PRESENT`.
3. **Value and agreement** — `AGE_NEGATIVE` and `AGE_TOO_HIGH` wait on
   `AGE_NOT_A_NUMBER`; `DATES_OUT_OF_ORDER` waits on both dates being present.

Rules of thumb:

- Depend on the check that would make yours meaningless, not on everything above
  it. `AGE_NEGATIVE` needs `AGE_NOT_A_NUMBER`; naming `AGE_PRESENT` as well adds
  nothing, since the graph is transitive.
- Keep layer 0 cheap and unconditional: it is what every root-cause report
  bottoms out at.
- A **disabled** prerequisite blocks its dependents, as does an **errored** one.
  A check that never ran confirmed nothing about the row, so it must not silently
  unlock what sits below it. Switching off a presence check with a rule therefore
  switches off its whole layer — check the `skipped` column afterwards.

`layer` is computed, never declared: 0 with no prerequisites, otherwise one more
than the deepest one. It sorts the registry and the summary so fundamental checks
read first.

Everything structural fails at load: an unknown prerequisite code, a prerequisite
in a check file that was not loaded, a cycle (direct or transitive), a duplicate
code, a signature the engine cannot call.

## When a check raises

An exception inside a check becomes a `Status.ERROR` outcome carrying the
exception text, the row carries on, and dependents treat it as "did not pass".
Errors are counted separately from failures in the summary, so a broken check can
never be mistaken for bad data. Pass `on_error="raise"` to `explain_row`,
`validate_row` or `validate` for a run that should stop at the first
broken check instead.

A check reading a column that is not in the frame raises `KeyError`, which lands
as one of these `ERROR` outcomes naming the column.

## Per-row context

`RowContext` is **empty by default** and is yours to fill: four loose dicts
(`flags`, `paths`, `state`, `extra`) rather than a schema, because every pipeline
carries different metadata. The library's `build_context` returns an empty one
and reads nothing out of the row — supply your own builder instead:

```python
from dataclasses import dataclass

from jobcheck import RowContext, validate


@dataclass
class FileContext(RowContext):
    """The whole file, for a check that cannot answer from one row."""

    counts: dict = None


shared = FileContext(counts={c: df[c].value_counts().to_dict() for c in df.columns})
outcomes = validate(df, context_builder=lambda row: shared)
```

Handing every row the *same* object is what makes a cross-row check (uniqueness,
a total) cheap: the counts are built once, not per row.


Metadata that is not tabular — flags, computed paths, pipeline state — goes in
`RowContext`, not in extra DataFrame columns, which cause dtype churn and end up
in exports. `build_context(row)` in `src/jobcheck/context.py` is a deliberate stub:
fill it with whatever produces per-row metadata in your pipeline, and take
`(row, ctx)` in the checks that need it.

## In a pipeline

```python
import pandas as pd
from jobcheck import (
    build_context, build_report, check_rule_columns, load_checks,
    load_overrides, root_cause, validate, validate_row, write_report,
)

load_checks(["examples/checks/check_age.py", "examples/checks/check_email.py"])
overrides = load_overrides([
    "examples/rules/split_by_topic/01_age_rules.yaml",
    "examples/rules/split_by_topic/02_email_rules.yaml",
])
for warning in check_rule_columns(df, overrides):
    print(f"warning: {warning}")

# Full report, when you want to look at the failures:
outcomes = validate(df, overrides=overrides)
write_report(build_report(outcomes, df=df, key_column="id"), "report.csv")

# Or just the failures per row, when you only need to gate:
df["errors"] = df.apply(
    lambda row: validate_row(row, ctx=build_context(row), overrides=overrides), axis=1
)
df["root_cause"] = df["errors"].apply(lambda results: root_cause(results) or "")
clean = df[df["errors"].str.len() == 0]
```

Load the check files and the rules **once**, outside the `apply`. The `errors` column holds
outcome objects, so project it to text before writing the frame anywhere.

## Troubleshooting

**A check never fires.** Explain a row you expect it to catch: it will be
`disabled`, `skipped` with the blocking prerequisite named, `errored`, or absent
entirely — absent means its module was never loaded.

**`Check 'X' depends on 'Y', which is not registered.`** `Y` is a typo, or it
lives in a check file that was not loaded. The message lists the files that were.

**`Dependency cycle among checks: A -> B -> A`.** Two checks require each other —
often a presence check given a `depends_on` naming something that waits for it.

**`Duplicate check code 'X'`.** Two checks share a code. Codes are permanent, so
rename the new one.

**`Check 'X' returned None.`** The function fell off the end without returning.

**An `errored` outcome with a `KeyError`.** The check read a column that is not in
the frame; check the spelling against the data.

**A rule looks right but has no effect.** Another rule later in load order
matches the same row and code, and last wins — or its criterion names a column
the data lacks, which `check_rule_columns` reports.
