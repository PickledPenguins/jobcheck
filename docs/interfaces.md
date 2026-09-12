# Interfaces

Everything here is exported from the `jobcheck` package and is the stable
surface. Names prefixed with `_` are internal and may change.

Back to the [README](../README.md). Authoring guidance is in
[writing-checks.md](writing-checks.md), the report in [reporting.md](reporting.md),
and the rule file format in [configuration.md](configuration.md).

`jobcheck.__version__` is the package version, pre-1.0: the API may change
between versions, while check codes, status values and the override YAML schema
are treated as permanent.

## The short list

Writing checks and running them needs eight names, and nothing else here is
required reading:

`register_check`, `PASS`, `CheckResult`, `Status` for a check file;
`load_checks`, `load_overrides`, `validate` and `build_report` for the pipeline
that runs them. Add `RowContext` when a check needs per-row state the frame does
not carry, and `validate_row` for a frame too large to keep every outcome.

Everything below that is the tooling surface: printing, explaining, counting,
inspecting the registry, and the pieces a wrapper around this library reaches
for. It is exported and supported -- `~/work/ai/jobchain` builds on several of
these names -- but a first check file needs none of it.

## Data types

### `Status`

`IntEnum` of failure kinds: `PASS` 0, `MISSING` 1, `MALFORMED` 2, `INVALID` 3,
`ERROR` 9. Zero is a pass; every other value is a failure. The vocabulary is
fixed: these five are the whole of it, and a value outside them is refused.

- `render_status(code) -> str` (`"INVALID (3)"`).
- `normalize_result(returned, code) -> CheckResult` — the boundary the engine puts
  every return value through: a `CheckResult` passes straight back, a bool or a
  status value is converted, anything else raises naming the check. Exported so a
  wrapper around checks can accept the same shapes.

### `CheckResult`

What a check returns. Frozen dataclass: `status: int = Status.PASS`,
`comments: Mapping[str, Any] = {}`.

- `bool(result)` is **True when the check passed**; `.failed` says the opposite
  explicitly. The raw `status` is not a truthiness source — 0 is a pass but falsy.
- A **bool** is accepted in place of a status, so a check can wrap a bare
  comparison: `CheckResult(row["age"] > 0)` is a pass or an `INVALID` failure. It is
  resolved before anything reads the value as an integer, since `True == 1 ==
  MISSING` would otherwise invert the meaning. A check wanting `MISSING` or
  `MALFORMED` names it.
- Comments are copied and frozen at construction, so a shared result cannot be
  mutated through the dict a caller passed in.
- Construction validates: a value outside `Status`, `Status.ERROR` (the engine's, not
  a check's), a non-integer non-bool status, a non-mapping `comments`, or a
  non-string comment key all raise.
- `PASS` is the shared, immutable passing result.

### `CheckOutcome`

What the engine recorded for one check on one row: `code` (the check code),
`outcome` (`passed`, `failed`, `disabled`, `skipped`, `errored`), `status` (a
`Status` value), `layer`, `message`, `detail`, `comments`.

`.failed` is True for `failed` and `errored`; `.status_label` renders as
`INVALID (3)`. `detail` explains the three non-evaluating outcomes: which rule
disabled it, which prerequisites blocked it, or what it raised.

The outcome strings are also exported as `PASSED`, `FAILED`, `DISABLED`,
`SKIPPED`, `ERRORED`.

### `Check`

One registered check: `code`, `message`, `fn`, `source_file`,
`default_enabled`, `depends_on`, `layer`. Created by the decorator, never by
hand. `layer` is computed by `validate_registry`. What a check is *for* is its
`message`, printed wherever it fails and shown in the registry table; there is no
second description field to keep in step with it.

`CHECKS` is the live registry list, in registration order. Read it freely; mutate
it only through the decorators and `clear_registry`.

### `RowContext`

Per-row metadata kept out of the DataFrame. **Bare**: the library defines the type
and no fields. Subclass it, add what your checks read, and build it however suits
the pipeline — a classmethod, a factory, or one object built outside the loop.
Whatever builds it is `validate`'s `context_builder`, a callable taking the row and
returning a `RowContext`. Without one, every row is handed the same empty context.

### `MatchCriterion`, `OverrideRule`

A rule's `{column, pattern}` filter, and the rule itself: `name`, `action`,
`codes`, `criteria`, `match_all`, `message`, `source_file`.

## Registering checks

### `register_check(code, message, default_enabled=True, depends_on=None)`

Decorator. The function takes `(row)` or `(row, context)` and returns `PASS` or a
`CheckResult` — `CheckResult(condition)` wraps a bare comparison.

Raises at import for a duplicate code, an empty code or message, a non-list
`depends_on` (a bare string would otherwise register one prerequisite per
character), a non-bool `default_enabled`,
or a signature the engine cannot call -- including a required keyword-only
argument. The `depends_on` *codes* are checked later by `validate_registry`,
since a prerequisite may live in a module not yet imported.

### `load_checks(paths: list[str]) -> None`

Imports the named `.py` files by path so their checks register themselves. A list
of paths, always — a bare string is refused, since it would otherwise be read as a
list of its characters. **Nothing is discovered**, which is what lets two entry
points in one codebase run different sets of checks. A file already loaded, or listed twice,
is skipped. `validate_registry` runs once the whole call has been imported, so a
prerequisite may live in any of the files. Raises `ValueError` for a path that is
not a file, and propagates whatever a file raises while importing.

Each file is given a unique module name, so two directories that each hold a
`checks.py` both load. No `__pycache__` is written beside the file: a check file
comes from wherever the caller names, which is a record of what was read rather
than somewhere to write to.

### `loaded_check_files() -> list[str]`

The resolved paths loaded that way, in load order. A copy.

### `validate_registry() -> None`, `clear_registry() -> None`

`validate_registry` checks every `depends_on` edge, detects cycles, computes
layers, and caches the evaluation order. An unregistered prerequisite raises —
including one living in a check file that was not loaded, deliberately as loud as
a typo. A chain too deep for the ordering walk (thousands of checks, each
registered before the prerequisite it names) raises `ValueError` naming the
registry size, rather than a bare `RecursionError` naming nothing.

`snapshot() -> dict` copies the whole registry and `restore(state)` puts it back,
dropping whatever is there now. One place owns what registry state *is*, which is
what a caller wanting a throwaway registry needs; the test suite takes one per
test.

`clear_registry` empties the registry and evicts the modules that registered
checks from `sys.modules`, so a later `load_checks` re-registers rather than
silently doing nothing.

## Loading override rules

`load_overrides(paths)` takes a list of paths, exactly as
`load_checks` does, and returns `list[OverrideRule]` in the order given — which is
the precedence order, since the last matching rule wins. It raises `ValueError` at
load time for every malformed rule, and for a rule name used twice anywhere in the
call. It is a thin wrapper over `jobcheck.rules`, which holds the format and its
parser and is handed the codes that exist rather than reaching into the registry.
Load the check files first: a rule naming an unregistered code is an error. See
[configuration.md](configuration.md).

`list_rule_codes(rule_name, overrides) -> list[str]` prints and returns the codes
one named rule touches.

## Running checks

### `explain_row(row, context=None, overrides=None, on_error="record") -> list[CheckOutcome]`

What every check did on one row, in evaluation order. The single implementation of
the per-row algorithm.

`on_error="record"` turns an exception inside a check into a `Status.ERROR`
outcome and continues; `"raise"` propagates it. A check returning something that is
not a result always raises — that is an authoring bug, not a data problem.

Raises `ValueError` when the row has duplicate column labels, before running
anything.

### `validate_row(row, context=None, overrides=None, on_error="record") -> list[CheckOutcome]`

The failing outcomes from `explain_row`, in evaluation order. Does not mutate `row`
or `context`. For the one to read first, ask `root_causes`.

### `root_causes(row_outcomes) -> list[str]`

`root_causes` returns **every** failure at the shallowest failing layer, in
evaluation order: two chains failing at the same depth are two root causes, and
naming only the first evaluated would let registration order decide what a
person reads as the cause. Deeper failures are excluded as downstream — a check
only runs once its prerequisites passed. Empty for a row that passed.

A caller wanting a single label per row (a tally, a column in a frame) takes the
first. Accepts either `validate_row` or `explain_row` output.

### `resolve_enabled_state(row, overrides) -> dict[str, tuple[bool, str]]`

The effective on/off state of every registered code for one row, and why: each
check's `default_enabled`, then every matching rule in order, last match winning.
The reason is `"default"`, `"off by default"`, or `"rule 'name'"` — which is what
an explanation prints beside a `disabled` outcome.

### `check_override_columns(df, overrides) -> list[str]`

One line per rule criterion naming a column the frame lacks — a rule that can
never fire. Checks are not checked: they read the row themselves, so a missing
field raises and is recorded as an `ERROR` outcome naming the column.

### `validate(df, overrides=None, context_builder=None, on_error="record") -> list[list[CheckOutcome]]`

Every check against every row: one `explain_row` call per row, and one list of
outcomes per row, in frame order. That is the shape `build_report` and
`summarize_outcomes` take.

`context_builder` is called once per row and returns the `RowContext` handed to
every check; hand back one shared object when a check needs the whole frame.
Without one, every row is handed the same empty `RowContext`.

It keeps one outcome per check per row, so for a frame where that will not fit in
memory, call `validate_row(row)` per row instead and write the failures out as
they appear.

## Reporting

`build_report(frame_outcomes, df, key_column=None, extra_columns=None,
include="failures")` — `df` is required, since the outcomes describe its rows;
`key_column` names the single column that identifies a row — one that is not in the
frame, or is in it more than once, raises `ValueError`; `extra_columns` copies
frame columns into the report just after `row`; `include` is `"failures"`,
`"blocked"` or `"all"`. See
[reporting.md](reporting.md#showing-data-alongside-the-failures).

`build_report`, `render_report`, `render_comments`,
`escape_for_spreadsheet`, `write_report`,
`print_report`, `row_explanation`, `print_row_explanation`, `summarize_outcomes`,
`root_cause_counts`, `print_summary` — all exported from `jobcheck` and
documented in [reporting.md](reporting.md).

Registry tables:

Every one of these takes `extra_columns`, the same argument `build_report` takes
for columns of the data: the names you want beyond the base columns, refused
rather than ignored when the name is not on offer.

- `get_registry_table(extra_columns=None)` — one row per check, sorted layer, then
  code. Columns `code`, `layer`, `default`, `message`, `depends_on`; offers
  `source_file`.
- `print_registry(overrides=None, extra_columns=None)` — prints it. Offers
  `source_file`, plus the two columns that read the loaded rules:
  `could_be_overridden_by`, the rules that *reference* each code with the action
  each would take, and `effective_state`, which says `DEFAULT (ON)` when no rule
  references the code and "depends on row" when one does. Neither is "was
  overridden by" — whether a rule fires is a per-row question this table cannot
  answer. `overrides` feeds those two columns and nothing else, so passing rules
  without asking for either prints the same table as passing none.
- `print_override_rules(overrides, extra_columns=None)` — one row per rule:
  `name`, `action`, `codes_hit_count`, `match`, `message`. Offers `source_file`.

`format_table(table, wrap_columns=None)` renders any frame as bordered text;
`is_null(value)` is the null check both the engine and the renderer use — reach for
it in your own checks too, since `NaN` is truthy and `pd.isna` returns an array for
list-like values.

## Stability

Pre-1.0 and unversioned. The parts most likely to stay fixed are check codes,
status values, the `(row, ctx)` signature, and the override YAML schema, since
data written against them outlives the code.
