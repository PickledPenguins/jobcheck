# Interfaces

Everything here is exported from the `jobcheck` package and is the stable
surface. Names prefixed with `_` are internal and may change.

Back to the [README](../README.md). Authoring guidance is in
[writing-checks.md](writing-checks.md), the report in [reporting.md](reporting.md),
and the rule file format in [configuration.md](configuration.md).

`jobcheck.__version__` is the package version, pre-1.0: the API may change
between versions, while check codes, status values and the override YAML schema
are treated as permanent.

## Data types

### `Status`

`IntEnum` of failure kinds: `PASS` 0, `MISSING` 1, `MALFORMED` 2, `INVALID` 3,
`ERROR` 9. Zero is a pass; every other value is a failure. The vocabulary is
fixed: these five are the whole of it, and a value outside them is refused.

- `render_status(code) -> str` (`"INVALID (3)"`).
- `normalise_result(returned, code) -> CheckResult` — the boundary the engine puts
  every return value through: a `CheckResult` passes straight back, a bool or a
  status value is converted, anything else raises naming the check. Exported so a
  wrapper around checks can accept the same shapes.

### `CheckResult`

What a check returns. Frozen dataclass: `code: int = Status.PASS`,
`comments: Mapping[str, Any] = {}`.

- `bool(result)` is **True when the check passed**; `.passed` and `.failed` say it
  explicitly. The raw `code` is not a truthiness source — 0 is a pass but falsy.
- `.status` is the status name.
- Comments are copied and frozen at construction, so a shared result cannot be
  mutated through the dict a caller passed in.
- Construction validates: a value outside `Status`, `Status.ERROR` (the engine's, not
  a check's), a bool as the code, a non-mapping `comments`, or a non-string comment
  key all raise.
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
`default_enabled`, `description`, `depends_on`, `layer`. Created by the
decorator, never by hand. `layer` is computed by `validate_registry`.

`CHECKS` is the live registry list, in registration order. Read it freely; mutate
it only through the decorators and `clear_registry`.

### `RowContext`

Per-row metadata kept out of the DataFrame: `flags`, `paths`, `state`, `extra`,
each a dict. `build_context(row) -> RowContext` is the adopter's hook and ships
as a stub.

### `MatchCriterion`, `OverrideRule`

A rule's `{column, pattern}` filter, and the rule itself: `name`, `action`,
`codes`, `criteria`, `match_all`, `description`, `source_file`.

## Registering checks

### `register_check(code, message, default_enabled=True, description="", depends_on=None)`

Decorator. The function takes `(row)` or `(row, ctx)` and returns `PASS`, a
`CheckResult`, a bool, or a `Status` value.

Raises at import for a duplicate code, an empty code or message, a non-list
`depends_on` (a bare string would otherwise register one prerequisite per
character), a non-string `description`, a non-bool `default_enabled`,
or a signature the engine cannot call -- including a required keyword-only
argument. The `depends_on` *codes* are checked later by `validate_registry`,
since a prerequisite may live in a module not yet imported.

### `load_checks(paths: str | list[str]) -> None`

Imports the named `.py` files by path so their checks register themselves. One
path or several; **nothing is discovered**, which is what lets two entry points in
one codebase run different sets of checks. A file already loaded, or listed twice,
is skipped. `validate_registry` runs once the whole call has been imported, so a
prerequisite may live in any of the files. Raises `ValueError` for a path that is
not a file, and propagates whatever a file raises while importing.

Each file is given a unique module name, so two directories that each hold a
`checks.py` both load. No `__pycache__` is written beside the file: a check file
comes from wherever the caller names, which is a record of what was read rather
than somewhere to write to.

### `loaded_files() -> list[str]`

The resolved paths loaded that way, in load order. A copy.

### `validate_registry() -> None`, `clear_registry() -> None`

`validate_registry` checks every `depends_on` edge, detects cycles, computes
layers, and caches the evaluation order. An unregistered prerequisite raises —
including one living in a check file that was not loaded, deliberately as loud as
a typo.

`clear_registry` empties the registry and evicts the modules that registered
checks from `sys.modules`, so a later `load_checks` re-registers rather than
silently doing nothing.

## Loading override rules

`load_overrides(paths)` takes one path or a list of them, exactly as
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

### `explain_row(row, ctx=None, overrides=None, on_error="record") -> list[CheckOutcome]`

What every check did on one row, in evaluation order. The single implementation of
the per-row algorithm.

`on_error="record"` turns an exception inside a check into a `Status.ERROR`
outcome and continues; `"raise"` propagates it. A check returning something that is
not a result always raises — that is an authoring bug, not a data problem.

Raises `ValueError` when the row has duplicate column labels, before running
anything.

### `validate_row(row, ctx=None, overrides=None, on_error="record") -> list[CheckOutcome]`

The failing outcomes from `explain_row`, in evaluation order. Does not mutate `row`
or `ctx`. For the one to read first, ask `root_cause`.

### `root_cause(outcomes) -> str | None`, `root_causes(outcomes) -> list[str]`

`root_causes` returns **every** failure at the shallowest failing layer, in
evaluation order: two chains failing at the same depth are two root causes, and
naming only the first evaluated would let registration order decide what a
person reads as the cause. Deeper failures are excluded as downstream — a check
only runs once its prerequisites passed. Empty for a row that passed.

`root_cause` returns one of them, for a caller that wants a single label per row
(a tally, a column in a frame), or `None`. Both accept either `validate_row` or
`explain_row` output.

### `resolve_enabled_state(row, overrides) -> dict[str, bool]`

The effective on/off state of every registered code for one row: each check's
`default_enabled`, then every matching rule in order, last match winning.

### `check_rule_columns(df, overrides) -> list[str]`

One line per rule criterion naming a column the frame lacks — a rule that can
never fire. Checks are not checked: they read the row themselves, so a missing
field raises and is recorded as an `ERROR` outcome naming the column.

### `validate(df, overrides=None, context_builder=build_context, on_error="record") -> list[list[CheckOutcome]]`

Every check against every row: one `explain_row` call per row, and one list of
outcomes per row, in frame order. That is the shape `build_report` and
`summarise_outcomes` take.

`context_builder` is called once per row and returns the `RowContext` handed to
every check; hand back one shared object when a check needs the whole frame.

It keeps one outcome per check per row, so for a frame where that will not fit in
memory, call `validate_row(row)` per row instead and write the failures out as
they appear.

## Reporting

`build_report(outcomes_per_row, df=None, key_column=None, data_columns=None,
include_skipped=False, include_passed=False)` — `data_columns` copies frame
columns into the report just after `row`; see
[reporting.md](reporting.md#showing-data-alongside-the-failures).

`build_report`, `render_report`, `render_comments`,
`escape_for_spreadsheet`, `write_report`,
`print_report`, `row_explanation`, `print_row_explanation`, `summarise_outcomes`,
`root_cause_counts`, `print_summary` — all exported from `jobcheck` and
documented in [reporting.md](reporting.md).

Registry tables:

- `get_registry_table(debug=0)` — one row per check, sorted layer, then code.
  Columns `code`, `layer`, `default_state`, `description`, `depends_on`; plus
  `source_file` at `debug >= 2`.
- `print_registry(overrides=None, debug=0)` — prints it. At `debug >= 1` adds
  `could_be_overridden_by`: rules that *reference* each code. Not "was overridden
  by" — whether a rule fires is a per-row question this table cannot answer.
- `print_registry_with_overrides(overrides, debug=0)` — adds `override_rules` and
  `effective_state`, which says `DEFAULT (ON)` when no rule references the code
  and "depends on row" when one does.
- `print_override_rules(overrides, debug=0)` — one row per rule: `name`,
  `action`, `codes_hit_count`, `match`; plus `source_file` at `debug >= 2`.

`format_table(df, wrap_columns=None)` renders any frame as bordered text;
`is_null(value)` is the null check both the engine and the renderer use — reach for
it in your own checks too, since `NaN` is truthy and `pd.isna` returns an array for
list-like values.

## Stability

Pre-1.0 and unversioned. The parts most likely to stay fixed are check codes,
status values, the `(row, ctx)` signature, and the override YAML schema, since
data written against them outlives the code.
