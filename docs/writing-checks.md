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

A check takes `(row)` or `(row, ctx)` — nothing else; any other signature is
rejected when the module imports. It reads whatever columns it needs from the
row itself, which is why there is no `column` argument: these rules are
row-scoped, and many of them weigh several fields together.

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
rather than guessed at, since `True == 1 == Status.MISSING`.

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

The vocabulary is fixed: these five are the whole of it, and a `Verdict`
carrying anything else is refused at construction. What varies between projects is
the *codes*, not the kinds — a check says which of these five happened, and its
comments say the rest.

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
from jobcheck import load_checks, loaded_check_files

load_checks(["my_checks/check_age.py", "my_checks/check_email.py"])
loaded_check_files()           # the two resolved paths, in load order
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
__file__))`, and `examples/main.py` does exactly that. An absolute path ignores
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
from jobcheck import load_checks, loaded_check_files

HERE = os.path.join(os.getcwd(), "my_checks")
load_checks(["check_age.py", "check_email.py"], base_dir=HERE)
loaded_check_files()
```

The caller then names one path, `my_checks/all_checks.py`, and gets all of them.
The members are loaded files like any other: each is in `loaded_check_files()`,
before the bundle that pulled it in, and naming one directly as well loads it
once. A bundle may register checks of its own, and may load other bundles.
`examples/checks/all_checks.py` is a shipped one; `examples/bundle_main.py` is an
entry point that loads nothing else.

Two things are worth knowing before you build one:

- **Prerequisites may point anywhere in the whole load.** The dependency graph is
  validated as the outermost call returns, so a check in a bundle may depend on a
  code from another bundle, or from a file the caller names *after* it.
- **A failure is per file, at every depth.** If one member raises, the members
  before it stay loaded with their checks, the failing member leaves nothing, and
  the bundle itself is not recorded as loaded — fix the member and load the bundle
  again.

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
silently missing. The members also never appear in `loaded_check_files()`, which
is the record of what the run read. Prefer the nested `load_checks`.

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

A check defined in the running process — a notebook, a test, a script registering
its own — never passes through `load_checks`, so nothing runs the graph checks until
the first `validate`. `validate_registry()` runs them on demand, before any data is
read:

```python
from jobcheck import OK, Status, Verdict, register_check, validate_registry

@register_check("ORDER_ID_PRESENT", "Order id is missing")
def order_id_present(row):
    return OK if row.get("order_id") else Verdict(Status.MISSING)

@register_check("ORDER_ID_NUMERIC", "Order id is not a number",
                depends_on=["ORDER_ID_PRESENT"])
def order_id_numeric(row):
    return Verdict(str(row["order_id"]).isdigit())

validate_registry()   # a misspelled depends_on raises here, naming both codes
```

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

`context_args` is passed through untouched, once per row, so a named function is
the common case and a lambda is the corner case. A builder taking `(row)` alone
still works and is never handed the arguments. A builder is held to the same shape rule
as a check, and settled once before any row: other arities, and a keyword-only parameter
without a default, are refused with a `ValueError` naming the builder, even for an empty
frame.

Without a `context_builder` every row is handed the same empty `RowContext`, and so
is every row of `validate_row` and `explain_row` called without one: a check taking
`(row, context)` never sees `None`.

Metadata that is not tabular — flags, computed paths, pipeline state — goes in
`RowContext`, not in extra DataFrame columns, which cause dtype churn and end up
in exports. Take `(row, context)` in the checks that need it.

## In a pipeline

```python
import pandas as pd
from jobcheck import (
    build_report, warn_missing_rule_columns, load_checks,
    load_rules, root_causes, validate, validate_row, write_report,
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
write_report(build_report(outcomes, df=df, key_column="id"), "report.csv")

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
matches the same row and code, and last wins — or its criterion names a column
the data lacks, which `warn_missing_rule_columns` reports.
