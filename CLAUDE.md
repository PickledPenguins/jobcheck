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
the whole of the record from before the rename. It is now copied into `recovery/bytecode/`
and tracked (`.gitignore` has an exception for it), because the `*.pyc` rules meant one
`git clean` would have destroyed the only copy. `recovery/README.md` is the entry point;
`scripts/read_bytecode_api.py` regenerates `recovery/recovered-api.md`.

The bytecode is unusually informative, because a
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

1. **Decompile `recovery/bytecode/jobcheck/*.cpython-312.pyc`.** The 3.12 generation is the
   check-era source (09-03..09-07) and is far likelier to be supported by a decompiler
   than the 3.14 one. Ask before installing anything: `pycdc` builds from source, and
   `decompyle3`/`uncompyle6` support up to 3.8 only, so 3.12 needs `pycdc`.
2. **Reconstruct from the bytecode's own metadata.** Without a decompiler, every public
   name, its parameters and its docstring can still be read straight out of the code
   objects with `marshal` — enough to rebuild an interface and its documentation, though
   not the bodies. The signatures below were produced that way.

`run` and `load_checks` have since been rebuilt this way (see below). `lint`, `parallel`
and `params` have not, deliberately -- `recovery/README.md` records the decision and the
reason to revisit each. **Do not delete `recovery/bytecode/`** while any of the three might
be wanted; deleting it is the decision that they never come back.

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
| `load_checks(files)` | `load_test_files(paths)`, rebuilt 2026-09-10. `load_suites(suites, package)` is the other loader: suite subpackages of *your* package, rather than file paths |

Gone at the rename and rebuilt on 2026-09-10: `validate(df, overrides, context_builder)`,
the whole-frame entry point, now in `run.py` alongside `iter_traces` and the
`ValidationRun` type. The per-row `validate_row(row, ctx=None, overrides=None,
on_error="record")` and `explain_row` are unchanged, and `collect_outcomes` is the
lower-level call that returns bare lists.

The vocabulary moved from "check" to "test" throughout. A name still spelled `check` in
this repository (`check_rule_columns`) is deliberate and unrelated.

## Commands

```sh
./run-tests.sh          # fast: unit, smoke, interface, regression, cheap pathological, plus mypy
./run-tests.sh long     # integration, load, concurrency, faults, scaling, catalogs, then the profile
./run-tests.sh all      # both, plus mypy and the profile
./run-tests.sh cov      # the fast suite with coverage, gated at 95%
./run-tests.sh perf     # timing against this machine's baseline (its own gate)
./run-tests.sh memory   # peak-memory ceilings (its own gate)
./run-tests.sh profile  # where the example runs spend their time
./run-tests.sh types    # mypy alone
scripts/install-hooks.sh
scripts/regen_catalog.py, scripts/regen_golden.py   # regenerate committed fixtures
scripts/make_example_data.py                        # regenerate examples/data/*.csv
scripts/profile_examples.py                         # the profile, alone
scripts/read_bytecode_api.py <dir>                  # read the lost interface out of recovery/bytecode/
```

The long suite needs `hypothesis` and refuses to run without it rather than skipping the
property tests quietly; `PYTHON=/path/to/python` picks the interpreter, and the conda
`pytesting` environment is the one here that has `hypothesis` and `mutmut`.

Python 3.10+ (`X | None` syntax throughout), pandas 2.1+ and PyYAML at runtime;
`pip install -e .[dev]` for the suite, which needs pytest, coverage, mypy, hypothesis and
mutmut. Tests are split by pytest markers (`fast`, `long`), not by directory.

## jobchain depends on this project, and the port is a rename plus rule files

`~/work/ai/jobchain` runs a run's check files through this library. It was written against
the 09-07 tree and still calls it, so until it is ported every `checks:` run fails, twenty
of its tests skip, and its documented quick start does not execute.

Two of the gaps were closed here on 2026-09-10 rather than in jobchain, because both were
capabilities this tree had lost rather than names it had changed:

- `load_test_files(paths)` imports `.py` files by path, the way `load_checks` did.
  `load_suites(suites, package)` cannot: jobchain names arbitrary files in a prepared run's
  `inputs/` directory, and a package is the wrong shape for that.
- `validate(df, overrides, context_builder)` is back in `run.py`, returning a
  `ValidationRun` with the `.errors`, `.position`, `.root_cause` and `.failures` jobchain
  reads. `collect_outcomes` remains the lower-level call.

What jobchain still has to change, name by name:

| jobchain calls | here now | note |
|---|---|---|
| `clear_registry()` | `clear_registry()` | unchanged |
| `load_checks(paths)` | `load_test_files(paths)` | rename; same semantics, and no `.pyc` left beside the file |
| `load_overrides(*files)` | `load_overrides_from_files(paths)` | one list rather than varargs; `load_overrides(path)` for one file |
| `validate(df, overrides, context_builder)` | `validate(df, overrides, context_builder, on_error)` | unchanged, plus `on_error` |
| `run.errors`, `trace.position`, `trace.root_cause`, `trace.failures` | same four | unchanged |
| `failure.code/.message/.comments/.outcome` | same four names on `TestOutcome` | unchanged |
| `render_comments(comments)` | `render_comments(comments)` | unchanged |
| `ERRORED` | `ERRORED` (`"errored"`) | unchanged |
| `RowContext`, subclassed | `RowContext`, subclassed | unchanged; fields are `flags`, `paths`, `state`, `extra` |
| `check_group(...)` | `test_group(depends_on, suite, default_enabled)` | rename, plus the new `suite` argument |
| `CheckResult(Status.X, {...})` | `TestResult(code, comments)` | rename; same positional shape |
| `PASS`, `Status.MISSING/MALFORMED/INVALID` | identical | `Status.ERROR` is reserved for the engine |
| `jobcheck` | `pandas_row_validation` | the import, and `_ENGINE_NAMES` with it |

**The remaining incompatibility is the rule file format, and it is data, not code.** The
check era took one top-level `column`/`pattern` pair per rule, matched with
`fnmatchcase`; this tree takes a `match:` list of `{column, pattern}` criteria matched as
regular expressions, and rejects the old keys as typos rather than ignoring them.
Rejecting is right — ignoring would disable nothing while the caller believed a code was
switched off — so every rule file jobchain ships or documents has to be rewritten. Glob
`x` becomes regex `^x$`, not `x`, which matches anywhere.

### The comparison against jobchain's record is done

`tests/test_differential_jobchain.py` restates what jobchain's suite asserted of the
check-era engine — layered dependencies reporting one failure rather than three, the
shallowest failure as root cause, a cross-row test counting over the whole file, a
population that is not the frame being validated, a raising test recorded as `ERRORED`
with the exception in its detail, a rule file switching one code off for chosen rows — and
runs it against this tree. All of it holds. The only differences found are the two above.

Nothing in this repository imports jobchain, and nothing should: the dependency runs one
way. `jobchain/checks.py:_ENGINE_NAMES` is the list of everything jobchain depends on,
written down in one place so a rename here can be checked against it.
