# Architecture

Back to the [README](../README.md).

## Shape

One process-global list of checks, `registry._CHECKS`, is the center. It is internal: a
caller reads the registry through `registry_table`, because nothing that mutates the
list directly drops the cached evaluation order the row loop walks. Checks are ordinary functions
that register themselves into it when their module is imported; which modules get
imported is the loading mechanism. Everything else reads that list: rule files are
validated against it, the tables list it, and `validate` walks it once per row in a
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
  +-- validate(df)          -> _explain per row, every outcome kept
  |       resolve state (defaults, then matching rules, last wins)
  |       walk the cached topological order
  |       disabled / blocked  -> CheckOutcome, fn never called
  |       fn(row, context)    -> Verdict -> CheckOutcome(passed|failed)
  |       fn raises           -> CheckOutcome(errored, Status.ERROR)
  |
  +-- build_report(...) -> long-format frame, titled -> pandas to_string / to_csv
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
pyproject.toml               packaging, plus pytest, coverage, ruff and mypy config
.build/                      every generated artifact, all gitignored
.agent/, .claude/            the handoff record, saved reviews, agent guidance
```

Nothing generated is written to the project root. `.build/` holds the coverage
data, the pytest, ruff and mypy caches, the hypothesis database, the example profile
and the machine's performance baseline, and `tests/run-tests.sh` runs from the
root whichever directory it is invoked from. The one exception is `mutants/`,
which `mutmut` writes beside the project because it hardcodes the path; delete
it when a mutation run is finished.

A src layout, so an installed copy and a clone behave the same: nothing imports
the package by accident from the working directory. The demos and the scripts add
`src/` to `sys.path` themselves, and the suite gets it from `pythonpath` in
`pyproject.toml`, so the repository runs without being installed.

## Modules

What each module holds. For the public functions themselves -- arguments, defaults,
return values and what each does, one line apiece -- see
[interfaces.md: At a glance](interfaces.md#at-a-glance).

| File | Responsibility |
|---|---|
| `src/jobcheck/registry.py` | The registry: registration, file import, dependency validation, ordering and layers. What checks *exist*. `load_setup` lives here too, being the one place that composes both loaders. |
| `src/jobcheck/engine.py` | What happens to one row: per-row on/off state from the rules, evaluation in dependency order, every outcome kept. |
| `src/jobcheck/views.py` | Every view, each a titled DataFrame built from data already collected: the long-format report and its root causes, one row's explanation, the per-check summary, and the registry and rules tables. |
| `src/jobcheck/results.py` | What a check returns and what the engine records: statuses, `Verdict`, `CheckOutcome`. |
| `src/jobcheck/rules.py` | The rule file format and its parser. Knows nothing about the registry. |
| `src/jobcheck/tables.py` | How a cell reads as text, null handling, and the `add_columns` refusal, shared by every view. |
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
| `scripts/regen_docs.py` | Rewrites the output shown after each Python block in `docs/` and the README with what the block prints. |
| `scripts/mutation_score.py` | Scores the results a mutmut run left against a floor: the mutation gate. |
| `scripts/profile_examples.py` | Profiles the catalog's runs in this process: the `profile` mode. |

## Dependency direction

Imports point one way, and a module never imports one listed after it:

```
context, results, tables, paths    import nothing from the package
rules                              <- paths, tables
registry                           <- context, paths, rules
engine                             <- context, registry, results, rules, tables
views                              <- registry, results, rules, tables
__init__                           <- all of the above, to re-export them
```

The library parses no arguments, prints nothing and sets no exit code: it returns
DataFrames, and every refusal is an exception. Argument parsing, stdout and stderr,
and exit codes belong to the entry points in `examples/`, which depend on the package
and never the other way.

## Decisions

**Simple, and loud with an explanation, over handling every case.** The package supports
what its documents specify, and nothing more. When a caller or a file does something it
does not explicitly support, the library raises where it can tell, and the message says
what was wrong, where, and with what value. It does not guess what was meant, reinterpret
the input or add code for each corner case. The one obligation is that the failure is
informative. Cost: some mistakes, such as YAML reading an unquoted `off` as a boolean,
are refused rather than accepted. Rejected: catching and repairing each such case, which
grows the code for inputs the documents never promised to accept (F.49 in
[future-work.md](future-work.md)).

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

**One row checked as many copies: the caller explodes, the check says what repeats.**
A row that stands for several things, counted only at run time, is exploded by the
caller into copies, and `validate(repeat_key=...)` names the column that marks them. A
check marked `repeat=True`, and everything that depends on it, runs on every copy; every
other check runs on the first copy whose rules enable it and is recorded `shared` on the
copies after it, or `disabled` where a rule switches it off. Every copy
keeps one outcome per check, so each outcome list still describes one visible row, and
the summary counts calls. The flag is on the check because it is a fact about the check;
the key is on the call because which rows are copies is a fact about the frame, and it
is never guessed from a repeated index. Cost: a sixth outcome, a summary column and a
registry column. Rejected (2026-09-30): the engine looping over a list held in the
context (`for_each="dirs"`), which tied a check to a context attribute by name and hid
each copy's identity from the report and the rules; a per-group outcome list, which
breaks the one list per row that `build_report` pairs with the frame; and repeating
every check on every copy with rules to suppress the extras, which disabled the
prerequisites of the checks that did repeat.

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

**Every view is a titled DataFrame, and pandas writes it.** A function that builds a
table returns it with its title in `attrs["title"]`, and the caller turns it into text
with pandas: `to_string()` for a terminal, `to_csv()` for a file.
So there is no print, render or write variant per table, and a table is data a caller
can filter before it is text. Cost: pandas neither wraps long text nor escapes a cell,
so a wide report runs past the terminal and a formula-like value reaches a CSV as it
is. Rejected (F.68, 2026-09-28): the package's own `render`, a bordered, wrapping,
escaping writer of about 64 lines that duplicated pandas and `csvlook` for the one
view it improved.<sup>[9](reporting.md#every-table-names-itself)</sup>

**Tables state what they cannot know.** `could_be_overridden_by` is named for *reference*,
not effect: only `validate` against a real row can decide.<sup>[10](interfaces.md#registry_tablerulesnone---dataframe)</sup>

**`clear_registry` is a flat reset.** It empties the check list, the loaded-file list
and the ordering cache, and drops the modules `load_checks` made for check files (named
`jobcheck_check_file_*`) from `sys.modules`. It touches no other module.
`load_checks` runs each file again under a new module name, so a reload registers
afresh. A module a check file merely imports is Python's to cache: it registers its
checks once per process, and after a clear it registers nothing. So checks register
only in the files `load_checks` is given, and a module a check file imports holds
helpers. This replaced a record, kept at registration, of which module to evict. That
record guessed the module from the registered object, which for a callable object or an
imported function named a module that registered nothing, and evicting it left earlier
importers holding a second copy (F.53, 2026-09-29).

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

**`validate` keeps everything; the views filter.** Root-cause reporting needs to know
why a check did *not* run, which means recording disabled, skipped and errored
outcomes. One algorithm runs once per row and keeps every outcome, and every view
-- the report at each `include` level, a row's explanation, the summary -- picks
what to show from that one result, so no two of them can disagree about a row, and
explaining a row never runs its checks a second time. Rejected (F.73, 2026-10-01):
`validate_row`, a per-row call keeping only the failures, and a public
`root_causes`; the first was a second entry point to the same algorithm whose lists
the summary could not count, the second is now `include="root_causes"`. The cost is
an object per check per row; a frame too large for that is validated in chunks.

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
`views.py` how to show it, `results.py` and `tables.py` the
values and the rendering they share. Each imports only what sits below it, and the
import graph is one-directional, so the rule format can be read and changed without
touching the engine. `context.py` is separate because it is the adopter's hook, and the
`check_*.py` files are outside the package because the entry point names which of them
to load.

## Extension points

- **A check**: a function in a `.py` file the entry point loads. Nothing else.
- **Per-row metadata**: subclass `RowContext` and add the fields your checks read, then
  hand `validate` something that builds it.
- **An entry point**: a script calling `load_checks` with its own list of files. See
  `examples/main.py`.
- **A new report**: build a DataFrame and set `attrs["title"]`; pandas writes it.

## Dependencies

`pandas` for the row and table types; `PyYAML` for rule and setup files, read with a
`SafeLoader` subclass that also refuses a key given twice. Nothing
else at runtime — file loading uses `importlib`,
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
- `validate` keeps an object per check per row, so it costs memory proportional to
  checks x rows; a larger frame is validated in chunks, one report appended per chunk.<sup>[14](reporting.md#cost)</sup>

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
| 10 | [interfaces.md: registry_table](interfaces.md#registry_tablerulesnone---dataframe) | the column in full |
| 11 | [writing-checks.md: What to return](writing-checks.md#what-to-return) | every form a check may return |
| 12 | [concepts.md: What a check says](concepts.md#what-a-check-says-and-what-the-engine-records) | status against outcome: why the kinds hold no "failed" |
| 13 | [writing-checks.md: When a check raises](writing-checks.md#when-a-check-raises) | what an errored check records |
| 14 | [reporting.md: Cost](reporting.md#cost) | validating a large frame in chunks |
