# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## What this is

`pandas-row-validation`: validating rows of a pandas DataFrame with many small,
independently named tests that depend on each other, so a blank field produces one error
rather than one from every test that reads it. The README is the reference manual and
`docs/` holds the rest; read `docs/interfaces.md` before changing a public name.

The directory is still called `~/work/ai/jobcheck`, and the remote — if one is ever added —
will not be. The project was named **jobcheck** until 2026-09-09 and renamed in one pass
that evening. Everything below exists because that rename is not visible in `git log`.

## The git history starts on 2026-09-09, and that is an accident

The `.git` directory was removed by mistake and the repository re-initialised, so
`git log` shows three commits (`f930e09` "Initial commit", `1058b3e` "init",
`34bac65` "removed .github") and nothing before them. **The history of the project as
jobcheck is gone.** Treat `git log` as the record from 2026-09-09 onward only; for
anything older the evidence is the working tree and the notes here.

Two consequences worth remembering:

- Do not reason about "when was this introduced" from the log. The answer for anything
  older than 2026-09-09 is: unknowable from this repository.
- The re-initialised repository never tracked a `jobcheck` package at any commit
  (`git ls-files` confirms this for all three), which will mislead anyone who assumes the
  log is complete. It is not evidence that the package never existed.

## What the bytecode says was here, and what is not here now

The first pass over this question concluded "nothing was lost". That was too strong, and
the fuller evidence is below. Read it before deciding anything about recovery.

`src/jobcheck/` still exists on disk holding **only** `__pycache__`, and that bytecode is
the whole of the record from before the rename. It is unusually informative, because a
`.pyc` header stores the mtime **and the byte size of the source that produced it**, and
there are two generations of it — `cpython-312` compiled between 09-03 and 09-07, and
`cpython-314` compiled at 09-09 23:47.

Reading those headers gives the size of every source file at two points in time, which can
be compared with what is on disk now:

| Module | 09-03..09-07 | now (`pandas_row_validation`) |
|---|---|---|
| `context` | 1,382 | 1,837 |
| `registry` | 16,799 | 34,613 (absorbed `engine` and `registry_tables`) |
| `report` | 11,994 | 16,439 |
| `results` | 5,902 | 8,251 |
| `rules` | 6,473 | 9,222 |
| `tables` | 2,624 | 2,632 |
| `__init__` | 2,750 | 2,914 |
| `engine` | 12,198 | folded into `registry` |
| `registry_tables` | 7,163 | folded into `registry` |
| `run` | 10,756 | **absent** |
| `lint` | 14,326 | **absent** |
| `parallel` | 15,072 | **absent** |
| `params` | 7,173 | **absent** |

The test suite tells a less tidy story than the package does. Comparing the same two
generations of `tests/__pycache__`, some modules grew, several shrank, and eleven are
absent entirely:

| Grew | Shrank | Absent now |
|---|---|---|
| `test_tables_unit` 2,379 → 11,114 | `test_overrides_unit` 26,982 → 15,375 | `test_lint_unit` 37,624 |
| `test_report_unit` 14,524 → 17,166 | `test_registry_unit` 16,313 → 12,047 | `test_parallel_unit` 32,611 |
| `test_results_unit` 5,172 → 6,848 | `test_validate_row_unit` 22,377 → 20,413 | `test_engine_unit` 12,818 |
| `conftest` 2,569 → 4,042 | `test_packaging` 12,015 → 10,432 | `test_run_unit` 15,482 |
| `test_integration` 9,019 → 9,201 | `test_pathological` 12,718 → 11,376 | `test_params_unit` 11,097 |
| | `test_readme` 11,168 → 10,417 | `test_error_messages` 10,991 |
| | `test_interface_cli` 8,932 → 8,386 | `test_rules_unit` 7,997 |
| | `test_context_unit` 2,119 → 1,404 | `test_parallel_integration` 6,673 |
| | `golden_fixture` 4,982 → 3,604 | `test_benchmarks` 6,356 |
| | `catalog` 3,047 → 2,229 | `test_perf` 5,655 |
| | | `test_examples` 3,175 |

That is roughly 150 KB of tests present in the older generation and not in this one.

**So the two trees are not one lineage with a rename applied.** Parts of what is here are
plainly later work (the `tables` and `report` tests, the extensible-status machinery in
`results`, `load_overrides_from_dir`/`from_files`, `MatchCriterion`), and parts of what is
gone was plainly real (a 37 KB test module for `lint` is not a sketch). The docstrings
match closely enough to be the same document lineage — `check_group`'s "Defaults for a
file of checks: prerequisites and default on/off state" is `test_group`'s "Defaults for a
file of tests: prerequisites, suite, and default state" — so this is one project, but the
tree here at 23:54 is not simply the tree at 23:27 with names changed.

## The timeline, as far as it can be established

- **09-03 to 09-07 18:42** — the last real edits to the `jobcheck` sources, in the
  **check** vocabulary: `check_group`, `CheckResult`, `load_checks(paths)`,
  `validate(df, ...)`. `lint`, `params`, `registry_tables` and `run` stop being imported
  on 09-05; `parallel` on 09-06.
- **09-09 23:27** — every one of the eight then-live modules gets that mtime while its
  size stays exactly what it was on 09-07. Sizes unchanged with mtimes reset is what a
  copy or a restore looks like, not an edit. This is the likely moment of the `.git`
  accident and whatever recovery followed it.
- **09-09 23:54** — `src/pandas_row_validation/*.py` and the current `tests/` appear,
  27 minutes later, in the **test/suite** vocabulary.

Chris's own recollection is of renaming **test → check**, which fits everything above if
that rename happened before 09-07 and the tree that landed at 23:54 came from before it —
in other words, the current source may be an *earlier* line of development that was
restored, with some later work on top, rather than the direct continuation of the 09-07
tree. The alternative reading — one continuous lineage that renamed check → test at 23:54
and dropped four modules in the same pass — is also consistent with the file sizes. The
evidence does not settle it, and this file deliberately does not pretend otherwise.

What is certain: **`lint`, `parallel`, `params`, `run` and their tests exist nowhere in
this repository**, in any form other than bytecode.

## Recovering the check-era tree

The bytecode is not a curiosity; it is the only copy. It contains every function and class,
their argument names, and their docstrings, for both generations. Two routes, in order of
fidelity:

1. **Decompile `src/jobcheck/__pycache__/*.cpython-312.pyc`.** The 3.12 generation is the
   check-era source (09-03..09-07) and is far likelier to be supported by a decompiler
   than the 3.14 one. Ask before installing anything: `pycdc` builds from source, and
   `decompyle3`/`uncompyle6` support up to 3.8 only, so 3.12 needs `pycdc`.
2. **Reconstruct from the bytecode's own metadata.** Without a decompiler, every public
   name, its parameters and its docstring can still be read straight out of the code
   objects with `marshal` — enough to rebuild an interface and its documentation, though
   not the bodies. The signatures below were produced that way.

Nothing here is urgent unless `lint`, `parallel` or `params` are wanted back. If they are
not, delete `src/jobcheck/` and this section becomes history; if they might be, **do not
delete it**, because it is the only copy.

## The check-era API, as jobchain records it

`~/work/ai/jobchain` was written against the 09-07 tree and still calls it, which makes
`jobchain/checks.py` a second, independent record of that API — one written in ordinary
Python rather than bytecode, with the semantics spelled out in comments. If the check-era
tree is ever rebuilt, this is the contract it has to satisfy; if instead jobchain is ported
forward, this is the list of what has to find a new spelling.

Module surface jobchain calls, with the argument names taken from the bytecode:

```
clear_registry()
load_checks(paths)                       # list of .py paths; raises ValueError/OSError
load_overrides(*rule_files)              # -> overrides, passed straight back to validate
validate(df, overrides, context_builder) # -> ValidationRun
render_comments(comments)                # -> str, for a failure's detail line
ERRORED                                  # the outcome value meaning "the check raised"
RowContext                               # subclassed by the caller; see below
```

`ValidationRun` as jobchain uses it: `run.errors` is a count of checks that raised, and
iterating the run yields one trace per row, each with `.position` (index into the frame),
`.root_cause` (the code of the shallowest failure) and `.failures`. A failure carries
`.code`, `.message`, `.comments` and `.outcome`.

`RowContext` is a dataclass the caller subclasses to carry whatever a cross-row check
needs; `context_builder` is `callable(row) -> ctx`, and jobchain hands every row the same
instance, built once, holding the whole file and a per-column value-count map.

The check-file vocabulary, which is what any user's check files import:

```python
from jobcheck import PASS, CheckResult, Status, check_group

g = check_group()                         # optionally depends_on=[...], default_enabled=

@g("CODE", "message", depends_on=["OTHER_CODE"])
def rule(row):                            # or (row, ctx) for a cross-row check
    return PASS if ok else CheckResult(Status.INVALID, {"value": row["x"]})
```

`Status` members jobchain's own tests and documentation use: `INVALID`, `MALFORMED`,
`MISSING`.

Other names present in the check-era bytecode and worth knowing about when rebuilding:
`registry.register_check`, `registry.evaluation_order`, `registry.loaded_files`,
`registry.registry_table`, `results.CheckRecord`, `rules.load_rules(paths, known_codes)`,
`engine.iter_traces`, `engine.RowTrace`, `run.RunStats`,
`parallel.validate_parallel(df, package, suites, overrides, on_error, workers)`,
`parallel.split_frame`, `parallel.worker_count`, `parallel.registry_is_reconstructible`,
`lint.lint_rules(overrides, defaults, df, today, declared)`, `lint.findings_table`,
`lint.worst_severity`, `params.register_params(defaults)`, `params.declared_params`.

Note that `parallel` already spoke of `package` and `suites` on 09-06, the vocabulary this
tree uses now — one more reason the two lines cannot be ordered with confidence.

## What the rename changed, name by name

Kept, unchanged: `RowContext`, `build_context`, `clear_registry`, `load_overrides`,
`render_comments`, `ERRORED`, `Status`, `normalise_result`, `render_status`,
`format_table`, `is_null`, `build_report`, `print_report`, `print_summary`,
`root_cause_counts`, `row_explanation`.

Renamed:

| Was | Is |
|---|---|
| `jobcheck` (package) | `pandas_row_validation`, distribution `pandas-row-validation` |
| `check_group` | `test_group` |
| `Check`, `CheckGroup` | `Test`, `TestGroup` |
| `CheckResult` | `TestResult` |
| `CheckRecord` | `TestOutcome` |
| `load_checks(files)` | `load_suites(suites, package)` — imports suite subpackages of *your* package, rather than taking file paths |

Gone with no successor: `validate(df, overrides, context_builder)`, the whole-frame entry
point. Only per-row `validate_row(row, ctx=None, overrides=None, on_error="record")` and
`explain_row` remain, so a caller that had a DataFrame now drives the rows itself.

The vocabulary moved from "check" to "test" throughout. A name still spelled `check` in
this repository (`check_rule_columns`) is deliberate and unrelated.

## Commands

```sh
./run-tests.sh          # fast: unit, smoke, interface, regression, cheap pathological, plus mypy
./run-tests.sh long     # integration, load, end-to-end catalogs
./run-tests.sh all      # both, plus mypy
./run-tests.sh cov      # the fast suite with coverage, gated at 95%
./run-tests.sh types    # mypy alone
scripts/install-hooks.sh
scripts/regen_catalog.py, scripts/regen_golden.py   # regenerate committed fixtures
```

Python 3.10+ (`X | None` syntax throughout), pandas 2.1+ and PyYAML at runtime;
`pip install -e .[dev]` for the suite, which needs pytest, coverage, mypy, hypothesis and
mutmut. Tests are split by pytest markers (`fast`, `long`), not by directory.

## jobchain depends on this project, and is currently broken against it

`~/work/ai/jobchain` runs a run's check files through this library. It was written against
the 09-07 tree and still calls it, so every `checks:` run fails, twenty of its tests skip,
and its documented quick start does not execute.

Every name it needs has a counterpart here **except one**, and the exception is what a
port has to solve. Checked against the current source on 2026-09-10:

| jobchain calls | here now | note |
|---|---|---|
| `clear_registry()` | `clear_registry()` | unchanged |
| `load_checks(paths)` | **nothing** | the gap; see below |
| `load_overrides(*files)` | `load_overrides_from_files(paths)` | or `load_overrides(path)` for one, `load_overrides_from_dir` for a directory |
| `validate(df, overrides, context_builder)` | `collect_outcomes(df, overrides, context_builder, on_error)` | same three arguments; returns `list[list[TestOutcome]]` rather than a `ValidationRun` |
| `run.errors` | `sum(o.outcome == ERRORED for row in outcomes for o in row)` | derive |
| `trace.position` | the index in the returned list | derive |
| `trace.root_cause` | `root_cause(outcomes)` | returns the code, or `None` |
| `trace.failures` | `[o for o in outcomes if o.failed]` | `failed` is a property of `TestOutcome` |
| `failure.code/.message/.comments/.outcome` | same four names on `TestOutcome` | unchanged |
| `render_comments(comments)` | `render_comments(comments)` | unchanged |
| `ERRORED` | `ERRORED` (`"errored"`) | unchanged |
| `RowContext`, subclassed | `RowContext`, subclassed | unchanged; fields are `flags`, `paths`, `state`, `extra` |
| `check_group(...)` | `test_group(depends_on, suite, default_enabled)` | rename, plus the new `suite` argument |
| `CheckResult(Status.X, {...})` | `TestResult(code, comments)` | rename; same positional shape |
| `PASS`, `Status.MISSING/MALFORMED/INVALID` | identical | `Status.ERROR` is reserved for the engine |

**The one gap: loading a check file by path.** `load_checks` took explicit `.py` paths and
imported each with `spec_from_file_location` / `module_from_spec` / `exec_module`, then
called `validate_registry()`. `load_suites(suites, package)` cannot do that: it takes an
importable package and imports subpackages of it. jobchain names arbitrary files — after a
run is prepared, files in that run's own `inputs/` directory — so a package is the wrong
shape for it.

Nothing here needs to change for that. Registration happens at import, through the
decorator, so the caller can do the import itself and then call the public
`validate_registry()` to get the dependency check and the cached evaluation order that
`load_checks` used to run at the end. A file imported by path gets a flat module name, and
`_suite_of` maps anything with fewer than three dotted parts to `BASE_SUITE`, which is
always loaded — so a path-imported check file lands in the base suite and runs.

If a path-based loader is wanted here instead, it belongs in `registry.py` beside
`load_suites`, and the check-era implementation can be read out of
`src/jobcheck/__pycache__/registry.cpython-312.pyc`.

### To do: compare jobchain's record of jobcheck against this tree

Not done yet, and worth doing before any decision about recovery or a port. jobchain is
the only surviving *written* description of the check-era library — bytecode aside — and it
is a fuller one than the signatures above suggest: fifteen separate `from jobcheck import`
sites across its tests, docs, README and example catalogue, each exercising or documenting
behaviour rather than just naming it.

What is there to compare against:

| In jobchain | What it records |
|---|---|
| `jobchain/checks.py` | The engine call sequence, the caching around it, and what each error path was expected to raise (`ValueError`/`OSError` from `load_checks`, an arbitrary exception from a check file's own import) |
| `tests/test_checks_unit.py` | Fifteen uses of `check_group`/`CheckResult`/`Status`, including `depends_on` layering, the crash path, cross-row `ctx.count`, `among=` populations, and a rule file switching one check off for chosen rows — each with the behaviour it asserted |
| `tests/examples/test_complex.py` | Another fifteen, in end-to-end runs |
| `docs/configuration.md` F.2, `docs/guide.md` G.3, `README.md` | The check-file contract as documented for users: what a check receives, what it may return, how `depends_on` reports one failure rather than three, what a cross-row `ctx` is for |

Three questions that comparison would answer, none of which the bytecode alone can:

1. **Does anything here behave differently from what jobchain asserts?** Its tests are
   executable expectations of the old engine. Porting them to run against this package —
   renaming `check_group` to `test_group` and so on — turns them into a differential test
   between the two lineages. Any that fail for a reason other than a rename is a real
   behavioural difference, and worth understanding before assuming this tree is the later
   one.
2. **Is any documented behaviour missing here?** jobchain's prose describes `depends_on`
   root-cause reporting, the crash-into-`ERRORED` path and cross-row counting as
   guarantees. Check each against this source rather than against memory.
3. **Which lineage is later?** The timeline section above could not settle it. A
   feature-by-feature comparison against an independent record might: a behaviour jobchain
   documents that this tree cannot do is evidence the 09-07 line was ahead, and the
   reverse is evidence for this one.

Read it as evidence, not as a specification: jobchain describes what it needed, which is a
subset, and its wording is its own.

Nothing in this repository imports jobchain, and nothing should: the dependency runs one
way. `jobchain/checks.py:_ENGINE_NAMES` is the list of everything jobchain depends on,
written down in one place so a rename here can be checked against it.
