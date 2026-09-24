# Architecture

Back to the [README](../README.md).

## Shape

One process-global list of checks, `CHECKS`, is the center. Checks are ordinary functions
that register themselves into it when their module is imported; which modules get
imported is the loading mechanism. Everything else reads that list: rule files are
validated against it, the tables render it, and `explain_row` walks it once per row in a
precomputed order.

```
entry point
  |
  +-- load_checks([...]) -> imports the named .py files by path
  |                             -> @register_check appends to CHECKS
  |                             -> validate_registry(): depends_on, cycles, layers, topo order
  |
  +-- load_rules(...)   -> parse YAML -> validate each rule against CHECKS -> [Rule]
  |
  +-- validate(df)          -> explain_row per row
  |       resolve state (defaults, then matching rules, last wins)
  |       walk the cached topological order
  |       disabled / blocked  -> CheckOutcome, fn never called
  |       fn(row, ctx)        -> Verdict -> CheckOutcome(passed|failed)
  |       fn raises           -> CheckOutcome(errored, Status.ERROR)
  |
  +-- build_report(...) -> long-format frame -> render_report / write_report
```

## Repository layout

```
src/jobcheck/   the package: the only thing that ships
examples/                    the demo entry point main.py, the rule files and
                             data it loads, and checks/ -- the checks it runs
docs/                        this and its siblings
tests/                       the suites, the golden files, the catalogs, and
                             run-tests.sh, the entry point for every gate
scripts/                     hook installer, the data, catalog and golden
                             regenerators, the profiler, the bytecode reader
pyproject.toml               packaging, plus pytest, coverage and mypy config
.build/                      every generated artifact, all gitignored
.agent/, .claude/            the handoff record, saved reviews, agent guidance
```

Nothing generated is written to the project root. `.build/` holds the coverage
data, the pytest and mypy caches, the hypothesis database, the example profile
and the machine's performance baseline, and `tests/run-tests.sh` runs from the
root whichever directory it is invoked from. The one exception is `mutants/`,
which `mutmut` writes beside the project because it hardcodes the path; delete
it when a mutation run is finished.

A src layout, so an installed copy and a clone behave the same: nothing imports
the package by accident from the working directory. The demos and the scripts add
`src/` to `sys.path` themselves, and the suite gets it from `pythonpath` in
`pyproject.toml`, so the repository runs without being installed.

## Modules

| File | Responsibility |
|---|---|
| `src/jobcheck/registry.py` | The registry: registration, file import, dependency validation, ordering and layers. What checks *exist*. `load_setup` lives here too, being the one place that composes both loaders. |
| `src/jobcheck/engine.py` | What happens to one row: per-row on/off state from the rules, evaluation in dependency order, the outcomes, and the root causes. |
| `src/jobcheck/registry_tables.py` | The registry and the rules as tables: what is registered, which rules could touch each code, what each rule covers. |
| `src/jobcheck/report.py` | Collecting outcomes for a frame, the long-format failure table, summaries, explanations, and rendering them as text or CSV. |
| `src/jobcheck/results.py` | What a check returns and what the engine records: statuses, `Verdict`, `CheckOutcome`. |
| `src/jobcheck/rules.py` | The rule file format and its parser. Knows nothing about the registry. |
| `src/jobcheck/tables.py` | Table rendering and null handling, shared by every view. |
| `src/jobcheck/paths.py` | The path a caller named, turned into a file on disk, and the error when it is not one. Used by both loaders. |
| `src/jobcheck/context.py` | The per-row metadata type — the one adopter-supplied hook. |
| `src/jobcheck/__init__.py` | Re-exports the public surface. Registers no checks, and ships none. |
| `examples/checks/` | The example checks. Outside the package on purpose: nothing of ours should register in an adopter's registry. |
| `examples/main.py` | Demo entry point and end-to-end driver: registry tables, the report, explanations, summaries. |
| `examples/bundle_main.py` | Second demo entry point: loads one bundle, prints what it loaded. `examples/checks/all_checks.py` is the bundle it loads by default. |
| `tests/` | pytest suites, split `fast`/`long` by marker, plus the example and failure catalogs and `run-tests.sh`, the entry point for every gate. |
| `scripts/` | The pre-commit hook installer, the catalog regenerator, the example profiler and the bytecode interface reader. |

## Decisions

**Codes are permanent identifiers, never renumbered.** Rule files written by
non-developers, saved reports, and downstream tooling all refer to codes. Reusing a
retired code would silently change the meaning of data already written. Cost: the code
space is untidy over time. Rejected: sequential numbering, which forces edits across every
consumer whenever a check is inserted.

**Decorator registration, no central list.** Adding a check must touch exactly one file,
because checks are added constantly. Rejected: an explicit registry list, which is a merge
conflict on every addition and drifts from the files it names.

**Loading is explicit per entry point, not an eager auto-import.** Importing `jobcheck`
registers nothing. Several entry points in one process space can each opt into a different
subset without interfering. Rejected: importing every `check_*.py` on package import, which
makes the set of active checks a property of the codebase rather than of the script.

**One loading mechanism, not two.** Checks are loaded from a list of file paths and
nothing else — no package convention, no directory scan, no suite names. Two mechanisms
that differed in what they discovered was one more thing to explain than the feature was
worth, and a path is what a pipeline writing check files into a run directory already has.

**Per-row metadata lives in `RowContext`, not in DataFrame columns.** Extra columns
holding dicts or paths cause dtype churn and leak into exports. `RowContext` is left
bare on purpose: it is the one type an adopter is expected to fill in.

**Dependency validation happens after loading, not at decoration.** A prerequisite may be
registered by a module not yet imported, so the check belongs at the end of
`load_checks`. An unloaded prerequisite raises rather than silently skipping its
dependent: otherwise which checks ran would change with an unrelated CLI flag, with no
diagnostic.

**A check file may call `load_checks` itself, and the outermost call owns the
validation.** That is a bundle: one path in the caller's list, the files it collects
behind it. Validating at the end of every call would refuse a bundle whose prerequisite
the caller names after it — a constraint on the order of a list, for no gain, since the
whole load is still one moment. The registry tracks which file is being imported, so
loading stays per file at every depth: a file that raises drops the checks *it*
registered and keeps whatever its completed members did, leaving the registry and
`loaded_check_files()` agreeing. A file already being imported further up the call is
skipped like one already loaded, which is what makes a bundle that names itself, or two
that name each other, finish instead of exhausting the stack.

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

**`clear_registry` evicts the modules a load brought in.** Python caches a module
after its first import, so clearing the list alone would make the next `load_checks` a
silent no-op. Two routes record a module for eviction, and both are needed: registration,
so a module pulled in by any route — a check file importing a shared one directly, for
instance — is tracked, and a completed `load_checks` import, so a file that registered
nothing of its own, such as a bundle, is tracked too. The price is that *whatever* module a check registers from is evicted, a test
module included, and `sys.modules[name]` is then `None`: a dataclass whose annotations
have to be resolved (`ClassVar`, `InitVar`, `get_type_hints`) raises `AttributeError:
'NoneType' object has no attribute '__dict__'` from `dataclasses` afterwards. Define such
a class at module level, or before the clear. Dropping the registration-time record would
remove that, and reintroduce the silent empty registry for a shared module two check files
import.

**Checks read the row; there is no declared column.** These rules are row-scoped
and many weigh several fields together, so a single "the" column was a fiction.
The cost is that a misspelled field is no longer detectable before the run: it
raises `KeyError` from the check and lands as an `ERROR` outcome naming the
column. `warn_missing_rule_columns` still covers the rule side, where nothing else
would catch it.

**A check returns a status and comments, not a bool.** "Age is out of range" is
not actionable without the value and the limit, and threading that into the
report through anything but the return value meant per-row state. A bare bool
return is refused at the boundary rather than converted: `True == 1 ==
Status.MISSING`, so a guess would invert the meaning. `Verdict(condition)` is
the one-liner form.

**Failure kinds are one small fixed vocabulary.** Five statuses, `OK` and four
failure kinds, and a `Verdict` carrying anything else is refused at
construction. A fixed set can be grouped and counted across every check in a
summary, which per-check enums could not; what varies between projects is the
codes, not the kinds.

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



**The rule format is its own module, and knows nothing about the registry.** A
rule file changes for reasons the engine does not share -- a new key, a new
matcher -- and the only thing the parser needs from the registry is the set of
codes that exist, which the registry's `load_rules` wrapper hands it. That keeps
the import one-directional and lets the format be read, tested and changed on its
own.

**The library ships no checks of its own.** The example checks live under
`examples/`, not in the package, because importing a package should register nothing:
anything shipped inside would register in every adopter's registry and fail on
their rows. It also makes the path list on `load_checks` required rather than
defaulted, which is the honest signature -- the checks being loaded are always
someone else's.

**One module per question, and the questions are few.** `registry.py` answers what
checks exist, `engine.py` what happened to a row, `rules.py` what a rule file means,
`report.py` and `registry_tables.py` how to show it, `results.py` and `tables.py` the
values and the rendering they share. Each imports only what sits below it, and the
import graph is one-directional, so the rule format can be read and changed without
touching the engine. `context.py` is separate because it is the adopter's hook, and the
`check_*.py` files are outside the package because the entry point names which of them
to load.

## Extension points

- **A check**: a function in a `check_*.py` file the entry point loads. Nothing else.
- **Per-row metadata**: subclass `RowContext` and add the fields your checks read, then
  hand `validate` something that builds it.
- **An entry point**: a script calling `load_checks` with its own list of files. See
  `examples/main.py`.
- **A new report**: build a DataFrame and hand it to `format_table`.

## Dependencies

`pandas` for the row and table types; `PyYAML` (`yaml.safe_load`) for rule files. Nothing
else at runtime — table rendering uses `textwrap`, file loading uses `importlib`,
`source_file` and signature adaptation use `inspect`. `mypy` and `types-PyYAML` are
development-only.

## Limitations

- The registry is process-global. Two sets of check files cannot be active in one process at once;
  entry points are separate processes.
- `validate` iterates the frame row by row in Python (`iterrows`), not vectorized. Large
  frames are slow by construction; the design buys per-row rule resolution and dependency
  logic with that.
- Rules can only enable and disable existing codes. They cannot define checks, change
  messages, or parameterize thresholds.
- Regex matching stringifies values, so numeric or datetime criteria match the text of the
  value.
- A check reading a column the frame lacks raises `KeyError`, which lands as an `ERROR`
  outcome per row rather than being caught once before the run; nothing declares which
  columns a check reads, so nothing can check them up front.
- Collecting outcomes keeps an object per check per row, so the report path costs memory
  proportional to checks x rows; `validate_row` retains only one row's failures at a time.
