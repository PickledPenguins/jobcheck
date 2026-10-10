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
not carry.

Everything below that is the tooling surface: printing, explaining, counting,
inspecting the registry, and the pieces a wrapper around this library reaches
for. It is exported and supported -- jobchain, the pipeline runner built on this
library, uses several of these names -- but a first check file needs none of it.

## At a glance

Every exported name, one line each, grouped by the step it belongs to; the name links
to its full entry below. **Required** arguments are positional and have no default;
**Optional** ones show their default. A dash means none.

**Writing checks**

| Name | Required | Optional (default) | Returns | What it does |
|---|---|---|---|---|
| [`register_check`](#register_checkcode-message-default_enabledtrue-depends_onnone-repeatfalse) | `code`, `message` | `default_enabled=True`, `depends_on=None`, `repeat=False` | decorator | Registers a `(row)` or `(row, context)` function as check `code`; `message` is what a failure prints. `default_enabled=False` keeps it off until a rule enables it. `depends_on` lists codes that must pass before it runs. `repeat=True` runs it, and its dependents, on every copy of a row under `validate(repeat_key=...)`. Bad arguments raise at import. |
| [`is_null`](#is_nullvalue---bool) | `value` | – | `bool` | True for `None`, `NaN`, `NaT` and `pd.NA`; never for a list or array. The safe blank test inside a check. |

**Loading checks and rules**

| Name | Required | Optional (default) | Returns | What it does |
|---|---|---|---|---|
| [`load_checks`](#load_checkspaths-liststr-base_dir-str--path--none--none---none) | `paths` | `base_dir=None` | `None` | Imports the listed `.py` files so their checks register. Nothing is discovered. Relative paths resolve against `base_dir`, else the working directory. A file already loaded is skipped. Validates the dependency graph on return. |
| [`load_rules`](#loading-rules) | `paths` | `base_dir=None` | `list[Rule]` | Parses rule YAML files, paths resolved as `load_checks` does. List order is precedence: the last matching rule wins. Load checks first; an unknown code raises. |
| [`load_setup`](#loading-both-at-once) | `path` | – | `list[Rule]` | Reads one YAML file naming `checks` (required) and `rules` (optional), resolved against that file's directory. Loads the checks, returns the rules. |
| [`clear_registry`](#clear_registry---none) | – | – | `None` | Empties the registry and drops the check-file modules, so the next `load_checks` registers afresh. For tests, or loading a different set in one process. |

**Running checks**

| Name | Required | Optional (default) | Returns | What it does |
|---|---|---|---|---|
| [`validate`](#validatedf-rulesnone-context_buildernone-on_errorrecord-context_argsnone-repeat_keynone---listlistcheckoutcome) | `df` | `rules=None`, `context_builder=None`, `on_error="record"`, `context_args=None`, `repeat_key=None` | `list[list[CheckOutcome]]` | Every check on every row of a DataFrame; one complete outcome list per row, in frame order. `context_builder` builds each row's `RowContext` from `(row)` or `(row, context_args)`. `on_error="raise"` propagates a check's exception instead of recording it as `errored`. `repeat_key` names the column marking copies of one row: a copy runs only the checks that repeat, and shares the rest. Holds every outcome in memory. |

**Checking rule files**

Each returns warning lines and raises nothing; an empty list means no problem.

| Name | Required | Optional (default) | Returns | What it does |
|---|---|---|---|---|
| [`warn_missing_rule_columns`](#warn_missing_rule_columnsdf-rules---liststr) | `df`, `rules` | – | `list[str]` | One line per rule criterion naming a column `df` lacks: a rule that can never fire. |
| [`warn_shadowed_rules`](#warn_shadowed_rulesrules---liststr) | `rules` | – | `list[str]` | One line per rule and code that a later `match: all` rule overrules on every row. |
| [`warn_blocking_rules`](#warn_blocking_rulesrules---liststr) | `rules` | – | `list[str]` | One line per disable rule and code whose dependents it silently skips without listing them. Reads the registry, so load the checks first. |

**Reporting**

Every table is a DataFrame titled in `attrs["title"]`; pandas prints any of them
(`to_string()`, `to_csv()`). The report is indexed by the row key, the added columns and
`code`, and keeps that index; the others drop their plain one with `index=False`.

| Name | Required | Optional (default) | Returns | What it does |
|---|---|---|---|---|
| [`build_report`](#build_reportframe_outcomes-df-key_columnnone-add_columnsnone-includefailures---dataframe) | `frame_outcomes`, `df` | `key_column=None`, `add_columns=None`, `include="failures"` | DataFrame `Report` | The long-format report: one line per outcome per data row, indexed by the row key, the `add_columns`, then `code`. `key_column` labels rows and names the key level (default: the index, named `row`); `add_columns` copies frame columns in; `include` is `"root_causes"`, `"failures"`, `"blocked"` or `"all"`. |
| [`explain_row`](#explain_rowframe_outcomes-position---dataframe) | `frame_outcomes`, `position` | – | DataFrame `Row explanation` | Every check on the data row at `position`, in evaluation order, under the report's columns without `row`. Runs nothing. |
| [`summarize_outcomes`](#summarize_outcomesframe_outcomes---dataframe) | `frame_outcomes` | – | DataFrame `Summary` | Per-check counts across all rows: `failed`, `root_cause_rows`, `errored`, `skipped`, `disabled`, `shared`, `passed`. Takes `validate`'s result, or any iterable of its rows. |
| [`registry_table`](#registry_tablerulesnone---dataframe) | – | `rules=None` | DataFrame `Registry` | One line per registered check: `code`, `layer`, `default`, `repeat`, `message`, `depends_on`, `source_file`, and from `rules`, `could_be_overridden_by`. |
| [`rules_table`](#rules_tablerules---dataframe) | `rules` | – | DataFrame `Rules` | One line per rule: `name`, `action`, `code_count`, `codes`, `match`, `message`, `source_file`. |

**Types and constants**

| Name | Fields or members | What it is |
|---|---|---|
| [`Verdict`](#verdict) | `status=Status.PASS`, `comments={}` | What a check returns. A bool status is accepted: True passes, False is an `INVALID` failure. `comments` is the detail printed with a failure. True in a boolean test when it passed. |
| `OK` | – | The shared passing `Verdict`. |
| [`Status`](#status) | `PASS` 0, `MISSING` 1, `MALFORMED` 2, `INVALID` 3, `ERROR` 9 | `IntEnum` of failure kinds. `ERROR` is the engine's, for a check that raised; a check never returns it. |
| [`CheckOutcome`](#checkoutcome) | `code`, `outcome`, `status`, `layer`, `message`, `detail`, `comments`, `rule` | What the engine recorded for one check on one row. `.failed` covers failed and errored; `detail` says why a check did not run, what it raised, or, on a copy under `repeat_key`, what it did on the first copy and where; `rule` names the rule that switched it on or off. |
| [`Outcome`](#outcome) | `PASSED`, `FAILED`, `DISABLED`, `SKIPPED`, `ERRORED`, `SHARED` | `str` enum of what happened to a check on a row. |
| [`RowContext`](#rowcontext) | none; subclass to add | Per-row state the frame does not carry, handed to `(row, context)` checks. Built by `validate`'s `context_builder`. |
| [`Rule`](#rule) | `name`, `action`, `codes`, `criteria`, `match_all`, `message`, `source_file` | One loaded rule, as `load_rules` returns it. |
| `__version__` | – | The package version string; pre-1.0. |

## Data types

### `Status`

`IntEnum` of failure kinds: `PASS` 0, `MISSING` 1, `MALFORMED` 2, `INVALID` 3,
`ERROR` 9. Zero is a pass; every other value is a failure.<sup>[1](concepts.md#what-a-check-says-and-what-the-engine-records)</sup> The vocabulary is
fixed: these five are the whole of it, and a value outside them is refused.<sup>[2](writing-checks.md#statuses)</sup>

- A check must return a `Verdict`: anything else — a bare bool, a bare `Status`
  value, `None` — raises `TypeError` naming the check, as the engine reads it.

Example: [writing-checks.md: Layering](writing-checks.md#layering-one-problem-one-error),
one status per depth.

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
- Construction validates: a value outside `Status` (a string included), `Status.ERROR`
  (the engine's, not a check's), or a non-mapping `comments` raises.<sup>[4](#error-messages)</sup>
- `OK` is the shared passing result.

Example: [writing-checks.md: The shape of a check](writing-checks.md#the-shape-of-a-check).

### `CheckOutcome`

What the engine recorded for one check on one row: `code` (the check code),
`outcome` (an `Outcome`), `status` (a
`Status` value), `layer`, `message`, `detail`, `comments`, `rule`.

`.failed` is True for `failed` and `errored`; `.status_label` renders as
`INVALID (3)`. `detail` explains the four non-evaluating outcomes: which rule
disabled it, which prerequisites blocked it, what it raised, or, for `shared`, what it
did on the copy that ran it and where that copy is. What it raised reads `Type: text
(file.py:line)`: the innermost line in the file the check was written in, and no colon
when the exception has no text. A `shared` outcome's status is `PASS`, as
for `skipped` and `disabled`, and it has no message or comments. An `errored` outcome's
`message` is the fixed text `check raised; see detail`, not the check's message.
`rule` names the rule that switched the check on or off for the row, enable or
disable, whatever the outcome; it is `""` where the check's default stood.<sup>[1](concepts.md#what-a-check-says-and-what-the-engine-records)</sup>

```python
# Why nothing fired on the fifth row: each check that never ran, and the rule
# that decided it, if any.
for outcome in outcomes[4]:
    if outcome.outcome in (Outcome.SKIPPED, Outcome.DISABLED):
        print(outcome.code, outcome.detail, outcome.rule or "(default)")
```

### `Outcome`

What happened to a check on a row: `Outcome.PASSED`, `FAILED`, `DISABLED`, `SKIPPED`,
`ERRORED`, `SHARED`, whose values are `passed`, `failed`, `disabled`, `skipped`,
`errored`, `shared`. `SHARED` marks a copy of a row reusing an earlier copy's result for
a check that does not repeat. A
`str` as well, so `outcome.outcome == "failed"` holds, and a misspelled member is an
`AttributeError`. `CheckOutcome` accepts the plain string and refuses one that is
not an outcome. Write `.value` where the text is wanted: formatting a member prints
`Outcome.FAILED` on Python 3.11 and later, and `failed` on 3.10.<sup>[5](reporting.md#diagnosing-one-row)</sup>

Example: [reporting.md: Working with the tables](reporting.md#working-with-the-tables),
selecting rows by outcome.

### The registry

Each registered check has a `code`, `message`, `fn`, `source_file`,
`default_enabled`, `depends_on`, `repeat`, `layer` and whether it repeats, created by
the decorator and computed with the evaluation order. What a check
is *for* is its `message`, printed wherever it fails and shown in the registry
table; there is no second description field to keep in step with it.

The registry itself is internal (`registry._CHECKS`). Read it through
`registry_table`, which gives every check's code, layer, default, repeat, message,
`depends_on`, `source_file` and `could_be_overridden_by` as a frame. `source_file` is `<unknown>` for
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
`AttributeError`, which the engine records as `errored`. A subclass without
`__slots__` of its own has a `__dict__` and takes any attribute; one that declares
`__slots__` takes only those.

Example: [writing-checks.md: Per-row context](writing-checks.md#per-row-context).

### `Rule`

One loaded rule: `name`, `action`, `codes`, `criteria`, `match_all`, `message`,
`source_file`. Each of `criteria` has a `column`, the `pattern` as written, and the
compiled `regex`; its type is internal, because nothing but the rule parser builds one.

```python
# What each loaded rule does, and on which rows.
for rule in rules:
    where = "every row" if rule.match_all else ", ".join(
        f"{criterion.column} ~ {criterion.pattern}" for criterion in rule.criteria)
    print(f"{rule.name}: {rule.action} {', '.join(rule.codes)} on {where}")
```

## Registering checks

### `register_check(code, message, default_enabled=True, depends_on=None, repeat=False)`

Decorator. The function takes `(row)` or `(row, context)` and returns `OK` or a
`Verdict` — `Verdict(condition)` wraps a bare comparison.

`repeat=True` matters only under `validate(repeat_key=...)`: the check runs on every
copy of a row, not only the first, and so does every check that depends on it, directly
or through another. The rest run once per `repeat_key` value.

Raises at import for a duplicate code, an empty code or message, a non-list
`depends_on` (a bare string would otherwise register one prerequisite per
character), a non-bool `default_enabled` or `repeat`,
or a signature the engine cannot call -- including a required keyword-only
argument, and a second positional parameter with a default other than `None`, which
would be handed the context (`def age_below(row, limit=130)`; write `*, limit=130` or
use `functools.partial`). A context builder is refused the same way. The `depends_on`
*codes* are checked later, when the dependency graph is validated, since a prerequisite
may live in a module not yet imported.<sup>[4](#error-messages)</sup>

Example: [writing-checks.md: The shape of a check](writing-checks.md#the-shape-of-a-check).

### `load_checks(paths: list[str], base_dir: str | Path | None = None) -> None`

Imports the named `.py` files by path so their checks register themselves. A list
of paths, always — a bare string is refused, since it would otherwise be read as a
list of its characters. **Nothing is discovered**, which is what lets two entry
points in one codebase run different sets of checks. A file listed twice, or already
loaded, raises before any file is imported; a process that loads again calls
`clear_registry()` first. The dependency graph is validated once the whole call has been
imported, so a prerequisite may live in any of the files, in any order, or in a file an
earlier call loaded.<sup>[7](writing-checks.md#check-files-that-depend-on-each-other)</sup> A relative path is resolved against
`base_dir` when one is given and against the working directory otherwise; an
absolute path ignores both. Raises `ValueError` for a path that is not a file,
naming the absolute path it tried, and for a file without a `.py` suffix
(`Cannot import '<path>' as a Python file.`), and propagates whatever a file raises
while importing. A file that raises is not rolled back: the checks registered before
the failing line stay, and the file is not recorded as loaded.<sup>[8](configuration.md#errors)</sup>

Each file's module name comes from its path (`jobcheck_check_file_<stem>_<8 hex digits>`),
the same every run, so two directories that each hold a `checks.py` both load. No
`__pycache__` is written beside the file: a check file comes from wherever the
caller names, which is a record of what was read rather than somewhere to write
to. Only the check file goes without bytecode; a module it imports is cached as usual.

### When the dependency graph is validated

The dependency graph is validated when `load_checks` returns, and otherwise when
something first needs the evaluation order (`validate` on a frame with rows,
`registry_table`). Every `depends_on` edge is checked, cycles detected, layers
computed. An unregistered prerequisite raises — including one living in a check
file that was not loaded, deliberately as loud as a typo. The ordering walk is
recursive, so a chain about 900 links deep (Python's default recursion limit is 1000)
raises a plain `RecursionError` from `_topological_order`.<sup>[9](writing-checks.md#layering-one-problem-one-error)</sup>

### `clear_registry() -> None`

Empties the registry and drops the modules `load_checks` made for check files from
`sys.modules`, and no other module. A later `load_checks` runs each file again and
re-registers; a module a check file only imports stays cached and registers nothing
again, so register checks in the files `load_checks` is given. It is the whole of the registry-state API: there is no
way to save a registry and put it back, because outside a test there is no use
for one. A caller loads its check files at start-up, or clears and loads a
different set between runs, or runs a second entry point in a second process --
which is what the process-global registry means (see
[architecture](architecture.md)).

```python
from jobcheck import clear_registry, load_checks

# A notebook session after editing a check file: load the set again.
load_checks(["examples/checks/check_age.py"])
clear_registry()
load_checks(["examples/checks/check_age.py"])
```

## Loading rules

`load_rules(paths, base_dir=None)` takes a list of paths and anchors them
exactly as `load_checks` does, and returns `list[Rule]` in the order given — which is
the precedence order, since the last matching rule wins.<sup>[10](configuration.md#precedence-last-rule-wins)</sup> It raises `ValueError` at
load time for every malformed rule, and for a rule name used twice anywhere in the
call; a path that is not a file raises `ValueError` naming it, the way
`load_checks` does, and a file that is not valid YAML, a key written twice in one
mapping included, raises `yaml.YAMLError`, as the file layer reports it. A rule's
`source_file` is the path as the caller wrote it, relative or not: it is printed beside the rule, where an absolute path
resolved out of `base_dir` would name a directory only this machine has.
It is a thin wrapper over `jobcheck.rules`, which holds the format and its
parser and is handed the codes that exist rather than reaching into the registry.
Load the check files first: a rule naming an unregistered code is an error. See
[configuration.md](configuration.md).

Which codes a rule touches is `rule.codes`, and as a column,
`rules_table(rules)["codes"]`.

Example: [writing-checks.md: In a pipeline](writing-checks.md#in-a-pipeline).

## Loading both at once

`load_setup(path) -> list[Rule]` is the whole of configuring this library in one
call: it loads the check files a YAML file names and returns the rules from the rule
files it names.

```yaml
checks:
  - checks/check_age.py
  - checks/check_email.py
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
this composes them, and a caller holding paths of its own has no file to write. `examples/setup.yaml` is the
worked example.

Example: [configuration.md: Setup files](configuration.md#setup-files-naming-the-checks-and-the-rules-at-once).

## Checking rule files

### `warn_missing_rule_columns(df, rules) -> list[str]`

One line per rule criterion naming a column the frame lacks — a rule that can
never fire. Checks are not checked: they read the row themselves, so a missing
field raises and is recorded as an `ERROR` outcome naming the column.<sup>[12](configuration.md#warnings)</sup>

Example: [writing-checks.md: In a pipeline](writing-checks.md#in-a-pipeline).

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

```python
from jobcheck import warn_shadowed_rules

for warning in warn_shadowed_rules(rules):
    print("warning:", warning)
```

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

```python
from jobcheck import load_checks, load_rules, warn_blocking_rules

# A pipeline's start-up: refuse rule files that would silence checks unasked.
load_checks(["examples/checks/check_age.py", "examples/checks/check_email.py"])
problems = warn_blocking_rules(load_rules(["examples/rules/error_rules.yaml"]))
if problems:
    raise SystemExit("\n".join(problems))
```

## Running checks

### `validate(df, rules=None, context_builder=None, on_error="record", context_args=None, repeat_key=None) -> list[list[CheckOutcome]]`

Every check against every row: one list of outcomes per row, in frame order, each
holding what *every* check did -- passed, failed, disabled, skipped, errored or
shared -- in evaluation order. Nothing is filtered: the views below pick what to
show, so every one of them is built from this one result.

`on_error="record"` turns an exception inside a check into a `Status.ERROR`
outcome and continues; `"raise"` propagates it. A check returning something that is
not a result always raises — that is an authoring bug, not a data problem. Does not
mutate the frame.

`context_builder` is called once per row and returns the `RowContext` handed to
every check; hand back one shared object when a check needs the whole frame.
Without one, and for a builder that returns `None`, every row is handed the same
empty `RowContext`.

The builder is not covered by `on_error`: an exception it raises propagates out of
`validate` with its type and message unchanged, and no row's outcomes are returned. It
must not raise on the
data — map a blank cell to `None` and let a presence check report it; see
[writing-checks.md](writing-checks.md#per-row-context).

It takes `(row)` or `(row, context_args)`, settled once per `validate` rather than
per row, the same way a check takes `(row)` or `(row, context)`. `context_args` is
whatever the entry point wants every context built from — its parsed command line,
a connection, a configuration — passed through untouched. A builder taking neither
shape raises `ValueError` naming what it takes, before any row is read.

An `on_error` that is neither `"record"` nor `"raise"` raises `ValueError` before
any row is read, an empty frame included; anything but a `DataFrame` raises
`TypeError`. A frame with duplicate column labels raises `ValueError` before any row is
read, an empty frame included.<sup>[4](#error-messages)</sup>

An exception that escapes while a row is checked -- the builder's, a check's under
`"raise"`, or the `TypeError` for a check that returned no result -- keeps its type and
message and, on Python 3.11 and later, gains a note naming the row, which the traceback
prints below the message: `validate: raised on the row at position 1 (index label 'b').`

`repeat_key` names a column whose repeated values mark copies of one row, as
`DataFrame.explode` makes them. The first row with each value, in frame order, runs
every check. A later copy runs only the checks that repeat
([`register_check`](#register_checkcode-message-default_enabledtrue-depends_onnone-repeatfalse));
every other check is not called, and is recorded `shared`, with status `PASS` and a
`detail` such as `failed at position 0, the first row with id J1`. A repeated
check reads a shared prerequisite's result from the first copy. Rules are matched on
each copy. A copy where a rule disables a check records `disabled`, and its dependents
`skipped`, whether or not the check repeats. A check that does not repeat runs on the
first copy whose rules leave it and its prerequisites enabled; the copies after that one
share its result, with a `detail` ending `the first row with id J1 to enable it` when
that copy is not the first. A key that is not
exactly one column raises `ValueError` before any row is read; a blank value raises
`ValueError`, and a value that cannot be a dictionary key raises `TypeError`, each
naming the position.<sup>[4](#error-messages)</sup> See
[writing-checks.md](writing-checks.md#one-row-many-copies).

It keeps one outcome per check per row; for a frame where that will not fit in
memory, validate it in chunks and write each chunk's report out.<sup>[14](reporting.md#cost)</sup>

Example: [reporting.md: The short version](reporting.md#the-short-version).

## Reporting

Every view is a DataFrame whose `attrs["title"]` names it — `Report`,
`Row explanation`, `Summary`, `Registry`, `Rules` — and pandas turns any of them
into text. Each carries every column it builds, and a caller drops what it does not
want; see [reporting.md](reporting.md#which-columns-a-table-shows). Writing each to a
CSV file is in [reporting.md](reporting.md#writing-the-tables-to-files).

### `build_report(frame_outcomes, df, key_column=None, add_columns=None, include="failures") -> DataFrame`

The long-format report: one line per outcome `include` admits, per data row, in
evaluation order. `df` is required, since the outcomes describe its rows, and must
have one row per list in `frame_outcomes` — otherwise `ValueError`
(`outcomes cover 1 row(s) but the frame has 2: ...`). `key_column` names the single
column that identifies a row — one that is not in the frame, or is in it more than
once, raises `ValueError`; without it the frame's index labels the rows.
`add_columns` copies frame columns into the report; a name not in the frame, named
twice, or colliding with one of the report's own columns raises `ValueError`.

The report is indexed by the row key -- a level named after `key_column`, or `row`
when the frame's index is the key -- then the `add_columns` in the order given, then
`code`. A `key_column` named like one of the report's own columns raises `ValueError`:
`key_column 'code' would head the report's key, but the report already has a column of that name (code, status, layer, outcome, message, detail, comments, rule, is_root_cause). Copy the column under another name and pass that.` `to_string()` prints a row's labels once and hangs its lines beneath them;
`to_csv()` writes every label on every line; `reset_index()` makes them plain
columns. Two data rows with the same label print as one block, so a `key_column`
that is not unique reads as one row in the terminal.

`include` is `"root_causes"`, `"failures"`, `"blocked"` or `"all"`, each holding the
one before it, and anything else raises `ValueError`.<sup>[15](reporting.md#what-to-include)</sup>
Titled `Report`. The columns are in
[reporting.md](reporting.md#shape-one-row-per-failure).

**Root causes.** `is_root_cause`, `include="root_causes"` and the summary's
`root_cause_rows` all read one rule: a row's root causes are **every** failure at
its shallowest failing layer, in evaluation order. Two chains failing at the same
depth are two root causes; naming only the first evaluated would let registration
order decide what a person reads as the cause. Deeper failures are left out as the
ones to read next, not as downstream of these: a check only runs once its
prerequisites passed, so every failure is the root of its own chain. Data failures
come first: an `errored` outcome counts only on a row with no `failed` one, so a
broken check never takes the flag from a real failure, and a row whose only problem
is a broken check is still flagged. A row that passed has none.

Example: [reporting.md: The short version](reporting.md#the-short-version).

### `explain_row(frame_outcomes, position) -> DataFrame`

One line per check on the data row at `position` (0 for the first) of `validate`'s
result, in evaluation order: `code`, `status`, `layer`, `outcome`, `message`, `detail`,
`comments`, `rule`, `is_root_cause` -- the report's columns without `row`, each meaning what
it means there, so the lines equal that row's lines of `build_report(include="all")`.
Every check is shown, passes included; it reads the outcomes and runs nothing. A
`position` outside the outcomes raises `ValueError`.
Titled `Row explanation`.<sup>[5](reporting.md#diagnosing-one-row)</sup>

Example: [reporting.md: Diagnosing one row](reporting.md#diagnosing-one-row).

### `summarize_outcomes(frame_outcomes) -> DataFrame`

Per check, across every row: `code`, `layer`, `failed`, `root_cause_rows`, `errored`,
`skipped`, `disabled`, `shared`, `passed`, sorted by `failed` and then
`root_cause_rows`, most first, then by `layer` and code, so among checks that failed
equally often the root cause comes first. `shared` counts the copies that reused the first copy's
result, so `failed` and `passed` count only the calls made. `root_cause_rows` counts
the rows whose root causes include the
check — an errored check among them on the rows with no data failure, so it can
exceed `failed`. Takes `validate`'s result, or any iterable of its rows, and keeps
only the counts. Titled `Summary`.<sup>[16](reporting.md#diagnosing-a-whole-file)</sup>

Example: [reporting.md: Diagnosing a whole file](reporting.md#diagnosing-a-whole-file).

### `registry_table(rules=None) -> DataFrame`

One row per check, sorted layer, then code, titled `Registry`. Columns `code`,
`layer`, `default`, `repeat` (`declared`, `inherited` from a prerequisite, or `-`),
`message`, `depends_on`, `source_file`, and
`could_be_overridden_by`, the one column that reads `rules`: the rules that
*reference* each code with the action each would take, `-` for none. It is not
"was overridden by" — whether a rule fires is a per-row question this table cannot
answer.<sup>[17](reporting.md#working-with-the-tables)</sup>

Example: [writing-checks.md: Which checks an entry point loads](writing-checks.md#which-checks-an-entry-point-loads).

### `rules_table(rules) -> DataFrame`

One row per rule, titled `Rules`: `name`, `action`, `code_count`, `codes` (the
list behind the count), `match`, `message`, `source_file`.

Example: [reporting.md: Working with the tables](reporting.md#working-with-the-tables).

### `is_null(value) -> bool`

The null check the engine and the tables use — reach for it in your own
checks too, since `NaN` is truthy and `pd.isna` returns an array for list-like
values. `None`, `NaN`, `NaT` and `pd.NA` are null; a list or an array never is.<sup>[18](writing-checks.md#reading-a-value-safely)</sup>

Example: [writing-checks.md: Reading a value safely](writing-checks.md#reading-a-value-safely).

## Error messages

Every message the library raises outside rule and setup files, which
[configuration.md](configuration.md#errors) lists. `<...>` stands for a value from your
call. Registration errors raise at import, where the check file is; the rest raise from
the call named.

| Raised by | Message |
|---|---|
| `register_check` | `Check code must be a non-empty string, got <code>.` |
| `register_check` | `Check '<code>': message must be a non-empty string, got <message>.` |
| `register_check` | `Duplicate check code '<code>' (registering <module>.<function>; already registered from <path>).` |
| `register_check` | `Check '<code>': depends_on must be a list of check codes, got '<text>'.` |
| `register_check` | `Check '<code>': default_enabled must be True or False, got <value>.` |
| `register_check` | `Check '<code>': repeat must be True or False, got <value>.` |
| `register_check` | `Check '<code>': <function>(<parameters>) must take (row) or (row, context), not 3 positional argument(s).` |
| `register_check` | `Check '<code>': <function>(<parameters>) needs keyword argument(s) <names> that the engine cannot supply. Give them defaults, or read them from the row or the context.` |
| `register_check` | `Check '<code>': age_below(row, limit=130) has a default on its second parameter, 'limit', which would be handed the row's context. Bind the value with functools.partial, or make it keyword-only by putting it after a *.` |
| `load_checks` | `load_checks takes a list of paths, not one string: pass ['<path>'].` |
| `load_checks` | `Check file listed twice or already loaded: <path>.` |
| `load_checks` | `Cannot import '<path>' as a Python file.` |
| `load_checks`, and the first run after a registration | `Check '<code>' depends on '<prerequisite>', which is not registered. Either the code is a typo, or it lives in a check file that was not loaded (currently loaded: <files>).` |
| the same | `Dependency cycle among checks: A -> B -> A.` |
| `validate` | `on_error must be 'record' or 'raise', got '<value>'.` |
| `validate` | `Data has duplicate column labels <labels>. Rename or drop the duplicate columns before validating.` |
| `validate` | `validate takes a DataFrame, got <type>.` |
| `validate` | `repeat_key '<name>' is not in the data. Available columns: <columns>.` |
| `validate` | `repeat_key '<name>' appears 2 times in the data. Rename or drop the duplicate columns.` |
| `validate` | `repeat_key '<name>' is blank at position <n>: every row needs a value to say which rows are its copies.` |
| `validate` | `repeat_key '<name>' holds <value> at position <n>, which cannot be compared as a key: use a column of text or numbers.` |
| `validate` | `context_builder '<name>' must take (row) or (row, context_args), not 3 positional argument(s).` |
| `validate` | `context_builder '<name>' needs keyword argument(s) <names> that validate cannot supply. Give them defaults, or read them from context_args.` |
| `validate` | `context_builder 'build' has a default on its second parameter, 'strict', which would be handed context_args. Read the value from context_args, or make it keyword-only by putting it after a *.` |
| a check's return, as the engine reads it | `Check '<code>' returned None. A check must return OK or a Verdict.` |
| `Verdict` | `Unknown status 7.` |
| `Verdict` | `Status.ERROR is the engine's, not a check's: it marks a check that raised. Raise the exception, or return a failure kind that describes the data.` |
| `Verdict` | `Verdict comments must be a mapping, got <value>.` |
| `build_report` | `outcomes cover 1 row(s) but the frame has 2: pass the same frame the outcomes were collected from.` |
| `build_report` | `include must be one of root_causes, failures, blocked, all, got '<value>'.` |
| `build_report` | `key_column '<name>' is not in the data. Available columns: <columns>.` |
| `build_report` | `key_column '<name>' appears 2 times in the data. Rename or drop the duplicate columns.` |
| `build_report`'s `add_columns` | `add_columns ['<name>'] cannot be used for the report. Each name must be asked for once and be one of: <columns>.` |
| `explain_row` | `position 3 is not a row: outcomes cover 3 row(s), numbered from 0.` |

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
| 7 | [writing-checks.md: Check files that depend on each other](writing-checks.md#check-files-that-depend-on-each-other) | what one call allows |
| 8 | [configuration.md: Errors](configuration.md#errors) | the file-not-found messages, and the rule file's |
| 9 | [writing-checks.md: Layering](writing-checks.md#layering-one-problem-one-error) | why checks depend on each other at all |
| 10 | [configuration.md: Precedence](configuration.md#precedence-last-rule-wins) | last rule wins, with an example |
| 11 | [configuration.md: Setup files](configuration.md#setup-files-naming-the-checks-and-the-rules-at-once) | the setup messages, quoted |
| 12 | [configuration.md: Warnings](configuration.md#warnings) | the three warning lines, quoted |
| 13 | [configuration.md: Disabling a check](configuration.md#disabling-a-check-disables-what-depends-on-it) | why a disabled prerequisite silences its dependents |
| 14 | [reporting.md: Cost](reporting.md#cost) | what `validate` holds in memory, and validating in chunks |
| 15 | [reporting.md: What to include](reporting.md#what-to-include) | the four levels |
| 16 | [reporting.md: Diagnosing a whole file](reporting.md#diagnosing-a-whole-file) | reading the summary |
| 17 | [reporting.md: Working with the tables](reporting.md#working-with-the-tables) | filtering and printing the tables |
| 18 | [writing-checks.md: Reading a value safely](writing-checks.md#reading-a-value-safely) | `is_null` in a check |
