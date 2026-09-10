# Handoff

Written 2026-09-10. Branch `claude`, commit `e4da2cf`, 17 commits ahead of `main`, tree
clean apart from this file and one line in `pyproject.toml` (both committed with it).
Start at `README.md` and the documents its index links; `CLAUDE.md` holds the project's
own history, which is stranger than most.

## State

Measured at `e4da2cf` on 2026-09-10 with the conda `pytesting` environment
(`~/.conda/envs/pytesting/bin/python`, Python 3.12.14, pandas 3.0.5, PyYAML 6.0.3,
pytest 9.1.1, coverage 7.16.0, mypy 2.3.1, hypothesis 6.167.1, mutmut 3.5.0).

| Gate | Result |
|---|---|
| `./run-tests.sh` (fast, the commit gate) | 717 passed, 28s, then mypy |
| `./run-tests.sh long` | 251 passed |
| `./run-tests.sh all` | 968 passed, 286s |
| `./run-tests.sh cov` | 100% of statements **and** branches (1,176 statements, 388 branches), floor 95 |
| `./run-tests.sh memory` | 3 passed, 72s |
| `./run-tests.sh perf` | 6 timings against `.perf-baseline.json` |
| `mypy` | clean, 62 source files |
| Mutation | 1,622 mutants, **1,466 killed, 156 survived, 0 timeouts (90.4%)** |

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh all     # + long, then the profile
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh cov     # coverage against the floor
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh perf    # timing vs this machine
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh memory  # peak-memory ceilings
~/.conda/envs/pytesting/bin/python -c "import pandas, sys; sys.argv=['mutmut','run']; \
    from mutmut.__main__ import cli; cli()"                      # mutation, see the traps
```

The default `python3` here is anaconda 3.14.6 and has neither hypothesis nor mutmut, which
is why `PYTHON=` is in every line above. `./run-tests.sh long` refuses to run without
hypothesis rather than skipping the property tests quietly.

Catalog: 48 example cases (20 simple, 18 moderate, 10 complex) and 18 failure cases, all
driven through the real entry point in a subprocess.

## The last task, unfinished: a simplified jobcheck

**This is where the next session starts.** The owner asked for a simplified version that a
junior developer can read, and asked first for a line count. The count was produced and a
strip list proposed; **two questions were asked and not yet answered**, so nothing was
changed. Everything below is the analysis, so it does not have to be redone.

### Executable lines today, at `e4da2cf`

Counted with an AST pass that excludes blank lines, comments and docstrings
(`/tmp/.../count.py` is gone; the script is eight lines of `ast.walk` collecting
docstring line ranges, then counting what is left).

| Group | Executable | Physical |
|---|---|---|
| Package `src/jobcheck/` | **1,428** | 2,572 |
| Example entry points (`main.py` 146, `main_hard_only.py` 42) | 188 | 279 |
| Example check suites | 166 | 266 |
| Dev scripts (data, catalog, golden, profile, bytecode reader) | 342 | 526 |
| **Total, no tests and no docs** | **2,124** | 3,643 |

Package by module: `registry` 344, `report` 255, `run` 149, `rules` 146, `__init__` 140
(almost all of it the re-export list), `engine` 121, `results` 115, `registry_tables` 105,
`tables` 41, `context` 12.

### The strip list, with the measured cost of each

Every one of the ten stated goals stays met after all of these.

| Strip | Executable lines | Why it is not load-bearing |
|---|---|---|
| `run.py` entirely — `ValidationRun`, `RowTrace`, `RunStats`, `iter_traces`, `validate` | 149 | A convenience layer over `collect_outcomes`; goal 8 is met by `build_report`. **jobchain calls `validate()`** — see the open question. |
| `CheckGroup` + `check_group` | 52 | Shared defaults per file. `register_check(depends_on=[...])` says the same thing per check. **jobchain's check files use `check_group`.** |
| Suites — `load_suites`, `_import_test_modules`, `_infer_suite`, `loaded_suites`, `BASE_SUITE`, the `suite` column | ~55 | Two loading mechanisms is one too many to explain. `load_checks(paths)` is the one jobchain uses. |
| Extensible statuses — `register_status`, `all_statuses`, `clear_extra_statuses`, `status_name` | 41 | A fixed `Status` enum covers the goals; a plugin point with no caller. |
| Summary views — `summarise_outcomes`, `print_summary`, `root_cause_counts` | 54 | Aggregates, not in the goal list. |
| Extra registry tables — `print_registry_with_overrides`, `print_override_rules`, `list_rule_codes` | 59 | Goal 9 needs one debug table: `get_registry_table` + `print_registry` is 34 lines. |
| Loader trio to one — `load_overrides`, `_from_dir`, `_from_files`, `combine` | ~15 | One function taking a list of paths. |
| `_make_runner` and `_register` trimmed | ~45 | Both are mostly error-message text, not logic. |
| `_check_data_columns` trimmed (30 to ~10) | ~20 | Four separate refusals where two would do. |

**Estimate: the package lands at 660-700 executable lines, from 1,428** — roughly half —
and the demo entry point at ~50 from 146 by dropping most of its twelve flags.

Keep, because a goal needs it: the decorator, `Check`, `CHECKS`, the dependency graph and
layers, `explain_row` (68 lines, the whole engine), `RowContext`, `CheckResult` and
`CheckOutcome`, the rule parser and matcher, `build_report` with `data_columns` and
`is_root_cause`, `row_explanation`, the table and CSV renderers, and
`escape_for_spreadsheet` (12 lines, and dropping it reintroduces CSV injection).

### The two questions waiting for an answer

1. **Where does the simplified version live?** A separate `jobcheck-lite` project, so both
   survive and the full one keeps serving jobchain — or simplify `jobcheck` itself on a new
   branch, with jobchain following it.
2. **Must jobchain keep working?** It uses exactly seven names, listed in
   `jobchain/checks.py:_ENGINE_NAMES`: `RowContext`, `clear_registry`, `load_checks`,
   `load_overrides_from_files`, `validate`, `render_comments`, `ERRORED` — plus
   `check_group` and `CheckResult` inside its own check files and tests. Stripping `run.py`
   and `check_group` removes three of those. Either keep a minimal `validate()` (~40 lines
   rather than 149) and `check_group`, or port jobchain to `collect_outcomes` and
   `register_check`.

## What this session changed

Seventeen commits, oldest first.

- `6956bcc` — `recovery/bytecode/` tracks the pre-2026-09-09 bytecode, the only copy of
  four lost modules, plus `scripts/read_bytecode_api.py` to read interfaces out of it.
- `af1906b` — `load_checks(paths)` rebuilt: importing check files by path, which
  `load_suites` cannot express.
- `c2a3851` — `run.py` rebuilt from the bytecode: `validate`, `iter_traces`,
  `ValidationRun`, `RowTrace`, `RunStats`.
- `f311078` — `tests/test_differential_jobchain.py`: what jobchain's suite asserted of the
  pre-rename engine, restated here. All of it holds.
- `0f00222` — `recovery/README.md`: what was lost, and the decision on each module.
- `84e5d1d` — `CLAUDE.md` committed (it was untracked) and brought up to date.
- `45fce47`, `837ef23` — a coverage gap and the one catalog case that renders paths.
- `da032a3` — the first handoff this project ever had.
- `9ea3727` — the test suite rebuilt to the `ctesting` standard: concurrency, fault
  injection, scaling, performance against a recorded baseline, memory in its own run, the
  entry points in-process; the catalog from 16 cases to 48 at three levels with real data;
  `--data`, `--key-column` and `--no-registry` added to the demo so cases could use it.
- `4a9226f` — every library error message pinned word for word, which found a real defect:
  `register_check(depends_on="CODE")` turned a mistyped string into its characters before
  the guard could see it.
- `4c20de6` — the mutation survivors that were real, killed; the rest classified.
- `5485357` — catalog cases run through a fixed-length root, so they no longer depend on
  where the repository is cloned.
- `0f2aeec` — the documents made true again, plus `tests/test_docs_unit.py`, which binds
  every call shown in a document against the real signature; `contributing.md` and
  `future-work.md` added.
- `e675337`, `7166108` — suite sizes corrected in the docs.
- `e4da2cf` — **the big one**: renamed back to `jobcheck`, the vocabulary reverted to
  "check", `registry.py` split three ways, four behaviour changes. Details below.

In `~/work/ai/jobchain`, branch `claude-port` (commit `649434b`, clean): ported to this
engine and then back again with it. 744 unit tests pass with nothing skipped (it was 724
passing and 20 skipped), the 103-case example catalog passes, and its coverage gate went
from 85% failing an 89% floor to 89% passing it.

## Decisions worth knowing before changing things

**The project is `jobcheck` and the vocabulary is "check", deliberately.** It was renamed
to `pandas-row-validation` on 2026-09-09, package and words together, and renamed back on
2026-09-10 at the owner's instruction. The reason is concrete: a file named `test_*.py`
inside an adopter's package is collected by pytest, which imports it a second time under
its own rules and reports the registry's duplicate-code guard as a mysterious test failure.
So check files are `check_*.py` and the API is `check_group`, `CheckResult`,
`CheckOutcome`, `register_check`, `load_checks`, `CHECKS`. Do not "modernise" this.

**`RowContext` is empty by default.** `build_context` reads nothing out of the row. What
belongs in a context is the adopting pipeline's business, and the previous version invented
a `legacy` flag from `source_system` that most callers never asked for.

**Every failure at the shallowest layer is a root cause**, not just the first evaluated.
`root_causes()` returns them all, `root_cause()` returns one for a caller wanting a single
label, and `is_root_cause` flags all of them. Registration order used to decide what a
person read as the cause, which is the defect this closed.

**A multi-column key holding `|` raises.** `("a|b","c")` and `("a","b|c")` used to render
the same label, which is the one thing a key column exists to prevent.

**A check blocked only by disabled prerequisites says `prerequisite disabled:`.** "Did not
pass" reads as a failure, and a chain switched off at its root is not one.

**`registry.py` was split along a responsibility line, not by size**: `registry.py` (what
checks exist), `engine.py` (what happens to a row), `registry_tables.py` (how both are
displayed). `check_rule_columns` went to `rules.py`, because it judges a rule file against
a frame and touches no registry state.

**`git log` starts on 2026-09-09 and that is an accident, not the project's age.** The
`.git` directory was removed by mistake and the repository re-initialised. Do not date
anything from the log; `CLAUDE.md` has the forensics.

**Four modules exist only as bytecode.** `lint`, `parallel`, `params` and their tests live
in `recovery/bytecode/`, tracked against `.gitignore`'s own rules by a negation at the
bottom of that file. A tidy-up of `.gitignore` can silently untrack the only copy.

## Considered and deliberately not done

`docs/future-work.md` carries the full list with the evidence. The ones most likely to be
re-proposed:

- **Rebuilding `lint`, `parallel` or `params`** — nothing calls them; `recovery/README.md`
  records what each did and what would reopen it.
- **Chasing the last mutation survivors** — 21 are default-argument mutations mutmut's own
  trampoline cannot execute (verified by hand), several are equivalent on this platform
  (`utf-8` and `\n` are what Linux gives anyway), and the rest are print-function wording
  that the catalog and golden files pin byte for byte while mutmut cannot run either.
- **Inferring a report's format from the file extension** — one flag, one meaning.
- **Accepting the check-era rule format** (a top-level `column`/`pattern` glob) — the
  parser rejects those keys as typos, and ignoring them would disable nothing while the
  author believed a code was switched off.
- **A CI workflow** — settled: the pre-commit hook and the release gates are what run the
  suites, and an absent workflow is not outstanding work.
- **A changelog** — settled: `git log` is the record.
- **Lowering the coverage floor** — settled: the floor is 95 and the suite runs at 100.

Settled by standing preference, not open: the work stays on the `claude` branch and is not
merged; breaking the CLI or the Python API is acceptable and no compatibility shims are
wanted; the licence is the owner's to choose.

## Measurements, so they are not re-derived

- **Performance baseline**, 4,000-row frame, Python 3.12.14 on this machine, stored in the
  gitignored `.perf-baseline.json`: `collect_outcomes` 6.118s (spread 5%), `iter_traces`
  5.941s (2%), `build_report` 0.064s (77%), `render_report` 0.053s (4%),
  `summarise_outcomes` 0.021s (3%), `collect_outcomes` with 50 rules over 1,000 rows
  0.393s (27%). The gate is the machine's own measured spread doubled, floored at 35% and
  capped at 150%; verified by lowering a baseline and watching it report
  `6.15s against a limit of 2.06s`.
- **Where the time goes**: `explain_row` is about 85% of a validation run, and inside it
  the example suites' `dates_present` and `dates_in_order` are roughly 40% of the total,
  because both call `pandas.to_datetime` per row. That is example code, not library code.
- **Suite runtimes**: fast 28s, long ~265s, all 286s, cov 28s, memory 72s, perf ~85s,
  a full mutation run ~6 minutes at about 5 mutations/second.
- **Lost source sizes**, read from the `.pyc` headers: `run` 10,756 B, `lint` 14,326 B,
  `parallel` 15,072 B, `params` 7,173 B; the lost test modules total roughly 150 KB.

## Environment and housekeeping

- **Use `PYTHON=~/.conda/envs/pytesting/bin/python`** for anything but the fast suite. The
  default `python3` is anaconda 3.14.6 without hypothesis or mutmut.
- **Never install anything without asking.** Test tooling belongs in the `pytesting` env.
- Generated and gitignored: `mutants/` (19 MB after a run), `.build/` (the saved profile),
  `.mypy_cache/`, `.pytest_cache/`, `.perf-baseline.json` (962 bytes, machine-specific by
  design), `reviews/`.
- `reviews/` is empty: the review saved earlier today was worked through and cleared.
- `scripts/install-hooks.sh` installs the fast suite as `.git/hooks/pre-commit`.
- There is no `requirements.txt` any more. `pyproject.toml` is the one dependency list, and
  the test that used to read the file reads the metadata now — without `tomllib`, which
  arrived in 3.11 while the declared floor is 3.10.

## Things that will bite

**`mutmut` needs pandas imported before it starts.** Plain `mutmut run` dies in stats
collection with `RuntimeError: context has already been set` from `multiprocessing`. The
command in the State block above works.

**A stale `mutants/` tree lies about the score.** After the package rename, a run over the
existing tree reported 264 killed, 1,056 "no tests" and 302 survived — an impossible result
next to 100% branch coverage. `rm -rf mutants .mutmut-cache` and rerun gives the real
number (1,466 / 156). Delete the tree whenever the package layout changes.

**mutmut runs the *whole* selected suite once per mutant.** `pyproject.toml` excludes the
files that shell out (they never load the instrumentation), the two that read `docs/`, and
the slow suites; without those exclusions a run takes days rather than six minutes.

**Long commands get killed at the foreground timeout.** `all`, the catalog, a mutation run
and `regen_catalog.py` all exceed two minutes. Run them in the background, redirect to a
file and wait on the file.

**`./run-tests.sh long` refuses to run without hypothesis.** That is deliberate: a skipped
property suite reads as a pass.

**The catalog runs every case through a symlink** at `$TMPDIR/prv-catalog-root-<8-digit
uid>` so column widths do not depend on the clone's path length. A filesystem without
symlinks falls back to the real root, and one test skips.

**Regenerating is not the same as fixing.** `scripts/regen_catalog.py`,
`regen_golden.py` and `make_example_data.py` all rewrite files the suite compares byte for
byte. Read the diff, or a defect becomes a recorded expectation.
