# Writing checks

Back to the [README](../README.md). For what happens to the results, see
[reporting.md](reporting.md).

## The shape of a check

```python
from jobcheck import OK, Status, Verdict, register_check

@register_check("AGE_NEGATIVE", "Age is negative")
def age_negative(row):
    if row["age"] < 0:
        return Verdict(Status.INVALID, {"value": row["age"], "minimum": 0})
    return OK
```

A check takes `(row)` or `(row, context)` — nothing else; any other signature is
rejected when the module imports. It reads whatever columns it needs from the
row itself, which is why there is no `column` argument: these rules are
row-scoped, and many of them weigh several fields together.

A second parameter is the context, so a setting cannot go there with a default:
`def age_below(row, limit=130)` would be handed the context as `limit`, and is refused
when it registers. Make the setting keyword-only — `def age_below(row, *, limit=130)` —
or bind it with `functools.partial(age_below, limit=130)` for a family of checks. A
context parameter may still default to `None`. A context builder is held to the same
rule.<sup>[1](interfaces.md#error-messages)</sup>

Add one by putting a function in any `check_*.py` file the entry point loads.
There is no central list to update.

### Codes are permanent

`code` is a permanent identifier. Never renumber one, and never reuse a retired
one: rule files, saved reports and downstream tooling all refer to
codes, so a reused code silently changes the meaning of data already written.

### What to return

| Return | Meaning |
|---|---|
| `OK` | The check is happy with the row. |
| `Verdict(Status.X, {...})` | Failed, with a kind and comments for the report. |
| `Verdict(condition)` | Wraps a bare comparison: a pass, or an `INVALID` failure with no comments. |
| `Verdict(Status.MISSING)` (etc.) | Failed with that kind and no comments. |

Anything else — a bare `True`, a bare `Status` value, or falling off the end of
the function and returning `None` — raises `TypeError` naming the check. A check
that forgets to return must never be read as a pass, and a bare bool is refused
rather than guessed at, since `True == 1 == Status.MISSING`.<sup>[2](interfaces.md#verdict)</sup>

`Verdict` is truthy when the check **passed**, so `if result:` reads as "if the
check was happy". Do not lean on the raw `status` for truthiness: `0` is a pass but
is falsy as an integer, which is the opposite meaning.

### Reading a value safely

A missing value arrives from pandas as `NaN`, and **`NaN` is truthy**:
`if row["email"]:` is `True` for a blank field, so the obvious check silently
passes on exactly the rows it exists to catch. The library exports the check it
uses internally:

```python
from jobcheck import OK, Status, Verdict, is_null, register_check

@register_check("EMAIL_PRESENT", "Email is missing")
def email_present(row):
    return Verdict(Status.MISSING) if is_null(row["email"]) else OK
```

`is_null` is `None`-and-`NaN` aware and never raises on a list or an array, where
`pd.isna` returns an array and `bool()` of that is an error.<sup>[3](interfaces.md#is_nullvalue---bool)</sup>

### Statuses

Five, and no others:<sup>[4](concepts.md#what-a-check-says-and-what-the-engine-records)</sup>

| Status | Use it for |
|---|---|
| `PASS` (0) | The row is fine. |
| `MISSING` (1) | The field is absent or empty. |
| `MALFORMED` (2) | Present, but the wrong shape: unparseable, bad format. |
| `INVALID` (3) | Right shape, wrong content: out of range, unknown value. |
| `ERROR` (9) | The check raised. Recorded by the engine; a check **returning** it is refused, since that would report as a failure while claiming to be a broken check. |

The vocabulary is fixed: these five are the whole of it, and a `Verdict`
carrying anything else is refused at construction. What varies between projects is
the *codes*, not the kinds — a check says which of these five happened, and its
comments say the rest.<sup>[5](reporting.md#shape-one-row-per-failure)</sup>

### Comments

The dict a check attaches is what turns "Age is out of range" into something
actionable. It renders as `key=value; key=value`, sorted by key, in the report's
`comments` column. Put the numbers a reader would otherwise have to go and look
up: the value seen, the limit breached, the count that was wrong.

Keep them small and scalar. They end up in a CSV cell — one that is neutralized
against spreadsheet formula injection on the way out, since the values come from
the data ([reporting.md](reporting.md#opening-the-csv-in-a-spreadsheet)).

## Which checks an entry point loads

**Your checks live in your files, not in this package.** This package ships no
checks at all: importing `jobcheck` registers nothing, so every entry point says
what it wants, and two scripts in one codebase run different sets without
interfering.

```python
from jobcheck import load_checks, registry_table

load_checks(["my_checks/check_age.py", "my_checks/check_email.py"])
registry_table(add_columns=["source_file"])   # each check and the file it came from
```

Files are named explicitly and **nothing is discovered** — no directory scan, no
package convention, no import of anything that was not asked for. A relative path
is resolved against the working directory unless the call names a `base_dir`:

```python
import os
load_checks(["check_age.py"], base_dir=os.path.join(os.getcwd(), "my_checks"))
```

That is how a script keeps naming the files that sit beside it while being run
from anywhere: it passes its own directory, `os.path.dirname(os.path.abspath(
__file__))`, and `examples/main.py` does exactly that.<sup>[6](configuration.md#errors)</sup> An absolute path ignores
`base_dir`. A file listed
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

## Bundles: one file that loads the rest

Ten check files means ten paths in every entry point that wants them, and a
forgotten one is a check that silently does not run. A **bundle** is a check file
whose job is to load the others, so a caller names one path:

```python
# my_checks/all_checks.py -- inside the file, HERE is os.path.dirname(os.path.abspath(__file__))
import os
from jobcheck import load_checks

HERE = os.path.join(os.getcwd(), "my_checks")
load_checks(["check_age.py", "check_email.py"], base_dir=HERE)
```

The caller then names one path, `my_checks/all_checks.py`, and gets all of them.
The members are loaded files like any other: each check's `source_file` is its
member rather than the bundle, and naming one directly as well loads it once. A bundle may register checks of its own, and may load other bundles.
`examples/checks/all_checks.py` is a shipped one; `examples/bundle_main.py` is an
entry point that loads nothing else.

Two things are worth knowing before you build one:

- **Prerequisites may point anywhere in the whole load.** The dependency graph is
  validated as the outermost call returns, so a check in a bundle may depend on a
  code from another bundle, or from a file the caller names *after* it.
- **A failure ends the load.** If one member raises, the error reaches your script
  unchanged and nothing is rolled back. Fix the member and run the script again; a
  process that loads again without restarting calls `clear_registry()` first.

Importing the members instead of loading them works too, and costs you the
guarantees above:

```python
# my_checks/all_checks.py -- works, but see below
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "my_checks"))
import check_age, check_email     # noqa: F401
```

Those are ordinary modules, so a second bundle holding its own `check_age.py`
imports nothing — the name is already in `sys.modules` — and its checks are
silently missing. Prefer the nested `load_checks`.

`examples/checks/` is the worked example — four files outside the library, loaded
by `examples/main.py` from the list it names in `CHECK_FILES`.

## Layering: one problem, one error

`depends_on` names codes that must **pass on the same row** before a check runs.
Prerequisites are all-or-nothing — every one must pass, there is no "or" — and a
check whose prerequisites did not all pass is skipped entirely: not a pass, not a
failure, absent from the row's errors.<sup>[7](reporting.md#diagnosing-one-row)</sup>

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
  switches off its whole layer. `warn_blocking_rules(rules)` names every check a
  disable rule silences that way, and the summary's `skipped` column counts them.<sup>[8](configuration.md#disabling-a-check-disables-what-depends-on-it)</sup>

`layer` is computed, never declared: 0 with no prerequisites, otherwise one more
than the deepest one. The registry table sorts on it, so fundamental checks read
first, and `root_causes` reads it: a row's root causes are its failures at the
shallowest layer.<sup>[9](interfaces.md#root_causesrow_outcomes---liststr)</sup>

Everything structural fails at load: an unknown prerequisite code, a prerequisite
in a check file that was not loaded, a cycle (direct or transitive), a duplicate
code, a signature the engine cannot call.

A check defined in the running process — a notebook, a test, a script registering
its own — never passes through `load_checks`, so the graph checks run when something
first needs the evaluation order: the first `validate` on a frame with rows, or
`registry_table()`, which is the way to run them before any data is read:

```python
from jobcheck import OK, Status, Verdict, is_null, register_check, registry_table

@register_check("ORDER_ID_PRESENT", "Order id is missing")
def order_id_present(row):
    return Verdict(Status.MISSING) if is_null(row.get("order_id")) else OK

@register_check("ORDER_ID_NUMERIC", "Order id is not a number",
                depends_on=["ORDER_ID_PRESENT"])
def order_id_numeric(row):
    return Verdict(str(row["order_id"]).isdigit())

registry_table()   # a misspelled depends_on raises here, naming both codes
```

## When a check raises

An exception inside a check becomes a `Status.ERROR` outcome carrying the
exception text, the row carries on, and dependents treat it as "did not pass".
Errors are counted separately from failures in the summary, so a broken check can
never be mistaken for bad data. Pass `on_error="raise"` to `explain_row`,
`validate_row` or `validate` for a run that should stop at the first
broken check instead.<sup>[10](reporting.md#diagnosing-a-whole-file)</sup>

A check reading a column that is not in the frame raises `KeyError`, which lands
as one of these `ERROR` outcomes naming the column.

## Per-row context

`RowContext` is **bare**: the library defines the type and no fields, because every
pipeline carries different metadata and a schema here would be wrong for all of
them. Subclass it, add what your checks read, and build it however suits you:

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
a total) cheap: the counts are built once, not per row. Where the context really
is per row, a `build` classmethod on your subclass is the tidy place for it:
`validate(df, context_builder=FileContext.build)`.

A builder usually needs the run's own arguments — where the file came from, which
flags were passed — and it takes them as a second parameter rather than closing
over them:

```python
from argparse import Namespace
from dataclasses import dataclass

from jobcheck import RowContext, validate


@dataclass
class RunContext(RowContext):
    source: str = ""
    strict: bool = False


def build_context(row, args):
    return RunContext(source=args.data, strict=args.strict)


args = Namespace(data="customers.csv", strict=True)   # your parsed command line
outcomes = validate(df, context_builder=build_context, context_args=args)
```

**A builder must not raise on the data.** It is called outside the protection a check
gets: `on_error="record"` turns a check's exception into an `errored` outcome, but an
exception from the builder propagates out of `validate`, and every row's outcomes are
lost with it. A builder reads the same untrusted cells the checks do, so write it to
survive them: map a blank or unparseable cell to `None` in the context, and put a
presence check ahead of the checks that read it, so the blank is reported as one
failure rather than ending the run.

```python
from dataclasses import dataclass
from pathlib import Path

from jobcheck import OK, RowContext, Status, Verdict, is_null, register_check


@dataclass
class JobContext(RowContext):
    run_dir: Path | None = None       # None where the cell is blank


def build_context(row, args):
    blank = is_null(row["run_dir"])
    return JobContext(run_dir=None if blank else args.base / row["run_dir"])


@register_check("RUN_DIR_PRESENT", "Run directory is blank")
def run_dir_present(row):
    return Verdict(Status.MISSING) if is_null(row["run_dir"]) else OK


@register_check("RUN_DIR_EXISTS", "Run directory does not exist",
                depends_on=["RUN_DIR_PRESENT"])
def run_dir_exists(row, context):
    return OK if context.run_dir.is_dir() else Verdict(Status.MISSING)
```

The catalog case `tests/examples/complex/job-manifest-with-per-row-paths/` is this
pattern at full size.

`context_args` is passed through untouched, once per row, so a named function is
the common case and a lambda is the corner case. A builder taking `(row)` alone
still works and is never handed the arguments. A builder is held to the same shape rule
as a check, and settled once before any row: other arities, and a keyword-only parameter
without a default, are refused with a `ValueError` naming the builder, even for an empty
frame.<sup>[11](interfaces.md#validatedf-rulesnone-context_buildernone-on_errorrecord-context_argsnone---listlistcheckoutcome)</sup>

Without a `context_builder` every row is handed the same empty `RowContext`, and so
is every row of `validate_row` and `explain_row` called without one: a check taking
`(row, context)` never sees `None`. That shared base object takes no attributes, so a
check caching a parsed value on it gets an `AttributeError`, recorded as `errored`,
rather than handing the first row's value to every later row. Caching per row needs a
builder that returns a fresh subclass instance for each row.

Metadata that is not tabular — flags, computed paths, pipeline state — goes in
`RowContext`, not in extra DataFrame columns, which cause dtype churn and end up
in exports. Take `(row, context)` in the checks that need it.

## In a pipeline

```python
from pathlib import Path

import pandas as pd
from jobcheck import (
    build_report, warn_missing_rule_columns, load_checks,
    load_rules, render, root_causes, validate, validate_row,
)

load_checks(["examples/checks/check_age.py", "examples/checks/check_email.py"])
rules = load_rules([
    "examples/rules/split_by_topic/01_age_rules.yaml",
    "examples/rules/split_by_topic/02_email_rules.yaml",
])
for warning in warn_missing_rule_columns(df, rules):
    print(f"warning: {warning}")

# Full report, when you want to look at the failures:
outcomes = validate(df, rules=rules)
Path("report.csv").write_text(render(build_report(outcomes, df=df, key_column="id"), fmt="csv"))

# Or just the failures per row, when you only need to gate:
df["errors"] = df.apply(
    lambda row: validate_row(row, rules=rules), axis=1
)
df["root_cause"] = df["errors"].apply(lambda results: "; ".join(root_causes(results)))
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
Loading the missing file fixes it. Correcting the typo in the file that is already
loaded does not: `load_checks` skips a path it has read, so that file is never
re-imported and the bad check stays registered. Call `clear_registry()` first, which
is what the message says.

**`Dependency cycle among checks: A -> B -> A`.** Two checks require each other —
often a presence check given a `depends_on` naming something that waits for it.

**`Duplicate check code 'X'`.** Two checks share a code. Codes are permanent, so
rename the new one.

**`Check 'X' returned None.`** The function fell off the end without returning.

**An `errored` outcome with a `KeyError`.** The check read a column that is not in
the frame; check the spelling against the data.

**A rule looks right but has no effect.** Another rule later in load order
matches the same row and code, and last wins<sup>[12](configuration.md#precedence-last-rule-wins)</sup> — or its criterion names a column
the data lacks, which `warn_missing_rule_columns` reports.<sup>[13](configuration.md#warnings)</sup>

## References

| # | Section | What it covers |
|---|---|---|
| 1 | [interfaces.md: Error messages](interfaces.md#error-messages) | the registration refusals, quoted |
| 2 | [interfaces.md: Verdict](interfaces.md#verdict) | the type in full: truthiness, comments, what construction refuses |
| 3 | [interfaces.md: is_null](interfaces.md#is_nullvalue---bool) | exactly what counts as null |
| 4 | [concepts.md: What a check says](concepts.md#what-a-check-says-and-what-the-engine-records) | status, outcome and verdict: three questions, three types |
| 5 | [reporting.md: Shape](reporting.md#shape-one-row-per-failure) | where status and comments land in the report |
| 6 | [configuration.md: Errors](configuration.md#errors) | the message for a path that is not there |
| 7 | [reporting.md: Diagnosing one row](reporting.md#diagnosing-one-row) | seeing which checks a row skipped, and why |
| 8 | [configuration.md: Disabling a check](configuration.md#disabling-a-check-disables-what-depends-on-it) | the same rule, from the rule file's side |
| 9 | [interfaces.md: root_causes](interfaces.md#root_causesrow_outcomes---liststr) | the rule in full, errored checks included |
| 10 | [reporting.md: Diagnosing a whole file](reporting.md#diagnosing-a-whole-file) | the summary's `errored` column |
| 11 | [interfaces.md: validate](interfaces.md#validatedf-rulesnone-context_buildernone-on_errorrecord-context_argsnone---listlistcheckoutcome) | `context_builder` and `context_args` in full |
| 12 | [configuration.md: Precedence](configuration.md#precedence-last-rule-wins) | last rule wins, and what sets the order |
| 13 | [configuration.md: Warnings](configuration.md#warnings) | the warning lines, quoted |
