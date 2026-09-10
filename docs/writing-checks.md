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

Add one by putting a function in any `check_*.py` file under a suite directory.
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

Project-specific kinds start at 10:

```python
from jobcheck import register_status
DUPLICATE = register_status("DUPLICATE", 10)
```

Values are permanent identifiers like codes, and registration refuses anything
ambiguous: a reserved value, a duplicate value, or a duplicate name.

### Comments

The dict a check attaches is what turns "Age is out of range" into something
actionable. It renders as `key=value; key=value`, sorted by key, in the report's
`comments` column. Put the numbers a reader would otherwise have to go and look
up: the value seen, the limit breached, the count that was wrong.

Keep them small and scalar. They end up in a CSV cell — one that is neutralised
against spreadsheet formula injection on the way out, since the values come from
the data ([reporting.md](reporting.md#opening-the-csv-in-a-spreadsheet)).

## Groups: shared defaults for a file

```python
from jobcheck import check_group

age = check_group(depends_on=["AGE_PRESENT"], suite="hard_checks", default_enabled=True)

@age("AGE_NEGATIVE", "Age is negative")
def age_negative(row): ...

@age("AGE_NOT_INTEGER", "Age is not a whole number", default_enabled=False)
def age_not_integer(row): ...
```

A group carries `depends_on`, `suite` and `default_enabled` so a file of related
checks states them once.

**A group's prerequisites are unconditional.** A check's own `depends_on` is added
to them, never substituted, so "everything in this file waits for X" cannot be
quietly undone one check at a time. A check that must run regardless belongs in a
group without that prerequisite, or outside any group — and note that a check
cannot sit in a group that depends on that same check, which is a cycle and fails
at load.

`register_check` takes `depends_on` too, for a check that needs a prerequisite
without a group.

## Suites: which checks an entry point loads

**Your checks live in your package, not in this one.** This package ships no checks
at all, which is why `package=` is required rather than defaulted: a default
would name this library, and the error for a missing suite would then point at
the wrong tree entirely.

A suite is a subpackage of *your* package holding `check_*.py` files. That is the
entire wiring — an `__init__.py` and the files.

```python
load_suites(["hard_checks", "soft_checks"], package="example_suites")
loaded_suites()          # {'base', 'hard_checks', 'soft_checks'}
```

Importing `jobcheck` registers nothing, so each entry point states
what it wants and two scripts in one codebase can run different sets. Repeat and
overlapping calls import each suite once.

`check_*.py` files placed directly in your package are the **base** suite
(`BASE_SUITE`, the string `"base"`) and load on every call, whatever was asked
for: the checks that must run no matter which optional sets were chosen.

To add a suite: `mkdir my_checks/warning_checks`, an `__init__.py`, then
`load_suites(["warning_checks"], package="my_checks")`.

`examples/example_suites/` is the worked example of that layout — a package
outside the library, with `hard_checks/` and `soft_checks/` subpackages and a
`check_row_shape.py` in the base suite.

### Test files named by path

A pipeline that writes check files into a run directory has paths rather than an
importable package, and `load_checks` takes those:

```python
load_checks(["runs/2026-09-10/inputs/checks.py"])
```

Files are named explicitly and nothing is discovered; a file listed twice or
already loaded is skipped; prerequisites may live in any file of one call. Each
file gets a flat module name, so its checks land in the base suite, which is
always loaded. No `__pycache__` is written beside the caller's file.

## Layering: one problem, one error

`depends_on` names codes that must **pass on the same row** before a check runs.
Prerequisites are all-or-nothing — every one must pass, there is no "or" — and a
test whose prerequisites did not all pass is skipped entirely: not a pass, not a
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
in a suite that was not loaded, a cycle (direct or transitive), a duplicate code,
an unknown suite, a signature the engine cannot call.

## When a check raises

An exception inside a check becomes a `Status.ERROR` outcome carrying the
exception text, the row carries on, and dependents treat it as "did not pass".
Errors are counted separately from failures in the summary, so a broken check can
never be mistaken for bad data. Pass `on_error="raise"` to `explain_row`,
`validate_row` or `collect_outcomes` for a run that should stop at the first
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

from jobcheck import RowContext, collect_outcomes


@dataclass
class FileContext(RowContext):
    """The whole file, for a check that cannot answer from one row."""

    counts: dict = None


shared = FileContext(counts={c: df[c].value_counts().to_dict() for c in df.columns})
outcomes = collect_outcomes(df, context_builder=lambda row: shared)
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
    build_context, build_report, check_rule_columns, collect_outcomes,
    load_overrides_from_dir, load_suites, root_cause, validate, validate_row,
    write_report,
)

load_suites(["hard_checks", "soft_checks"], package="example_suites")
overrides = load_overrides_from_dir("examples/rules/split_by_topic")
for warning in check_rule_columns(df, overrides):
    print(f"warning: {warning}")

# Full report, when you want to look at the failures:
outcomes = collect_outcomes(df, overrides=overrides)
write_report(build_report(outcomes, df=df, key_column="id"), "report.csv")

# Or as one object that carries the frame and the rules with the outcomes:
run = validate(df, overrides=overrides)
write_report(run.report(key_column="id"), "report.csv")
print(run.stats.rows, run.errors, len(run.failed_rows))

# Or just the failures per row, when you only need to gate:
df["errors"] = df.apply(
    lambda row: validate_row(row, ctx=build_context(row), overrides=overrides), axis=1
)
df["root_cause"] = df["errors"].apply(lambda results: root_cause(results) or "")
clean = df[df["errors"].str.len() == 0]
```

Load suites and rules **once**, outside the `apply`. The `errors` column holds
outcome objects, so project it to text before writing the frame anywhere.

## Troubleshooting

**A check never fires.** Explain a row you expect it to catch: it will be
`disabled`, `skipped` with the blocking prerequisite named, `errored`, or absent
entirely — absent means its module was never loaded.

**`Test 'X' depends on 'Y', which is not registered.`** `Y` is a typo, or its
suite was not loaded. The message lists the suites that are.

**`Dependency cycle among checks: A -> B -> A`.** Two checks require each other —
often a presence check placed inside the group that depends on it.

**`Duplicate check code 'X'`.** Two checks share a code. Codes are permanent, so
rename the new one.

**`Test 'X' returned None.`** The function fell off the end without returning.

**An `errored` outcome with a `KeyError`.** The check read a column that is not in
the frame; check the spelling against the data.

**A rule looks right but has no effect.** Another rule later in load order
matches the same row and code, and last wins — or its criterion names a column
the data lacks, which `check_rule_columns` reports.
