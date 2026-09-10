# Writing tests

Back to the [README](../README.md). For what happens to the results, see
[reporting.md](reporting.md).

## The shape of a test

```python
from pandas_row_validation import PASS, Status, TestResult, register_test

@register_test("AGE_NEGATIVE", "Age is negative")
def age_negative(row):
    if row["age"] < 0:
        return TestResult(Status.INVALID, {"value": row["age"], "minimum": 0})
    return PASS
```

A test takes `(row)` or `(row, ctx)` — nothing else; any other signature is
rejected when the module imports. It reads whatever columns it needs from the
row itself, which is why there is no `column` argument: these rules are
row-scoped, and many of them weigh several fields together.

Add one by putting a function in any `test_*.py` file under a suite directory.
There is no central list to update.

### Codes are permanent

`code` is a permanent identifier. Never renumber one, and never reuse a retired
one: override rule files, saved reports and downstream tooling all refer to
codes, so a reused code silently changes the meaning of data already written.

### What to return

| Return | Meaning |
|---|---|
| `PASS` | The test is happy with the row. |
| `TestResult(Status.X, {...})` | Failed, with a kind and comments for the report. |
| `True` / `False` | Passed / failed as `Status.INVALID`. Fine for a one-liner. |
| `Status.MISSING` (etc.) | Failed with that kind and no comments. |

Anything else — including falling off the end of the function and returning
`None` — raises, naming the test. A test that forgets to return must never be
read as a pass.

`TestResult` is truthy when the test **passed**, so `if result:` reads as "if the
test was happy". Do not lean on the raw `code` for truthiness: `0` is a pass but
is falsy as an integer, which is the opposite meaning.

### Reading a value safely

A missing value arrives from pandas as `NaN`, and **`NaN` is truthy**:
`if row["email"]:` is `True` for a blank field, so the obvious check silently
passes on exactly the rows it exists to catch. The library exports the test it
uses internally:

```python
from pandas_row_validation import is_null

@group("EMAIL_PRESENT", "Email is missing")
def email_present(row):
    return TestResult(Status.MISSING) if is_null(row["email"]) else PASS
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
| `ERROR` (9) | The test raised. Recorded by the engine; a test **returning** it is refused, since that would report as a failure while claiming to be a broken test. |

Project-specific kinds start at 10:

```python
from pandas_row_validation import register_status
DUPLICATE = register_status("DUPLICATE", 10)
```

Values are permanent identifiers like codes, and registration refuses anything
ambiguous: a reserved value, a duplicate value, or a duplicate name.

### Comments

The dict a test attaches is what turns "Age is out of range" into something
actionable. It renders as `key=value; key=value`, sorted by key, in the report's
`comments` column. Put the numbers a reader would otherwise have to go and look
up: the value seen, the limit breached, the count that was wrong.

Keep them small and scalar. They end up in a CSV cell — one that is neutralised
against spreadsheet formula injection on the way out, since the values come from
the data ([reporting.md](reporting.md#opening-the-csv-in-a-spreadsheet)).

## Groups: shared defaults for a file

```python
from pandas_row_validation import test_group

age = test_group(depends_on=["AGE_PRESENT"], suite="hard_tests", default_enabled=True)

@age("AGE_NEGATIVE", "Age is negative")
def age_negative(row): ...

@age("AGE_NOT_INTEGER", "Age is not a whole number", default_enabled=False)
def age_not_integer(row): ...
```

A group carries `depends_on`, `suite` and `default_enabled` so a file of related
tests states them once.

**A group's prerequisites are unconditional.** A test's own `depends_on` is added
to them, never substituted, so "everything in this file waits for X" cannot be
quietly undone one test at a time. A test that must run regardless belongs in a
group without that prerequisite, or outside any group — and note that a test
cannot sit in a group that depends on that same test, which is a cycle and fails
at load.

`register_test` takes `depends_on` too, for a test that needs a prerequisite
without a group.

## Suites: which tests an entry point loads

**Your tests live in your package, not in this one.** This package ships no tests
at all, which is why `package=` is required rather than defaulted: a default
would name this library, and the error for a missing suite would then point at
the wrong tree entirely.

A suite is a subpackage of *your* package holding `test_*.py` files. That is the
entire wiring — an `__init__.py` and the files.

```python
load_suites(["hard_tests", "soft_tests"], package="example_suites")
loaded_suites()          # {'base', 'hard_tests', 'soft_tests'}
```

Importing `pandas_row_validation` registers nothing, so each entry point states
what it wants and two scripts in one codebase can run different sets. Repeat and
overlapping calls import each suite once.

`test_*.py` files placed directly in your package are the **base** suite
(`BASE_SUITE`, the string `"base"`) and load on every call, whatever was asked
for: the tests that must run no matter which optional sets were chosen.

To add a suite: `mkdir my_checks/warning_tests`, an `__init__.py`, then
`load_suites(["warning_tests"], package="my_checks")`.

`examples/example_suites/` is the worked example of that layout — a package
outside the library, with `hard_tests/` and `soft_tests/` subpackages and a
`test_row_shape.py` in the base suite.

### Test files named by path

A pipeline that writes test files into a run directory has paths rather than an
importable package, and `load_test_files` takes those:

```python
load_test_files(["runs/2026-09-10/inputs/checks.py"])
```

Files are named explicitly and nothing is discovered; a file listed twice or
already loaded is skipped; prerequisites may live in any file of one call. Each
file gets a flat module name, so its tests land in the base suite, which is
always loaded. No `__pycache__` is written beside the caller's file.

## Layering: one problem, one error

`depends_on` names codes that must **pass on the same row** before a test runs.
Prerequisites are all-or-nothing — every one must pass, there is no "or" — and a
test whose prerequisites did not all pass is skipped entirely: not a pass, not a
failure, absent from the row's errors.

A workable three-layer shape, which the shipped tests follow:

1. **Presence** (layer 0) — is the field there at all? `AGE_PRESENT`,
   `EMAIL_PRESENT`, `DATES_PRESENT`.
2. **Shape** — `AGE_NOT_A_NUMBER` waits on `AGE_PRESENT`.
3. **Value and agreement** — `AGE_NEGATIVE` and `AGE_TOO_HIGH` wait on
   `AGE_NOT_A_NUMBER`; `DATES_OUT_OF_ORDER` waits on both dates being present.

Rules of thumb:

- Depend on the test that would make yours meaningless, not on everything above
  it. `AGE_NEGATIVE` needs `AGE_NOT_A_NUMBER`; naming `AGE_PRESENT` as well adds
  nothing, since the graph is transitive.
- Keep layer 0 cheap and unconditional: it is what every root-cause report
  bottoms out at.
- A **disabled** prerequisite blocks its dependents, as does an **errored** one.
  A test that never ran confirmed nothing about the row, so it must not silently
  unlock what sits below it. Switching off a presence test with a rule therefore
  switches off its whole layer — check the `skipped` column afterwards.

`layer` is computed, never declared: 0 with no prerequisites, otherwise one more
than the deepest one. It sorts the registry and the summary so fundamental tests
read first.

Everything structural fails at load: an unknown prerequisite code, a prerequisite
in a suite that was not loaded, a cycle (direct or transitive), a duplicate code,
an unknown suite, a signature the engine cannot call.

## When a test raises

An exception inside a test becomes a `Status.ERROR` outcome carrying the
exception text, the row carries on, and dependents treat it as "did not pass".
Errors are counted separately from failures in the summary, so a broken test can
never be mistaken for bad data. Pass `on_error="raise"` to `explain_row`,
`validate_row` or `collect_outcomes` for a run that should stop at the first
broken test instead.

A test reading a column that is not in the frame raises `KeyError`, which lands
as one of these `ERROR` outcomes naming the column.

## Per-row context

Metadata that is not tabular — flags, computed paths, pipeline state — goes in
`RowContext`, not in extra DataFrame columns, which cause dtype churn and end up
in exports. `build_context(row)` in `src/pandas_row_validation/context.py` is a deliberate stub:
fill it with whatever produces per-row metadata in your pipeline, and take
`(row, ctx)` in the tests that need it.

## In a pipeline

```python
import pandas as pd
from pandas_row_validation import (
    build_context, build_report, check_rule_columns, collect_outcomes,
    load_overrides_from_dir, load_suites, root_cause, validate, validate_row,
    write_report,
)

load_suites(["hard_tests", "soft_tests"], package="example_suites")
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

**A test never fires.** Explain a row you expect it to catch: it will be
`disabled`, `skipped` with the blocking prerequisite named, `errored`, or absent
entirely — absent means its module was never loaded.

**`Test 'X' depends on 'Y', which is not registered.`** `Y` is a typo, or its
suite was not loaded. The message lists the suites that are.

**`Dependency cycle among tests: A -> B -> A`.** Two tests require each other —
often a presence test placed inside the group that depends on it.

**`Duplicate test code 'X'`.** Two tests share a code. Codes are permanent, so
rename the new one.

**`Test 'X' returned None.`** The function fell off the end without returning.

**An `errored` outcome with a `KeyError`.** The test read a column that is not in
the frame; check the spelling against the data.

**A rule looks right but has no effect.** Another rule later in load order
matches the same row and code, and last wins — or its criterion names a column
the data lacks, which `check_rule_columns` reports.
