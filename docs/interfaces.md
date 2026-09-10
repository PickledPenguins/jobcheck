# Interfaces

Everything here is exported from the `validation` package and is the stable
surface. Names prefixed with `_` are internal and may change.

Back to the [README](../README.md). Authoring guidance is in
[writing-tests.md](writing-tests.md), the report in [reporting.md](reporting.md),
and the rule file format in [configuration.md](configuration.md).

`pandas_row_validation.__version__` is the package version, pre-1.0: the API may change
between versions, while test codes, status values and the override YAML schema
are treated as permanent.

## Data types

### `Status`

`IntEnum` of failure kinds: `PASS` 0, `MISSING` 1, `MALFORMED` 2, `INVALID` 3,
`ERROR` 9. Zero is a pass; every other value is a failure. Values 0–9 are
reserved for these.

- `register_status(name, value) -> int` — add a project kind from 10 upwards.
  Refuses a reserved value, a duplicate value, a duplicate name, a non-integer
  value, or a name that is not an UPPER_CASE identifier. Values are permanent
  identifiers, like test codes.
- `all_statuses() -> dict[int, str]`, `status_name(code) -> str` (`"UNKNOWN"` for
  an unregistered value), `render_status(code) -> str` (`"INVALID (3)"`).
- `clear_extra_statuses()` — forget every registered kind; for tests of the
  framework itself.
- `normalise_result(returned, code) -> TestResult` — the boundary the engine puts
  every return value through: a `TestResult` passes straight back, a bool or a
  status value is converted, anything else raises naming the test. Exported so a
  wrapper around tests can accept the same shapes.

### `TestResult`

What a test returns. Frozen dataclass: `code: int = Status.PASS`,
`comments: Mapping[str, Any] = {}`.

- `bool(result)` is **True when the test passed**; `.passed` and `.failed` say it
  explicitly. The raw `code` is not a truthiness source — 0 is a pass but falsy.
- `.status` is the status name.
- Comments are copied and frozen at construction, so a shared result cannot be
  mutated through the dict a caller passed in.
- Construction validates: an unregistered status, `Status.ERROR` (the engine's, not
  a test's), a bool as the code, a non-mapping `comments`, or a non-string comment
  key all raise.
- `PASS` is the shared, immutable passing result.

### `TestOutcome`

What the engine recorded for one test on one row: `code` (the test code),
`outcome` (`passed`, `failed`, `disabled`, `skipped`, `errored`), `status` (a
`Status` value), `layer`, `suite`, `message`, `detail`, `comments`.

`.failed` is True for `failed` and `errored`; `.status_label` renders as
`INVALID (3)`. `detail` explains the three non-evaluating outcomes: which rule
disabled it, which prerequisites blocked it, or what it raised.

The outcome strings are also exported as `PASSED`, `FAILED`, `DISABLED`,
`SKIPPED`, `ERRORED`.

### `Test`

One registered test: `code`, `message`, `fn`, `suite`, `source_file`,
`default_enabled`, `description`, `depends_on`, `layer`. Created by the
decorators, never by hand. `layer` is computed by `validate_registry`.

`TESTS` is the live registry list, in registration order. Read it freely; mutate
it only through the decorators and `clear_registry`.

### `RowContext`

Per-row metadata kept out of the DataFrame: `flags`, `paths`, `state`, `extra`,
each a dict. `build_context(row) -> RowContext` is the adopter's hook and ships
as a stub.

### `MatchCriterion`, `OverrideRule`

A rule's `{column, pattern}` filter, and the rule itself: `name`, `action`,
`codes`, `criteria`, `match_all`, `description`, `source_file`.

## Registering tests

### `register_test(code, message, default_enabled=True, description="", depends_on=None, suite=None)`

Decorator. The function takes `(row)` or `(row, ctx)` and returns `PASS`, a
`TestResult`, a bool, or a `Status` value.

Raises at import for a duplicate code, an empty code or message, a non-list
`depends_on` (a bare string would otherwise register one prerequisite per
character), a non-string `suite` or `description`, a non-bool `default_enabled`,
or a signature the engine cannot call -- including a required keyword-only
argument. The `depends_on` *codes* are checked later by `validate_registry`,
since a prerequisite may live in a module not yet imported.

### `test_group(depends_on=None, suite=None, default_enabled=True) -> TestGroup`

Shared defaults for a file. The returned group is called like the decorator:
`group(code, message, default_enabled=None, description="", depends_on=None, suite=None)`.

The group's prerequisites are unconditional — a test's own are added to them,
never substituted. `suite` and `default_enabled` on a test override the group's.

### `load_suites(suites: list[str], package: str) -> None`

Imports every `test_*.py` module in each named subpackage, plus the base suite
(files directly in *package*) on every call. *package* is required and is **your**
package: this one ships no tests, so a default would name the wrong tree and the
error for a missing suite would point at it. Each suite imports once, so repeat
calls are no-ops. Calls `validate_registry` before returning. Raises `ValueError`
naming the expected subpackage for an unknown suite.

### `load_test_files(paths: str | list[str]) -> None`

Imports the named `.py` files by path so their tests register themselves — the
counterpart to `load_suites` for a caller whose test files are not an importable
package, such as a pipeline that writes them into a run directory. One path or
several; nothing is discovered. A file already loaded, or listed twice, is
skipped. `validate_registry` runs once the whole call has been imported, so a
prerequisite may live in any of the files. Raises `ValueError` for a path that is
not a file, and propagates whatever a file raises while importing.

Each file is given a unique module name, so two directories that each hold a
`checks.py` both load. That name is flat, so the tests land in the base suite.
No `__pycache__` is written beside the file.

### `loaded_files() -> list[str]`

The resolved paths loaded that way, in load order. A copy.

### `BASE_SUITE`

The suite name (`"base"`) given to tests that sit directly in *package* rather
than in a suite subpackage, and to any file loaded by path. It is loaded by every
`load_suites` call and cannot be switched off.

### `loaded_suites() -> set[str]`, `validate_registry() -> None`, `clear_registry() -> None`

`validate_registry` checks every `depends_on` edge, detects cycles, computes
layers, and caches the evaluation order. An unregistered prerequisite raises —
including one whose suite was not loaded, deliberately as loud as a typo.

`clear_registry` empties the registry and evicts the modules that registered
tests from `sys.modules`, so a later `load_suites` re-registers rather than
silently doing nothing.

## Loading override rules

`load_overrides(path)`, `load_overrides_from_dir(directory, pattern="*.yaml")`
(alphabetical), `load_overrides_from_files(paths)` (the order given) all return
`list[OverrideRule]` in load order, share one parser, and raise `ValueError` at
load time for every malformed rule. They are thin wrappers over
`pandas_row_validation.rules`, which holds the format and its parser and is handed the codes
that exist rather than reaching into the registry. Load suites first: a rule naming an
unregistered code is an error. See [configuration.md](configuration.md).

`list_rule_codes(rule_name, overrides) -> list[str]` prints and returns the codes
one named rule touches.

## Running tests

### `explain_row(row, ctx=None, overrides=None, on_error="record") -> list[TestOutcome]`

What every test did on one row, in evaluation order. The single implementation of
the per-row algorithm.

`on_error="record"` turns an exception inside a test into a `Status.ERROR`
outcome and continues; `"raise"` propagates it. A test returning something that is
not a result always raises — that is an authoring bug, not a data problem.

Raises `ValueError` when the row has duplicate column labels, before running
anything.

### `validate_row(row, ctx=None, overrides=None, on_error="record") -> list[TestOutcome]`

The failing outcomes from `explain_row`, in evaluation order. Does not mutate `row`
or `ctx`. For the one to read first, ask `root_cause`.

### `root_cause(outcomes) -> str | None`

The first failing code, or `None` for a row that passed. Accepts either
function's output.

### `resolve_enabled_state(row, overrides) -> dict[str, bool]`

The effective on/off state of every registered code for one row: each test's
`default_enabled`, then every matching rule in order, last match winning.

### `check_rule_columns(df, overrides) -> list[str]`

One line per rule criterion naming a column the frame lacks — a rule that can
never fire. Tests are not checked: they read the row themselves, so a missing
field raises and is recorded as an `ERROR` outcome naming the column.

### `validate(df, overrides=None, context_builder=build_context, on_error="record", progress=None, progress_every=1000) -> ValidationRun`

Every test against every row, returned as one object rather than a list of lists
and the frame beside it. `progress`, when given, is called as
`progress(done, total)` every `progress_every` rows and once at the end;
`progress_every` below 1 raises `ValueError`.

`ValidationRun` holds `df`, `traces`, `overrides` and `stats`. It supports
`len()` and iteration over its traces, and offers `records`, `errors`,
`failed_rows`, `root_causes`, `report(key_column, data_columns, include_skipped,
include_passed)`, `summary()` and `explain(position)` — which raises `IndexError`
naming the frame's size rather than letting a negative position wrap round.
`ValidationRun.from_records(df, records, overrides=None, stats=None)` builds one
from outcomes collected elsewhere, and raises `ValueError` unless there is
exactly one list per row.

`RowTrace` is one row: `position` (the position in the frame, not the index
label), `records`, and the derived `failures`, `root_cause` and `passed`.
`RunStats` is `rows`, `failures`, `errors`, `seconds` and `rows_per_second`,
which is infinity for a run too fast to time.

### `iter_traces(df, ...) -> Iterator[RowTrace]`

The streaming half of `validate`, taking the same arguments and holding one
trace at a time. For a frame where one outcome per test per row will not fit in
memory.

## Reporting

`build_report(outcomes_per_row, df=None, key_column=None, data_columns=None,
include_skipped=False, include_passed=False)` — `data_columns` copies frame
columns into the report just after `row`; see
[reporting.md](reporting.md#showing-data-alongside-the-failures).

`collect_outcomes`, `build_report`, `render_report`, `render_comments`,
`escape_for_spreadsheet`, `write_report`,
`print_report`, `row_explanation`, `print_row_explanation`, `summarise_outcomes`,
`root_cause_counts`, `print_summary` — all exported from `validation` and
documented in [reporting.md](reporting.md).

Registry tables:

- `get_registry_table(debug=0)` — one row per test, sorted suite, then layer,
  then code. Columns `code`, `layer`, `suite`, `default_state`, `description`,
  `depends_on`; plus `source_file` at `debug >= 2`.
- `print_registry(overrides=None, debug=0)` — prints it. At `debug >= 1` adds
  `could_be_overridden_by`: rules that *reference* each code. Not "was overridden
  by" — whether a rule fires is a per-row question this table cannot answer.
- `print_registry_with_overrides(overrides, debug=0)` — adds `override_rules` and
  `effective_state`, which says `DEFAULT (ON)` when no rule references the code
  and "depends on row" when one does.
- `print_override_rules(overrides, debug=0)` — one row per rule: `name`,
  `action`, `codes_hit_count`, `match`; plus `source_file` at `debug >= 2`.

`format_table(df, wrap_columns=None)` renders any frame as bordered text;
`is_null(value)` is the null test both the engine and the renderer use — reach for
it in your own tests too, since `NaN` is truthy and `pd.isna` returns an array for
list-like values.

## Stability

Pre-1.0 and unversioned. The parts most likely to stay fixed are test codes,
status values, the `(row, ctx)` signature, and the override YAML schema, since
data written against them outlives the code.
