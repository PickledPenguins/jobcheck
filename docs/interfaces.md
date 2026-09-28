# Interfaces

Everything here is exported from the `jobcheck` package and is the stable
surface. Names prefixed with `_` are internal and may change.

Back to the [README](../README.md). Authoring guidance is in
[writing-checks.md](writing-checks.md), the report in [reporting.md](reporting.md),
and the rule file format in [configuration.md](configuration.md).

`jobcheck.__version__` is the package version, pre-1.0: the API may change
between versions, while check codes, status values and the rule YAML schema
are treated as permanent.

## The short list

Writing checks and running them needs eight names, and nothing else here is
required reading:

`register_check`, `OK`, `Verdict`, `Status` for a check file;
`load_checks`, `load_rules`, `validate` and `build_report` for the pipeline
that runs them. Add `RowContext` when a check needs per-row state the frame does
not carry, and `validate_row` for a frame too large to keep every outcome.

Everything below that is the tooling surface: printing, explaining, counting,
inspecting the registry, and the pieces a wrapper around this library reaches
for. It is exported and supported -- jobchain, the pipeline runner built on this
library, uses several of these names -- but a first check file needs none of it.

## Data types

### `Status`

`IntEnum` of failure kinds: `PASS` 0, `MISSING` 1, `MALFORMED` 2, `INVALID` 3,
`ERROR` 9. Zero is a pass; every other value is a failure.<sup>[1](concepts.md#what-a-check-says-and-what-the-engine-records)</sup> The vocabulary is
fixed: these five are the whole of it, and a value outside them is refused.<sup>[2](writing-checks.md#statuses)</sup>

- A check must return a `Verdict`: anything else — a bare bool, a bare `Status`
  value, `None` — raises `TypeError` naming the check, as the engine reads it.

### `Verdict`

What a check returns. Frozen dataclass: `status: int = Status.PASS`,
`comments: Mapping[str, Any] = {}`.

- `bool(result)` is **True when the check passed**; `.failed` says the opposite
  explicitly. The raw `status` is not a truthiness source — 0 is a pass but falsy.
- A **bool** is accepted in place of a status, so a check can wrap a bare
  comparison: `Verdict(row["age"] > 0)` is a pass or an `INVALID` failure. It is
  resolved before anything reads the value as an integer, since `True == 1 ==
  MISSING` would otherwise invert the meaning. A check wanting `MISSING` or
  `MALFORMED` names it.<sup>[3](writing-checks.md#what-to-return)</sup>
- Comments are copied and frozen at construction, so a shared result cannot be
  mutated through the dict a caller passed in.
- Construction validates: a value outside `Status`, `Status.ERROR` (the engine's, not
  a check's), a non-integer non-bool status, a non-mapping `comments`, or a
  non-string comment key all raise.<sup>[4](#error-messages)</sup>
- `OK` is the shared, immutable passing result.

### `CheckOutcome`

What the engine recorded for one check on one row: `code` (the check code),
`outcome` (an `Outcome`), `status` (a
`Status` value), `layer`, `message`, `detail`, `comments`.

`.failed` is True for `failed` and `errored`; `.status_label` renders as
`INVALID (3)`. `detail` explains the three non-evaluating outcomes: which rule
disabled it, which prerequisites blocked it, or what it raised.<sup>[1](concepts.md#what-a-check-says-and-what-the-engine-records)</sup>

### `Outcome`

What happened to a check on a row: `Outcome.PASSED`, `FAILED`, `DISABLED`, `SKIPPED`,
`ERRORED`, whose values are `passed`, `failed`, `disabled`, `skipped`, `errored`. A
`str` as well, so `outcome.outcome == "failed"` holds, and a misspelled member is an
`AttributeError`. `CheckOutcome` accepts the plain string and refuses one that is
not an outcome. Write `.value` where the text is wanted: formatting a member prints
`Outcome.FAILED` on Python 3.11 and later, and `failed` on 3.10.<sup>[5](reporting.md#diagnosing-one-row)</sup>

### The registry

Each registered check has a `code`, `message`, `fn`, `source_file`,
`default_enabled`, `depends_on` and `layer`, created by the decorator. What a check
is *for* is its `message`, printed wherever it fails and shown in the registry
table; there is no second description field to keep in step with it.

The registry itself is internal (`registry._CHECKS`). Read it through
`registry_table`, which gives every check's code, layer, default, message and
`depends_on` as a frame, and `source_file` on request. `source_file` is `<unknown>` for
a check registered as a `functools.partial` or a callable object, which carry no source
file of their own. Nothing that mutates the list directly drops the cached evaluation
order.

### `RowContext`

Per-row metadata kept out of the DataFrame. **Bare**: the library defines the type
and no fields. Subclass it, add what your checks read, and build it however suits
the pipeline — a classmethod, a factory, or one object built outside the loop.
Whatever builds it is `validate`'s `context_builder`, a callable taking `(row)` or
`(row, context_args)` and returning a `RowContext`. The two-argument form is the
common one — a pipeline's context is built from the run's own arguments — so a
named function is passed directly rather than wrapped in a lambda that closes over
them. Without a builder, every row is handed the same empty context.<sup>[6](writing-checks.md#per-row-context)</sup>

The base class takes no attributes (`__slots__ = ()`): shared by every row, a value
a check cached on it would reach every later row. Setting one raises
`AttributeError`, which the engine records as `errored`. A subclass keeps its
`__dict__` and takes whatever it declares.

### `Rule`

One loaded rule: `name`, `action`, `codes`, `criteria`, `match_all`, `message`,
`source_file`. Each of `criteria` has a `column`, the `pattern` as written, and the
compiled `regex`; its type is internal, because nothing but the rule parser builds one.

## Registering checks

### `register_check(code, message, default_enabled=True, depends_on=None)`

Decorator. The function takes `(row)` or `(row, context)` and returns `OK` or a
`Verdict` — `Verdict(condition)` wraps a bare comparison.

Raises at import for a duplicate code, an empty code or message, a non-list
`depends_on` (a bare string would otherwise register one prerequisite per
character), a non-bool `default_enabled`,
or a signature the engine cannot call -- including a required keyword-only
argument, and a second positional parameter with a default other than `None`, which
would be handed the context (`def age_below(row, limit=130)`; write `*, limit=130` or
use `functools.partial`). A context builder is refused the same way. The `depends_on`
*codes* are checked later, when the dependency graph is validated, since a prerequisite
may live in a module not yet imported.<sup>[4](#error-messages)</sup>

### `load_checks(paths: list[str], base_dir: str | Path | None = None) -> None`

Imports the named `.py` files by path so their checks register themselves. A list
of paths, always — a bare string is refused, since it would otherwise be read as a
list of its characters. **Nothing is discovered**, which is what lets two entry
points in one codebase run different sets of checks. A file already loaded, or listed twice,
is skipped. The dependency graph is validated once the whole call has been imported,
so a prerequisite may live in any of the files. A relative path is resolved against
`base_dir` when one is given and against the working directory otherwise; an
absolute path ignores both. Raises `ValueError` for a path that is not a file,
naming the absolute path it tried, and for a file without a `.py` suffix
(`Cannot import '<path>' as a Python file.`), and propagates whatever a file raises
while importing. A file that raises is not rolled back: the checks registered before
the failing line stay, and the file is not recorded as loaded.<sup>[7](configuration.md#errors)</sup>

Each file is given a unique module name, so two directories that each hold a
`checks.py` both load, a bundle and a member of the same name included. No
`__pycache__` is written beside the file: a check file comes from wherever the
caller names, which is a record of what was read rather than somewhere to write
to. That is `sys.dont_write_bytecode`, which is the interpreter's flag rather
than this import's, so for the length of the import no thread writes bytecode
for anything it imports either.

A check file may call `load_checks` itself — a **bundle**, one path standing for
the files it collects:<sup>[8](writing-checks.md#bundles-one-file-that-loads-the-rest)</sup>

```python
# my_checks/all_checks.py -- inside the file, base_dir is
# os.path.dirname(os.path.abspath(__file__))
import os
from jobcheck import load_checks

load_checks(["check_age.py", "check_email.py"],
            base_dir=os.path.join(os.getcwd(), "my_checks"))
```

The members are loaded files in their own right: each check's `source_file` is
its member, and each is skipped if the caller also names it. The dependency graph
is validated as the *outermost* call returns, so a prerequisite may live in a bundle, in another bundle, or in a file
the caller names after the bundle. A file already being imported further up the
call is skipped, so a bundle naming itself, or two naming each other, finish
rather than recursing. A file that raises is not rolled back: the error propagates,
the checks registered before it stay, and the failing file is not recorded as
loaded. Loading again in the same process starts with `clear_registry()`.

One thread loads at a time: `load_checks` and `clear_registry` hold one reentrant
lock, so a second thread waits for the first to finish, and a bundle's nested call
still works.

Importing the members instead — `sys.path.insert` and `import check_age` — also
registers them, but they are then ordinary modules: two bundles holding a
same-named member silently load only the first, since the second import finds the
name in `sys.modules` and does nothing. Nesting `load_checks` has no such
collision, and records every member.

### When the dependency graph is validated

The dependency graph is validated when `load_checks` returns, and otherwise when
something first needs the evaluation order (`validate` on a frame with rows,
`registry_table`). Every `depends_on` edge is checked, cycles detected, layers
computed. An unregistered prerequisite raises — including one living in a check
file that was not loaded, deliberately as loud as a typo. A chain too deep for the
ordering walk — it is recursive, so it gives out near Python's own recursion limit,
around 900 links deep at the default 1000 — raises `ValueError` naming the registry
size and that limit, rather than a bare `RecursionError` naming nothing.<sup>[9](writing-checks.md#layering-one-problem-one-error)</sup>

### `clear_registry() -> None`

Empties the registry and evicts the modules that registered
checks from `sys.modules` -- never `__main__`, and never a standard-library module,
which is what a `functools.partial` or an `operator` callable reports; for a partial
it is the wrapped function's module -- so a later `load_checks` re-registers rather than
silently doing nothing. It is the whole of the registry-state API: there is no
way to save a registry and put it back, because outside a test there is no use
for one. A caller loads its check files at start-up, or clears and loads a
different set between runs, or runs a second entry point in a second process --
which is what the process-global registry means (see
[architecture](architecture.md)).

## Loading rules

`load_rules(paths, base_dir=None)` takes a list of paths and anchors them
exactly as `load_checks` does, and returns `list[Rule]` in the order given — which is
the precedence order, since the last matching rule wins.<sup>[10](configuration.md#precedence-last-rule-wins)</sup> It raises `ValueError` at
load time for every malformed rule, and for a rule name used twice anywhere in the
call; a path that is not a file raises `ValueError` naming it, the way
`load_checks` does, and a file that is not valid YAML raises `yaml.YAMLError`, as
the file layer reports it. A rule's `source_file` is the path as the caller wrote
it, relative or not: it is printed beside the rule, where an absolute path
resolved out of `base_dir` would name a directory only this machine has.
It is a thin wrapper over `jobcheck.rules`, which holds the format and its
parser and is handed the codes that exist rather than reaching into the registry.
Load the check files first: a rule naming an unregistered code is an error. See
[configuration.md](configuration.md).

Which codes a rule touches is `rule.codes`, and as a column,
`rules_table(rules, add_columns=["codes"])`.

## Loading both at once

`load_setup(path) -> list[Rule]` is the whole of configuring this library in one
call: it loads the check files a YAML file names and returns the rules from the rule
files it names.

```yaml
checks:
  - checks/all_checks.py        # a bundle, or list the files
rules:
  - rules/01_age.yaml           # in precedence order; optional
```

Both lists are resolved against the **setup file's own directory**, so the file and
the paths in it travel together; the setup file's own path is relative to where the
caller stands, like any path a user types. `checks` is required — a setup naming only
rules configures nothing, since rules switch checks on and off. `rules` may be
absent or empty, which is the no-rules baseline.

`ValueError` names the file for each refusal: a document that is not a mapping (a
flat list is the *rule* file's shape), an unknown key, a string where a list belongs
(`checks: one.py` is a string, and a string is a list of characters), an entry that
is not a path, an empty `checks`, and anything `load_checks` or `load_rules` would
refuse.<sup>[11](configuration.md#setup-files-naming-the-checks-and-the-rules-at-once)</sup>

Rules are named by path rather than written inline: a rule file is a flat top-level
list *without* a `rules:` key, which a setup file would contradict, and rule files
are meant to be shared between runs. `load_checks` and `load_rules` stay public —
this composes them, a bundle calls `load_checks` from inside a check file, and a
caller holding paths of its own has no file to write. `examples/setup.yaml` is the
worked example.

## Running checks

### `explain_row(row, context=None, rules=None, on_error="record") -> list[CheckOutcome]`

What every check did on one row, in evaluation order. The single implementation of
the per-row algorithm.

`on_error="record"` turns an exception inside a check into a `Status.ERROR`
outcome and continues; `"raise"` propagates it. A check returning something that is
not a result always raises — that is an authoring bug, not a data problem.

Raises `TypeError` when `row` is not a `pandas.Series`, and `ValueError` when it
has duplicate column labels — both before running anything.

A `context` of `None` — the default — becomes an empty `RowContext`, so a check
taking `(row, context)` is handed the same type here, in `validate_row` and in
`validate`.

### `validate_row(row, context=None, rules=None, on_error="record") -> list[CheckOutcome]`

The failing outcomes from `explain_row`, in evaluation order. Does not mutate `row`
or `context`. For the one to read first, ask `root_causes`.

### `root_causes(row_outcomes) -> list[str]`

`root_causes` returns **every** failure at the shallowest failing layer, in
evaluation order: two chains failing at the same depth are two root causes, and
naming only the first evaluated would let registration order decide what a
person reads as the cause. Deeper failures are left out as the ones to read next,
not as downstream of these: a check only runs once its prerequisites passed, so
every failure is the root of its own chain. Data failures come first: an
`errored` outcome counts only on a row with no `failed` one, so a broken check
never takes the flag from a real failure, and a row whose only problem is a broken
check is still flagged. Empty for a row that passed.

A caller wanting a single label per row (a tally, a column in a frame) takes the
first. Accepts either `validate_row` or `explain_row` output.

### `warn_missing_rule_columns(df, rules) -> list[str]`

One line per rule criterion naming a column the frame lacks — a rule that can
never fire. Checks are not checked: they read the row themselves, so a missing
field raises and is recorded as an `ERROR` outcome naming the column.<sup>[12](configuration.md#warnings)</sup>

### `warn_shadowed_rules(rules) -> list[str]`

One line per rule and code that a later rule overrules for every row: precedence is positional,
so a rule touching a code is dead for that code once a later rule touches it with
`match: all`. Needs no data — the answer is the same for every row, which is why
this is the one shadowing case reported. Two conditional rules that may or may not
overlap are left alone deliberately, since deciding that means comparing patterns
rather than reading them.

Judged per code, not per rule: a rule carrying several codes can be overruled for
one and decisive for another. Warns rather than raises, like
`warn_missing_rule_columns` — `examples/rules/error_rules.yaml` ships a shadowed
rule on purpose, as the precedence demonstration, and
`python3 examples/main.py --rules-table` prints the warning under the rules table.

### `warn_blocking_rules(rules) -> list[str]`

One line per disable rule and code that other checks depend on, naming every
dependent, direct or not, that the rule does not list itself: a check whose
prerequisite is off is skipped, so on the rows the rule matches those checks never
run and report nothing. Listing them in the same rule says the silence is meant and
ends the warning, which is why `examples/rules/error_rules.yaml`, disabling
`EMAIL_MISSING_AT` together with its dependent, reports nothing. A code below
another one the same rule disables is not reported again. Reads the registry for
the dependency graph, so load the checks first; like the other two, it warns rather
than raises, and `python3 examples/main.py --rules-table` prints it under the rules
table.<sup>[13](configuration.md#disabling-a-check-disables-what-depends-on-it)</sup>

### `validate(df, rules=None, context_builder=None, on_error="record", context_args=None) -> list[list[CheckOutcome]]`

Every check against every row: one `explain_row` call per row, and one list of
outcomes per row, in frame order. That is the shape `build_report` and
`summarize_outcomes` take.

`context_builder` is called once per row and returns the `RowContext` handed to
every check; hand back one shared object when a check needs the whole frame.
Without one, and for a builder that returns `None`, every row is handed the same
empty `RowContext`.

The builder is not covered by `on_error`: an exception it raises propagates out of
`validate` unchanged, and no row's outcomes are returned. It must not raise on the
data — map a blank cell to `None` and let a presence check report it; see
[writing-checks.md](writing-checks.md#per-row-context).

It takes `(row)` or `(row, context_args)`, settled once per `validate` rather than
per row, the same way a check takes `(row)` or `(row, context)`. `context_args` is
whatever the entry point wants every context built from — its parsed command line,
a connection, a configuration — passed through untouched. A builder taking neither
shape raises `ValueError` naming what it takes, before any row is read.

An `on_error` that is neither `"record"` nor `"raise"` raises `ValueError` before
any row is read, an empty frame included; anything but a `DataFrame` raises
`TypeError` naming `validate_row` and `explain_row` as the per-row calls.<sup>[4](#error-messages)</sup>

It keeps one outcome per check per row, so for a frame where that will not fit in
memory, call `validate_row(row)` per row instead and write the failures out as
they appear.<sup>[14](reporting.md#cost)</sup>

## Reporting

Every view is a DataFrame whose `attrs["title"]` names it — `Report`,
`Row explanation`, `Summary`, `Registry`, `Rules` — and `render` turns any of them
into text. The columns each shows by default are its entry in `_DEFAULT_COLUMNS` in
`src/jobcheck/tables.py`, the one place they are set; see
[reporting.md](reporting.md#which-columns-a-table-shows).

### `build_report(frame_outcomes, df, key_column=None, add_columns=None, include="failures") -> DataFrame`

The long-format report: one line per outcome `include` admits, per data row, in
evaluation order. `df` is required, since the outcomes describe its rows, and must
have one row per list in `frame_outcomes` — otherwise `ValueError`
(`outcomes cover 1 row(s) but the frame has 2: ...`). `key_column` names the single
column that identifies a row — one that is not in the frame, or is in it more than
once, raises `ValueError`; without it the frame's index labels the rows.
`add_columns` copies frame columns into the report just after `row`; a name not in
the frame, named twice, or colliding with one of the report's own columns raises
`ValueError`. `include` is `"failures"`, `"blocked"` or `"all"`, and anything else
raises `ValueError`. `"failures"` takes `validate_row`'s failures-only lists too;
the other two need every outcome, and refuse lists that differ in length.<sup>[15](reporting.md#what-to-include)</sup> Titled `Report`. The columns are in
[reporting.md](reporting.md#shape-one-row-per-failure).

### `row_explanation(row_outcomes, include="all") -> DataFrame`

One row per check on one data row, in evaluation order — `explain_row`'s result, or
one row's list from `validate`: `layer`, `code`, `outcome`, `status`, `detail`.
`detail` says why a check gave no verdict, and otherwise holds its rendered comments,
else its message, else `-`. `include` takes the report's three levels, with `"all"`
the default here; `"blocked"` drops the checks that simply passed. Titled
`Row explanation`.

### `summarize_outcomes(frame_outcomes) -> DataFrame`

Per check, across every row: `code`, `layer`, `failed`, `root_cause_rows`, `errored`,
`skipped`, `disabled`, `passed`, sorted by `failed`, `errored` and `skipped`, most
first, then by code. `root_cause_rows` counts the rows whose root causes include the
check — an errored check among them on the rows with no data failure, so it can
exceed `failed`. Takes `validate`'s result or any iterable of complete per-row lists,
a generator included — `explain_row(row)`
per row is the streaming form — and keeps only the counts. `validate_row`'s lists
hold failures only and would count wrong, so lists that differ in length raise
`ValueError`. Titled `Summary`.<sup>[16](reporting.md#diagnosing-a-whole-file)</sup>

### `render_comments(comments) -> str`

A check's comments as the report prints them: `key=value; key=value`, sorted by key
so the same failure renders the same way every run and reports diff cleanly, each
value through `str()`. An empty mapping gives an empty string. The report's `comments`
column is this; a caller printing one failure — jobchain's detail line — calls it
directly:

```python
from jobcheck import render_comments

print(render_comments({"value": -5, "minimum": 0}))
```

```
minimum=0; value=-5
```

### `registry_table(rules=None, add_columns=None) -> DataFrame`

One row per check, sorted layer, then code, titled `Registry`. Columns `code`,
`layer`, `default`, `message`, `depends_on`. Offers `source_file`, plus the two
columns that read `rules`: `could_be_overridden_by`, the rules that *reference* each
code with the action each would take, and `effective_state`, which says
`DEFAULT (ON)` when no rule references the code and "depends on row" when one does.
Neither is "was overridden by" — whether a rule fires is a per-row question this
table cannot answer.<sup>[17](reporting.md#working-with-the-tables)</sup>

### `rules_table(rules, add_columns=None) -> DataFrame`

One row per rule, titled `Rules`: `name`, `action`, `codes_hit_count`, `match`,
`message`. Offers `codes`, the list behind the count, and `source_file`.

Both registry tables take `add_columns`, the same argument `build_report` takes for
columns of the data: the names you want beyond the default columns, refused rather
than ignored when the name is not on offer.

### `render(table, fmt="table") -> str`

Any table as text. `"table"` draws it bordered under a `== Title ==` bar taken from
`table.attrs["title"]` (no bar when the frame has none), with long free-text columns
wrapped; `"csv"` returns CSV with no heading, escaping any cell or column name a
spreadsheet would run as a formula. Anything else raises `ValueError`.<sup>[18](reporting.md#opening-the-csv-in-a-spreadsheet)</sup> An empty
table renders as its title over `(empty)`, or the CSV header alone.

Cells are read by position: a duplicated column label renders each column's own
values, and an all-numeric frame keeps its integers as integers rather than `1.0`. A
cell holding line breaks (`\n`, `\r\n`, `\r` or a form feed) renders as a tall cell
rather than breaking the row, and tabs are expanded — a quoted multi-line CSV field
reaching the row key or an `add_columns` value is the usual way one arrives.

### `is_null(value) -> bool`

The null check both the engine and the renderer use — reach for it in your own
checks too, since `NaN` is truthy and `pd.isna` returns an array for list-like
values. `None`, `NaN`, `NaT` and `pd.NA` are null; a list or an array never is.<sup>[19](writing-checks.md#reading-a-value-safely)</sup>

## Error messages

Every message the library raises outside rule and setup files, which
[configuration.md](configuration.md#errors) lists. `<...>` stands for a value from your
call. Registration errors raise at import, where the check file is; the rest raise from
the call named.

| Raised by | Message |
|---|---|
| `register_check` | `Check code must be a non-empty string, got <code>.` |
| `register_check` | `Check '<code>': message must be the text a person sees on failure.` |
| `register_check` | `Duplicate check code '<code>' (registering <module>.<function>). Codes are permanent identifiers and must be unique.` |
| `register_check` | `Check '<code>': depends_on must be a list of check codes, got '<text>'. A bare string is a list of its characters, which is never what you meant.` |
| `register_check` | `Check '<code>': default_enabled must be True or False, got <value>.` |
| `register_check` | `Check '<code>': <function>(<parameters>) must take (row) or (row, context), not 3 positional argument(s).` |
| `register_check` | `Check '<code>': <function>(<parameters>) needs keyword argument(s) <names> that the engine cannot supply. Give them defaults, or read them from the row or the context.` |
| `register_check` | `Check '<code>': age_below(row, limit=130) has a default on its second parameter, 'limit', which would be handed the row's context. Bind the value with functools.partial, or make it keyword-only by putting it after a *.` |
| `load_checks` | `load_checks takes a list of paths, not one string: pass ['<path>']. A bare string would be read as a list of its characters.` |
| `load_checks` | `Cannot import '<path>' as a Python file.` |
| `load_checks`, and the first run after a registration | `Check '<code>' depends on '<prerequisite>', which is not registered. Either the code is a typo, or it lives in a check file that was not loaded (currently loaded: <files>). Loading the missing file works; correcting an already-loaded one does not, because load_checks skips a path it has already read -- call clear_registry() first.` |
| the same | `Dependency cycle among checks: A -> B -> A` |
| the same | `Dependency chain too deep to resolve among <n> checks: the ordering walk is recursive and gives out near Python's recursion limit of <limit> (widest declared depends_on: <n>). Shorten the chain, or register prerequisites before the checks that depend on them.` |
| `explain_row`, `validate_row`, `validate` | `on_error must be 'record' or 'raise', got '<value>'.` |
| `explain_row`, `validate_row` | `A row must be a pandas Series -- one row of a DataFrame -- got <type>; for a whole frame, call validate.` |
| `explain_row`, `validate_row` | `Row has duplicate column labels <labels>: a check reading one of them would be handed a Series instead of a value. Rename or drop the duplicate columns before validating.` |
| `validate` | `validate takes a DataFrame, got <type>; for one row, call validate_row or explain_row.` |
| `validate` | `context_builder '<name>' must take (row) or (row, context_args), not 3 positional argument(s).` |
| `validate` | `context_builder '<name>' needs keyword argument(s) <names> that validate cannot supply. Give them defaults, or read them from context_args.` |
| `validate` | `context_builder 'build' has a default on its second parameter, 'strict', which would be handed context_args. Read the value from context_args, or make it keyword-only by putting it after a *.` |
| a check's return, as the engine reads it | `Check '<code>' returned None. A check must return OK or a Verdict; Verdict(condition) wraps a bare comparison.` |
| `Verdict` | `Verdict status must be a Status value or a bool, got '<value>'.` |
| `Verdict` | `Unknown status 7. Use one of: Status.PASS, Status.MISSING, Status.MALFORMED, Status.INVALID, Status.ERROR.` |
| `Verdict` | `Status.ERROR is the engine's, not a check's: it marks a check that raised. Raise the exception, or return a failure kind that describes the data.` |
| `Verdict` | `Verdict comments must be a mapping, got <value>.` |
| `Verdict` | `Verdict comment keys must be strings, got <key>.` |
| `build_report` | `outcomes cover 1 row(s) but the frame has 2: pass the same frame the outcomes were collected from.` |
| `build_report`, `row_explanation` | `include must be one of failures, blocked, all, got '<value>'.` |
| `build_report`, `summarize_outcomes` | `<function> needs every check's outcome on every row, but the list for row <n> holds <n> and the one before it <n>: pass validate's result, or explain_row's per row. validate_row keeps only the failures.` |
| `build_report` | `key_column '<name>' is not in the data. Available columns: <columns>.` |
| `build_report` | `key_column '<name>' appears 2 times in the data: df[key_column] is then a table rather than a column, and every row would be labeled with the column name. Rename or drop the duplicate columns.` |
| any table's `add_columns` | `add_columns ['<name>'] cannot be used for <table>. Each name must be asked for once and be one of: <columns>.` |
| `render` | `fmt must be 'table' or 'csv', got '<value>'.` |
## Stability

Pre-1.0: the API may change between versions. The parts most likely to stay fixed
are check codes, status values, the `(row, context)` signature, and the rule YAML
schema, since data written against them outlives the code.

## References

| # | Section | What it covers |
|---|---|---|
| 1 | [concepts.md: What a check says](concepts.md#what-a-check-says-and-what-the-engine-records) | status against outcome: why a failure has a kind but no "failed" status |
| 2 | [writing-checks.md: Statuses](writing-checks.md#statuses) | which status to choose |
| 3 | [writing-checks.md: What to return](writing-checks.md#what-to-return) | every form a check may return |
| 4 | [Error messages](#error-messages) | each message, quoted |
| 5 | [reporting.md: Diagnosing one row](reporting.md#diagnosing-one-row) | the outcomes as a row's explanation shows them |
| 6 | [writing-checks.md: Per-row context](writing-checks.md#per-row-context) | writing a context and its builder |
| 7 | [configuration.md: Errors](configuration.md#errors) | the file-not-found messages, and the rule file's |
| 8 | [writing-checks.md: Bundles](writing-checks.md#bundles-one-file-that-loads-the-rest) | writing one, and the traps |
| 9 | [writing-checks.md: Layering](writing-checks.md#layering-one-problem-one-error) | why checks depend on each other at all |
| 10 | [configuration.md: Precedence](configuration.md#precedence-last-rule-wins) | last rule wins, with an example |
| 11 | [configuration.md: Setup files](configuration.md#setup-files-naming-the-checks-and-the-rules-at-once) | the setup messages, quoted |
| 12 | [configuration.md: Warnings](configuration.md#warnings) | the three warning lines, quoted |
| 13 | [configuration.md: Disabling a check](configuration.md#disabling-a-check-disables-what-depends-on-it) | why a disabled prerequisite silences its dependents |
| 14 | [reporting.md: Cost](reporting.md#cost) | what the report path holds in memory |
| 15 | [reporting.md: What to include](reporting.md#what-to-include) | the three levels, with output |
| 16 | [reporting.md: Diagnosing a whole file](reporting.md#diagnosing-a-whole-file) | reading the summary |
| 17 | [reporting.md: Working with the tables](reporting.md#working-with-the-tables) | filtering and printing the tables |
| 18 | [reporting.md: Opening the CSV](reporting.md#opening-the-csv-in-a-spreadsheet) | what is escaped, and why |
| 19 | [writing-checks.md: Reading a value safely](writing-checks.md#reading-a-value-safely) | `is_null` in a check |
