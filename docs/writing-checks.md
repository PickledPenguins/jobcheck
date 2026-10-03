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

Add one by putting a function in any `.py` file the entry point loads (the examples
name theirs `check_*.py`; nothing reads the name).
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
actionable. It renders as `key=value; key=value`, in the order the check wrote the
keys, in the report's `comments` column. Put the numbers a reader would otherwise have
to go and look up: the value seen, the limit breached, the count that was wrong.

Keep them small and scalar. They end up in a CSV cell, written as they are — a value
from the data that looks like a formula stays one
([reporting.md](reporting.md#opening-the-csv-in-a-spreadsheet)).

A comment shows the value the check worked with, not the cell as the file wrote it. A
numeric column holding a blank is read by pandas as `float`, and a check that converts
with `float()` does the same, so a cell `-1` reports as `value=-1.0`. Where the reader
needs the cell as written, read the file with `pd.read_csv(path, dtype=str)`, convert
inside the check, and put the original text in the comment.

## Which checks an entry point loads

**Your checks live in your files, not in this package.** This package ships no
checks at all: importing `jobcheck` registers nothing, so every entry point says
what it wants, and two scripts in one codebase run different sets without
interfering.

```python
from jobcheck import load_checks, registry_table

load_checks(["my_checks/check_age.py", "my_checks/check_email.py"])
registry_table()[["code", "source_file"]]   # each check and the file it came from
```

Files are named explicitly and **nothing is discovered** — no directory scan, no
package convention, no import of anything that was not asked for. A relative path
is resolved against the working directory unless the call names a `base_dir`:

```python
import os
load_checks(["check_age.py"], base_dir=os.path.join(os.getcwd(), "my_checks"))
```

That is how a script keeps naming its files while being run from anywhere: it passes a
directory found from its own location, `os.path.dirname(os.path.abspath(__file__))` or
a parent of it. `examples/main.py` passes the project root, the parent of its own
directory, and names its files `examples/checks/...` under it.<sup>[6](configuration.md#errors)</sup><sup>[6](configuration.md#errors)</sup> An absolute path ignores
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

A check file cannot import a module beside it. Each file is imported by path, and its
directory is not put on `sys.path`, so `from helpers import parse_number` raises
`ModuleNotFoundError: No module named 'helpers'`. Put helpers shared between check
files in a package that is installed or on `PYTHONPATH`, and import it from there. The
directory stays off `sys.path` on purpose: a helper named like a real module
(`csv.py`, `types.py`) would shadow it for the whole process.

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
silently missing. For the same reason, after `clear_registry()` a reload registers
none of them again. Prefer the nested `load_checks`, and register checks only in the
files it is given.

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
first, and the root causes read it: a row's root causes are its failures at the
shallowest layer.<sup>[9](interfaces.md#build_reportframe_outcomes-df-key_columnnone-add_columnsnone-includefailures---dataframe)</sup>

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

An exception inside a check becomes a `Status.ERROR` outcome whose `detail` is the
exception's type, its text and where it was raised -- `KeyError: 'amount'
(check_orders.py:14)`, the innermost line in the check's own file -- the row carries
on, and dependents treat it as "did not pass".
Errors are counted separately from failures in the summary, so a broken check can
never be mistaken for bad data. Pass `on_error="raise"` to `validate` for a run
that should stop at the first broken check instead.<sup>[10](reporting.md#diagnosing-a-whole-file)</sup>

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
frame.<sup>[11](interfaces.md#validatedf-rulesnone-context_buildernone-on_errorrecord-context_argsnone-repeat_keynone---listlistcheckoutcome)</sup>

Without a `context_builder` every row is handed the same empty `RowContext`: a check
taking `(row, context)` never sees `None`. That shared base object takes no attributes, so a
check caching a parsed value on it gets an `AttributeError`, recorded as `errored`,
rather than handing the first row's value to every later row. Caching per row needs a
builder that returns a fresh subclass instance for each row.

The builder runs once for every row, before any check, whether or not a check taking
`context` will run on that row. Cheap work does not care. Work that reads or stats
files belongs in a `functools.cached_property` on the subclass, so it happens only
when a check first asks for it.

Metadata that is not tabular — flags, computed paths, pipeline state — goes in
`RowContext`, not in extra DataFrame columns, which cause dtype churn and end up
in exports. Take `(row, context)` in the checks that need it.

## One row, many copies

Sometimes one row stands for several things to check, and how many is known only from
the data. For example, a job's `basedirname` lists its run directories, `alpha,alpha,beta`,
and each of `alpha`, `alpha2` and `beta` must exist and hold a child directory. Other
checks on the row, such as a bound on `val`, are about the job and need to run once.

Explode the list so each directory gets a row of its own, with every other column
copied, and pass `validate` the column that says which rows are copies of one job. Mark
the check at the top of the per-directory chain `repeat=True`:

```python
from pathlib import Path

import pandas as pd


@register_check("VAL_IN_RANGE", "val is outside 0 to 10")
def val_in_range(row):
    return OK if 0 <= float(row["val"]) <= 10 else Verdict(Status.INVALID, {"val": row["val"]})


@register_check("BASE_EXISTS", "Run directory does not exist", repeat=True)
def base_exists(row):
    return OK if Path("runs", row["dirname"]).is_dir() else Verdict(Status.MISSING)


@register_check("CHILD_EXISTS", "Child directory does not exist", depends_on=["BASE_EXISTS"])
def child_exists(row):
    return OK if Path("runs", row["dirname"], row["basedirname"]).is_dir() else Verdict(Status.MISSING)


def expand(jobs):
    """One row per listed name; `dirname` numbers the second and later uses of a name."""
    runs = jobs.assign(basedirname=jobs["basedirname"].str.split(","))
    runs = runs.explode("basedirname", ignore_index=True)
    use = runs.groupby(["id", "basedirname"], dropna=False).cumcount() + 1
    runs["dirname"] = runs["basedirname"] + use.map(lambda n: "" if n == 1 else str(n))
    return runs


for made in ("alpha/alpha", "beta/beta"):
    Path("runs", made).mkdir(parents=True)
jobs = pd.DataFrame({"id": ["J1", "J2"], "basedirname": ["alpha,alpha,beta", "beta"],
                     "val": ["50", "5"]})
runs = expand(jobs)
outcomes = validate(runs, repeat_key="id")
report = build_report(outcomes, df=runs, key_column="id", add_columns=["dirname"],
                      include="all")
print(report[["outcome", "detail"]].to_string())
```

```
                         outcome                                          detail
id dirname code                                                                 
J1 alpha   VAL_IN_RANGE   failed                                                
           BASE_EXISTS    passed                                                
           CHILD_EXISTS   passed                                                
   alpha2  VAL_IN_RANGE   shared  failed at position 0, the first row with id J1
           BASE_EXISTS    failed                                                
           CHILD_EXISTS  skipped          prerequisite did not pass: BASE_EXISTS
   beta    VAL_IN_RANGE   shared  failed at position 0, the first row with id J1
           BASE_EXISTS    passed                                                
           CHILD_EXISTS   passed                                                
J2 beta    VAL_IN_RANGE   passed                                                
           BASE_EXISTS    passed                                                
           CHILD_EXISTS   passed                                                
```

- **A check marked `repeat=True` runs on every copy,** and so does every check that
  depends on it: CHILD_EXISTS repeats because BASE_EXISTS does, so `alpha2`'s child is
  checked only if `alpha2` exists.
- **Every other check runs on the first copy only.** On a later copy it is not called,
  and is recorded `shared`: its `detail` says what it did and where. VAL_IN_RANGE fails
  once for J1, not three times.
- **Each copy still gets one outcome per check,** so every list `validate` returns
  describes one row of the frame you passed, and `explain_row` of a copy shows
  everything: what ran there, and what it shares.
- **Counts are of calls.** The summary's `failed` and `passed` count only the checks that
  ran; its `shared` column counts the copies that reused a result.
- **A repeated check can depend on one that is not.** It reads the first copy's result,
  so a presence check on `basedirname` that fails once skips BASE_EXISTS on every copy.
- **Rules:** every check is switched on or off per copy, so a rule matching `dirname`
  can turn off one directory of one job. A copy the rule disables records `disabled`,
  even for a check that does not repeat. If the rule disables such a check on the first
  copy, the next copy that enables it runs it, and the copies after share that result.

What makes this readable later is keeping the copy's identity in a column: `dirname`
above. The report shows it beside each line with `add_columns`, and rules can match it.
Anything held only in a context is invisible in both.

Three things need care:

- **Copies are the rows sharing a `repeat_key` value,** whether adjacent or not; the
  first in frame order is the one that runs everything. A key column that repeats for
  another reason, such as two frames joined with `concat`, would share results between
  unrelated rows, which is why `repeat_key` is never guessed.
- **The expansion runs before the engine does.** An exception in `expand` stops the run,
  so it must not raise on the data. A blank `basedirname` splits to nothing, and
  `explode` turns that into one row with the name missing, which `dropna=False` keeps
  numbered; a presence check on `basedirname` then reports it.
- **Without `repeat_key`,** `repeat` changes nothing: every check runs on every row.

The catalog case `tests/examples/complex/exploded-rows-repeat-only-the-path-checks/` is
this pattern at full size, with a rule turning off one copy.<sup>[11](interfaces.md#validatedf-rulesnone-context_buildernone-on_errorrecord-context_argsnone-repeat_keynone---listlistcheckoutcome)</sup>

## In a pipeline

```python
from jobcheck import (
    build_report, warn_missing_rule_columns, load_checks,
    load_rules, validate,
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
build_report(outcomes, df=df, key_column="id").to_csv("report.csv")

# Or a flag per row, when you only need to gate:
df["failed"] = [any(o.failed for o in row_outcomes) for row_outcomes in outcomes]
clean = df[~df["failed"]]
```

Load the check files and the rules **once**, before `validate`.

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
Fixing the file and loading it again in the same session does not clear it: the file
is skipped as already loaded, so call `clear_registry()` first.

**`Duplicate check code 'X'`.** Two checks share a code; the message names the file
the first one came from. Codes are permanent, so rename the new one. When both are the
same file, an earlier load of it failed part-way and left its checks registered: call
`clear_registry()` before loading it again.

**`Check 'X' returned None.`** The function fell off the end without returning.

**An `errored` outcome with a `KeyError`.** The check read a column that is not in
the frame; check the spelling against the data.

**An `errored` outcome with `'float' object has no attribute ...`.** The cell was
blank: pandas hands a blank as `NaN`, which is a `float`, so `row["name"].upper()`
raises. Give the check a prerequisite that tests the field with `is_null`.

**Every row errors with `'RowContext' object has no attribute ...`.** The checks take
`(row, context)` but `validate` was called without the `context_builder`, so each row
got the bare `RowContext`. Pass the builder.

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
| 9 | [interfaces.md: Root causes](interfaces.md#build_reportframe_outcomes-df-key_columnnone-add_columnsnone-includefailures---dataframe) | the rule in full, errored checks included |
| 10 | [reporting.md: Diagnosing a whole file](reporting.md#diagnosing-a-whole-file) | the summary's `errored` column |
| 11 | [interfaces.md: validate](interfaces.md#validatedf-rulesnone-context_buildernone-on_errorrecord-context_argsnone-repeat_keynone---listlistcheckoutcome) | `context_builder` and `context_args` in full |
| 12 | [configuration.md: Precedence](configuration.md#precedence-last-rule-wins) | last rule wins, and what sets the order |
| 13 | [configuration.md: Warnings](configuration.md#warnings) | the warning lines, quoted |
