# Architecture

Back to the [README](../README.md).

## Shape

One process-global list of checks, `registry._CHECKS`, is the center. It is internal: a
caller reads the registry through `registry_table`, because nothing that mutates the
list directly drops the cached evaluation order the row loop walks. Checks are ordinary functions
that register themselves into it when their module is imported; which modules get
imported is the loading mechanism. Everything else reads that list: rule files are
validated against it, the tables render it, and `explain_row` walks it once per row in a
precomputed order.

```
entry point
  |
  +-- load_checks([...]) -> imports the named .py files by path
  |                             -> @register_check appends to _CHECKS
  |                             -> _validate_registry(): depends_on, cycles, layers, topo order
  |
  +-- load_rules(...)   -> parse YAML -> validate each rule against _CHECKS -> [Rule]
  |
  +-- validate(df)          -> explain_row per row
  |       resolve state (defaults, then matching rules, last wins)
  |       walk the cached topological order
  |       disabled / blocked  -> CheckOutcome, fn never called
  |       fn(row, context)    -> Verdict -> CheckOutcome(passed|failed)
  |       fn raises           -> CheckOutcome(errored, Status.ERROR)
  |
  +-- build_report(...) -> long-format frame, titled -> render(frame, fmt)
```

## Repository layout

```
src/jobcheck/                the package: the only thing that ships
examples/                    the three demo entry points, checks/ -- the checks
                             they run -- and the rule files, data, run file and
                             setup file they load
docs/                        this and its siblings
tests/                       the suites, the golden files, the catalogs, and
                             run-tests.sh, the entry point for every gate
scripts/                     the hook installer, and tools that regenerate
                             committed fixtures or measure: one row each below
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
| `src/jobcheck/report.py` | The views of outcomes: the long-format failure report, one row's explanation, and the per-check summary, each a titled DataFrame. |
| `src/jobcheck/results.py` | What a check returns and what the engine records: statuses, `Verdict`, `CheckOutcome`. |
| `src/jobcheck/rules.py` | The rule file format and its parser. Knows nothing about the registry. |
| `src/jobcheck/tables.py` | What every table shows by default (`_DEFAULT_COLUMNS`), `render` -- bordered text or formula-escaped CSV -- and null handling, shared by every view. |
| `src/jobcheck/paths.py` | The path a caller named, turned into a file on disk, and the error when it is not one. Used by both loaders. |
| `src/jobcheck/context.py` | The per-row metadata type — the one adopter-supplied hook. |
| `src/jobcheck/__init__.py` | Re-exports the public surface. Registers no checks, and ships none. |
| `examples/checks/` | The example checks. Outside the package on purpose: nothing of ours should register in an adopter's registry. |
| `examples/main.py` | Demo entry point and end-to-end driver: registry tables, the report, explanations, summaries. |
| `examples/bundle_main.py` | Second demo entry point: loads one bundle and prints the registry with each check's source file. `examples/checks/all_checks.py` is the bundle it loads by default. |
| `examples/run_from_config.py` | Third demo entry point: one run file names the setup, the data and the tables to print; `examples/run.yaml` is the shipped one. The run-file format is this script's, not the library's. |
| `tests/` | pytest suites, split `fast`/`long` by marker, plus the example and failure catalogs and `run-tests.sh`, the entry point for every gate. |
| `scripts/install-hooks.sh` | Installs the pre-commit hook that runs the fast suite. |
| `scripts/make_example_data.py` | Writes `examples/data/*.csv`, the same bytes every run. |
| `scripts/new_catalog_case.py` | Adds one catalog case: directory, command, README and recorded output. |
| `scripts/regen_catalog.py` | Re-records the catalogs' expected output after an intended change. |
| `scripts/regen_golden.py` | Re-records `tests/golden/` after an intended change to the report. |
| `scripts/regen_docs.py` | Rewrites the output shown after each Python block in `docs/` with what the block prints. |
| `scripts/mutation_score.py` | Scores the results a mutmut run left against a floor: the mutation gate. |
| `scripts/profile_examples.py` | Profiles the catalog's runs in this process: the `profile` mode. |
| `scripts/read_bytecode_api.py` | Reads the pre-rename interface out of the bytecode kept in git history. |

## Dependency direction

Imports point one way, and a module never imports one listed after it:

```
context, results, tables, paths    import nothing from the package
rules                              <- paths, tables
registry                           <- context, paths, rules
engine                             <- context, registry, results, rules
report                             <- engine, results, tables
registry_tables                    <- registry, rules, tables
__init__                           <- all of the above, to re-export them
```

The library parses no arguments, prints nothing and sets no exit code: `render`
returns text, and every refusal is an exception. Argument parsing, stdout and stderr,
and exit codes belong to the entry points in `examples/`, which depend on the package
and never the other way.

## Decisions

**Codes are permanent identifiers, never renumbered.** Rule files written by
non-developers, saved reports, and downstream tooling all refer to codes. Reusing a
retired code would silently change the meaning of data already written. Cost: the code
space is untidy over time. Rejected: sequential numbering, which forces edits across every
consumer whenever a check is inserted.<sup>[1](writing-checks.md#codes-are-permanent)</sup>

**Decorator registration, no central list.** Adding a check must touch exactly one file,
because checks are added constantly. Rejected: an explicit registry list, which is a merge
conflict on every addition and drifts from the files it names.

**Loading is explicit per entry point, not an eager auto-import.** Importing `jobcheck`
registers nothing. Several entry points in one process space can each opt into a different
subset without interfering. Rejected: importing every `check_*.py` on package import, which
makes the set of active checks a property of the codebase rather than of the script.<sup>[2](writing-checks.md#which-checks-an-entry-point-loads)</sup>

**One loading mechanism, not two.** Checks are loaded from a list of file paths and
nothing else — no package convention, no directory scan, no suite names. Two mechanisms
that differed in what they discovered was one more thing to explain than the feature was
worth, and a path is what a pipeline writing check files into a run directory already has.

**Per-row metadata lives in `RowContext`, not in DataFrame columns.** Extra columns
holding dicts or paths cause dtype churn and leak into exports. `RowContext` is left
bare on purpose: it is the one type an adopter is expected to fill in.<sup>[3](writing-checks.md#per-row-context)</sup>

**Dependency validation happens after loading, not at decoration.** A prerequisite may be
registered by a module not yet imported, so the check belongs at the end of
`load_checks`. An unloaded prerequisite raises rather than silently skipping its
dependent: otherwise which checks ran would change with an unrelated CLI flag, with no
diagnostic.

**A check file may call `load_checks` itself, and the outermost call owns the
validation.** That is a bundle: one path in the caller's list, the files it collects
behind it. Validating at the end of every call would refuse a bundle whose prerequisite
the caller names after it — a constraint on the order of a list, for no gain, since the
whole load is still one moment. A file that raises is not rolled back: the error ends
the run, and a process that loads again calls `clear_registry()` first, as jobchain
does before every load. A file already being imported further up the call is
skipped like one already loaded, which is what makes a bundle that names itself, or two
that name each other, finish instead of exhausting the stack.<sup>[4](writing-checks.md#bundles-one-file-that-loads-the-rest)</sup>

**A disabled prerequisite counts as "did not pass", not as vacuously satisfied.** A check
that did not run confirmed nothing about the row. The alternative would let a rule
disabling one code quietly enable errors from another.<sup>[5](configuration.md#disabling-a-check-disables-what-depends-on-it)</sup>

**Topological order is computed per registry state, not per row.** The graph changes only
when the registry does. Registration and `clear_registry` invalidate the cache; the row
loop never sorts.

**Matching is regex only, and `match: all` is the sole wildcard.** One mechanism is easier
for non-developers than two. `match: []` and a missing `match` are rejected because an
empty list is far more likely an accident than a deliberate global rule, and the failure
mode — disabling checks across a whole dataset — is silent.<sup>[6](configuration.md#matching)</sup>

**Precedence is positional, last rule wins.** A priority field invites two rules with the
same priority and no defined outcome. The cost is that load order is part of the
configuration, which is why each loader documents its ordering.<sup>[7](configuration.md#precedence-last-rule-wins)</sup>

**All rule validation is at load time.** A malformed file stops the run before any data is
processed, rather than throwing part-way through a long pipeline.<sup>[8](configuration.md#errors)</sup>

**Every view is a titled DataFrame, and one `render` draws any of them.** A function
that builds a table returns it with its title in `attrs["title"]`; `render` turns it
into bordered text under a `== Title ==` bar, or into formula-escaped CSV. So there is
one output function rather than a print, render and write variant per table, and a
table is data a caller can filter before it is text. The renderer is local because
`DataFrame.to_string()` is cramped and unbordered for auditing, and a table library
would be a runtime dependency for formatting alone. Wrapping never breaks inside a
word, so identifiers stay greppable.<sup>[9](reporting.md#every-table-names-itself)</sup>

**Tables state what they cannot know.** `could_be_overridden_by` is named for *reference*,
not effect, and `effective_state` says "depends on row" instead of picking an answer. Only
`explain_row` against a real row can decide.<sup>[10](interfaces.md#registry_tablerulesnone-add_columnsnone---dataframe)</sup>

**`clear_registry` evicts the modules a load brought in.** Python caches a module
after its first import, so clearing the list alone would make the next `load_checks` a
silent no-op. Two routes record a module for eviction, and both are needed: registration,
so a module pulled in by any route — a check file importing a shared one directly, for
instance — is tracked, and a completed `load_checks` import, so a file that registered
nothing of its own, such as a bundle, is tracked too. Two exceptions. `__main__`: a
check defined in the running script is not evicted, since that would break pickling,
spawned workers and `import __main__` for the rest of the process. And the standard
library: a `functools.partial` or an `operator.methodcaller` reports `functools` or
`operator` as its module, and evicting one would leave every earlier importer holding a
copy that differs from the next one imported; for a partial, the wrapped function's own
module is the one recorded. The price is that
*whatever* other module a check registers from is evicted, a test
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
the one-liner form.<sup>[11](writing-checks.md#what-to-return)</sup>

**Failure kinds are one small fixed vocabulary.** Five statuses, `PASS` and four
failure kinds, and a `Verdict` carrying anything else is refused at
construction. A fixed set can be grouped and counted across every check in a
summary, which per-check enums could not; what varies between projects is the
codes, not the kinds.<sup>[12](concepts.md#what-a-check-says-and-what-the-engine-records)</sup>

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
authoring bug, and recording it would hide it.<sup>[13](writing-checks.md#when-a-check-raises)</sup>

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
- **A new report**: build a DataFrame, set `attrs["title"]`, and hand it to `render`.

## Dependencies

`pandas` for the row and table types; `PyYAML` for rule and setup files, read with a
`SafeLoader` subclass that also refuses a key given twice. Nothing
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
  proportional to checks x rows; `validate_row` retains only one row's failures at a time.<sup>[14](reporting.md#cost)</sup>

## References

| # | Section | What it covers |
|---|---|---|
| 1 | [writing-checks.md: Codes are permanent](writing-checks.md#codes-are-permanent) | the rule as an author meets it |
| 2 | [writing-checks.md: Which checks an entry point loads](writing-checks.md#which-checks-an-entry-point-loads) | naming check files from an entry point |
| 3 | [writing-checks.md: Per-row context](writing-checks.md#per-row-context) | writing a context and its builder |
| 4 | [writing-checks.md: Bundles](writing-checks.md#bundles-one-file-that-loads-the-rest) | writing one |
| 5 | [configuration.md: Disabling a check](configuration.md#disabling-a-check-disables-what-depends-on-it) | what a rule author sees, and the warning |
| 6 | [configuration.md: Matching](configuration.md#matching) | the matching rules in full |
| 7 | [configuration.md: Precedence](configuration.md#precedence-last-rule-wins) | the ordering each loader uses |
| 8 | [configuration.md: Errors](configuration.md#errors) | every load-time message, quoted |
| 9 | [reporting.md: Every table names itself](reporting.md#every-table-names-itself) | titles as a caller uses them |
| 10 | [interfaces.md: registry_table](interfaces.md#registry_tablerulesnone-add_columnsnone---dataframe) | the two columns in full |
| 11 | [writing-checks.md: What to return](writing-checks.md#what-to-return) | every form a check may return |
| 12 | [concepts.md: What a check says](concepts.md#what-a-check-says-and-what-the-engine-records) | status against outcome: why the kinds hold no "failed" |
| 13 | [writing-checks.md: When a check raises](writing-checks.md#when-a-check-raises) | what an errored check records |
| 14 | [reporting.md: Cost](reporting.md#cost) | choosing between the report path and `validate_row` |
