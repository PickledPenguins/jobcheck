# Architecture

Back to the [README](../README.md).

## Shape

One module holds the engine. Checks are ordinary functions that register themselves into a
process-global list when their module is imported; which modules get imported is the
suite mechanism. Everything else reads that list: rule files are validated against it,
the tables render it, and `validate_row` walks it once per row in a precomputed order.

```
entry point
  |
  +-- load_suites([...], package="your_package")
  |                          -> imports your_package/check_*.py and your_package/<suite>/check_*.py
  +-- load_checks([...]) -> imports named .py files by path, into the base suite
  |                             -> @register_check / a group appends to TESTS
  |                             -> validate_registry(): depends_on, cycles, layers, topo order
  |
  +-- load_overrides*(...)  -> parse YAML -> validate each rule against TESTS -> [OverrideRule]
  |
  +-- collect_outcomes(df)  -> explain_row per row
  |       resolve state (defaults, then matching rules, last wins)
  |       walk the cached topological order
  |       disabled / blocked  -> CheckOutcome, fn never called
  |       fn(row, ctx)        -> CheckResult -> CheckOutcome(passed|failed)
  |       fn raises           -> CheckOutcome(errored, Status.ERROR)
  |
  +-- build_report(...) -> long-format frame -> render_report / write_report
```

## Repository layout

```
src/jobcheck/   the package: the only thing that ships
examples/                    two demo entry points, the rule files they load,
                             and example_suites/ -- the checks they run
docs/                        this and its siblings
tests/                       the suites, the golden files, the catalogs
scripts/                     hook installer and the two regenerators
pyproject.toml               packaging, plus pytest, coverage and mypy config
run-tests.sh                 fast | long | all | cov
```

A src layout, so an installed copy and a clone behave the same: nothing imports
the package by accident from the working directory. The demos add `src/` to
`sys.path` themselves, so the repository runs without being installed.

## Modules

| File | Responsibility |
|---|---|
| `src/jobcheck/registry.py` | The registry: registration, suite and file import, dependency validation, ordering and layers. What checks *exist*. |
| `src/jobcheck/engine.py` | What happens to one row: per-row on/off state from the rules, evaluation in dependency order, the outcomes, and the root causes. |
| `src/jobcheck/registry_tables.py` | The registry and the rules as tables: what is registered, which rules could touch each code, what each rule covers. |
| `src/jobcheck/run.py` | The whole-frame entry point: `validate`, the streaming `iter_traces`, and the `ValidationRun`/`RowTrace`/`RunStats` types it returns. |
| `src/jobcheck/report.py` | Collecting outcomes for a frame, the long-format failure table, summaries, explanations, and rendering them as text or CSV. |
| `src/jobcheck/results.py` | What a check returns and what the engine records: statuses, `CheckResult`, `CheckOutcome`. |
| `src/jobcheck/rules.py` | The override rule file format and its parser. Knows nothing about the registry. |
| `src/jobcheck/tables.py` | Table rendering and null handling, shared by every view. |
| `src/jobcheck/context.py` | The per-row metadata type and its builder — the one adopter-supplied hook. |
| `src/jobcheck/__init__.py` | Re-exports the public surface. Registers no checks, and ships none. |
| `examples/example_suites/` | The example checks. Outside the package on purpose: nothing of ours should register in an adopter's registry. |
| `examples/main.py` | Demo entry point and end-to-end driver: registry tables, the report, explanations, summaries. |
| `examples/main_hard_only.py` | Second entry point proving suite selection is per-entry-point. |
| `tests/` | pytest suites, split `fast`/`long` by marker, plus the example and failure catalogs. |
| `run-tests.sh`, `scripts/` | Suite entry points, the pre-commit hook installer, the catalog regenerator, and the bytecode interface reader. |
| `recovery/` | The pre-2026-09-09 bytecode, tracked deliberately, and the interface read out of it. See `recovery/README.md`. |

## Decisions

**Codes are permanent identifiers, never renumbered.** Rule files written by
non-developers, saved reports, and downstream tooling all refer to codes. Reusing a
retired code would silently change the meaning of data already written. Cost: the code
space is untidy over time. Rejected: sequential numbering, which forces edits across every
consumer whenever a check is inserted.

**Decorator registration, no central list.** Adding a check must touch exactly one file,
because checks are added constantly. Rejected: an explicit registry list, which is a merge
conflict on every addition and drifts from the files it names.

**Suite is inferred from the module path, never passed.** A check file cannot then
disagree with where it lives. `jobcheck.hard_checks.check_age` gives `hard_checks`; a
module directly in the package gives `base`.

**Loading is explicit per entry point, not an eager auto-import.** Importing `validation`
registers nothing. Several entry points in one process space can each opt into a different
subset without interfering. Rejected: importing every `check_*.py` on package import, which
makes the set of active checks a property of the codebase rather than of the script.

**A base suite that always loads.** Some checks must run regardless of which optional
sets an entry point picked. It is a real named suite (`BASE_FLAVOR = "base"`) rather than
a special case, so it appears correctly in registry tables.

**Per-row metadata lives in `RowContext`, not in DataFrame columns.** Extra columns
holding dicts or paths cause dtype churn and leak into exports. `build_context` is left a
stub on purpose: it is the one place an adopter is expected to fill in.

**Dependency validation happens after loading, not at decoration.** A prerequisite may be
registered by a module not yet imported, so the check belongs at the end of
`load_suites`. An unloaded prerequisite raises rather than silently skipping its
dependent: otherwise which checks ran would change with an unrelated CLI flag, with no
diagnostic.

**A disabled prerequisite counts as "did not pass", not as vacuously satisfied.** A check
that did not run confirmed nothing about the row. The alternative would let a rule
disabling one code quietly enable errors from another.

**Topological order is computed per registry state, not per row.** The graph changes only
when the registry does. Registration and `clear_registry` invalidate the cache; the row
loop never sorts.

**Matching is regex only, and `match: all` is the sole wildcard.** One mechanism is easier
for non-developers than two. `match: []` and a missing `match` are rejected because an
empty list is far more likely an accident than a deliberate global rule, and the failure
mode — disabling checks across a whole dataset — is silent.

**Precedence is positional, last rule wins.** A priority field invites two rules with the
same priority and no defined outcome. The cost is that load order is part of the
configuration, which is why each loader documents its ordering.

**All rule validation is at load time.** A malformed file stops the run before any data is
processed, rather than throwing part-way through a long pipeline.

**Tables are rendered by a local `format_table`.** `DataFrame.to_string()` is cramped and
unbordered for auditing, and a table library would be a runtime dependency for output
formatting alone. Wrapping never breaks inside a word, so identifiers stay greppable.

**Tables state what they cannot know.** `could_be_overridden_by` is named for *reference*,
not effect, and `effective_state` says "depends on row" instead of picking an answer. Only
`resolve_enabled_state` against a real row can decide.

**`clear_registry` evicts the modules that registered checks.** Python caches a module
after its first import, so clearing the list alone would make the next `load_suites` a
silent no-op. Eviction is recorded at registration rather than at import, so a module
pulled in by any route — a check file importing it directly, for instance — is still
tracked.

**Checks read the row; there is no declared column.** These rules are row-scoped
and many weigh several fields together, so a single "the" column was a fiction.
The cost is that a misspelled field is no longer detectable before the run: it
raises `KeyError` from the check and lands as an `ERROR` outcome naming the
column. `check_rule_columns` still covers the rule side, where nothing else
would catch it.

**A check returns a status and comments, not a bool.** "Age is out of range" is
not actionable without the value and the limit, and threading that into the
report through anything but the return value meant per-row state. Bare bools
still work for one-liners, normalised at the boundary.

**Failure kinds are one small shared vocabulary, extensible from 10.** A fixed
set can be grouped and counted across every check in a summary, which per-check
enums could not. Reserving 0-9 leaves the built-ins room to grow without
colliding with a project's own codes.

**`explain_row` is the algorithm; `validate_row` filters it.** Root-cause
reporting needs to know why a check did *not* run, which means recording disabled,
skipped and errored outcomes. Two implementations -- a fast one that drops that
and a slow one that keeps it -- would eventually disagree about exactly the case
someone is trying to understand. The cost is an object per check per row, which is
why the report path is documented as the expensive one.

**A raising check is recorded, not fatal.** One broken check should not kill a long
batch, and an `errored` outcome is counted separately from `failed` so it cannot
be read as bad data. `on_error="raise"` restores fail-fast for a run that wants
it. A check returning a nonsense value still raises unconditionally: that is an
authoring bug, and recording it would hide it.

**Layer is computed, not declared.** An author states what a check depends on,
which they know; how deep that makes it is arithmetic, and a declared depth would
go stale the moment a prerequisite moved.

**A group's prerequisites are unconditional.** "Everything in this file waits for
X" would be worthless if any check could quietly opt out; a check that must run
regardless belongs outside the group. The cost is that a presence check cannot sit
in the group that waits on it -- that is a cycle, and it fails at load.

**The rule format is its own module, and knows nothing about the registry.** A
rule file changes for reasons the engine does not share -- a new key, a new
matcher -- and the only thing the parser needs from the registry is the set of
codes that exist, which the registry's three loader wrappers hand it. That keeps
the import one-directional and lets the format be read, tested and changed on its
own.

**The library ships no checks of its own.** The example suites live under
`examples/`, not in the package, because the base suite loads unconditionally:
anything shipped inside would register in every adopter's registry and fail on
their rows. It also makes `package=` on `load_suites` required rather than
defaulted, which is the honest signature -- the checks being loaded are always
someone else's.

**One module for the engine.** Registration, ordering, rules, and rendering all read the
same registry; splitting them into four files would spread one concept across four imports
without decoupling anything. `context.py` is separate because it is the adopter's hook,
and the `check_*.py` files are separate because their location is the suite mechanism.

## Extension points

- **A check**: a function in a `check_*.py` file under a suite subpackage. Nothing else.
- **A suite**: a subpackage with an `__init__.py`, then pass its name to `load_suites`.
- **Per-row metadata**: fill in `build_context`; add fields to `RowContext` if the four
  dicts do not fit.
- **An entry point**: a script calling `load_suites` with its own subset. See
  `examples/main_hard_only.py`.
- **A new report**: build a DataFrame and hand it to `format_table`.

## Dependencies

`pandas` for the row and table types; `PyYAML` (`yaml.safe_load`) for rule files. Nothing
else at runtime — table rendering uses `textwrap`, discovery uses `pkgutil` and
`importlib`, `source_file` uses `inspect`. `mypy` and `types-PyYAML` are development-only.

## Limitations

- The registry is process-global. Two suite sets cannot be active in one process at once;
  entry points are separate processes.
- `df.apply(..., axis=1)` is row-at-a-time Python, not vectorised. Large frames are slow by
  construction; the design buys per-row rule resolution and dependency logic with that.
- Rules can only enable and disable existing codes. They cannot define checks, change
  messages, or parameterise thresholds.
- Regex matching stringifies values, so numeric or datetime criteria match the text of the
  value.
- A check reading a column the frame lacks raises `KeyError`, which lands as an `ERROR`
  outcome per row rather than being caught once before the run; nothing declares which
  columns a check reads, so nothing can check them up front.
- Collecting outcomes keeps an object per check per row, so the report path costs memory
  proportional to checks x rows; `validate_row` alone does not.
