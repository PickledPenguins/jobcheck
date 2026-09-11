# Handoff

Written 2026-09-10. Branch `simplify`, commit `fab967a`, one commit ahead of `claude`
(which is 18 ahead of `main`), tree clean apart from this file. Start at `README.md` and
the documents its index links; `CLAUDE.md` holds the project's own history, which is
stranger than most, and its last section is what this branch changed.

## State

Measured at `fab967a` on 2026-09-10 with the conda `pytesting` environment
(`~/.conda/envs/pytesting/bin/python`, Python 3.12.14, pandas 3.0.5, PyYAML 6.0.3,
pytest 9.1.1, coverage 7.16.0, mypy 2.3.1, hypothesis 6.167.1, mutmut 3.5.0).

| Gate | Result |
|---|---|
| `./run-tests.sh` (fast, the commit gate) | 600 passed, 18s, then mypy |
| `./run-tests.sh long` | 228 passed, 330s |
| `./run-tests.sh cov` | 100% of statements **and** branches (895 statements, 314 branches), floor 95 |
| `./run-tests.sh memory` | 3 passed, 72s |
| `./run-tests.sh perf` | 6 timings against a re-recorded `.perf-baseline.json` |
| `mypy` | clean, 57 source files |
| Mutation | 1,300 mutants, **1,169 killed, 131 survived, 0 timeouts (89.9%)**, on a cleaned tree |

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

Catalog: 41 example cases (16 simple, 15 moderate, 10 complex) and 17 failure cases, all
driven through the real entry point in a subprocess.

## The simplification is done

**This is what the previous session left unfinished, and it is finished.** The two open
questions were answered: simplify `jobcheck` itself on a new branch (`simplify`), and port
jobchain to it (branch `simplify-port`, commit `4ded386`, 744 unit tests passing with
nothing skipped and its 103-case catalogue green).

### What the package measures now

Counted with the same AST pass as before — blank lines, comments and docstrings excluded.

| Group | Was | Now |
|---|---|---|
| Package `src/jobcheck/` | 1,428 | **1,052** |
| Demo entry points | 188 (two files) | 89 (one) |
| Example check files | 166 (a package of suites) | 163 (four flat files) |

By module: `report` 230, `registry` 195, `rules` 138, `engine` 131, `__init__` 112,
`registry_tables` 103, `results` 90, `tables` 41, `context` 12. `run.py` is gone.

The reduction is smaller than the 660-700 the earlier analysis projected because two of
the nine proposed strips were deliberately kept (the summary views, 54 lines, and the
extra registry tables, 59), and because `validate` survives at about 25 lines rather than
being deleted with the rest of `run.py`.

### What was dropped, and what replaced it

`CLAUDE.md` carries the table. In short: `run.py`, `check_group`, the suite mechanism and
the `suite` column, extensible statuses, two of the three override loaders, the second
demo entry point and eight of its twelve flags.

### Two behaviour changes, both intended

- A `skipped` outcome's detail now names only the prerequisite it directly waited for.
  `check_group`'s prerequisites were unconditional and added to every check in the file,
  so the old detail listed transitive ancestors too. Layers and skipping are unchanged.
- The registry table sorts by layer then code. There is no suite to sort by first.

Both are pinned by `tests/golden/`, regenerated and read as a diff.

### What is left on this branch

- **Mutation is re-run and classified** — see `docs/testing.md`. It found nine real gaps,
  all in code the simplification had just rewritten (five in `register_check`, four in
  `explain_row`'s errored outcome), now killed. The remaining 131 survivors are
  default-argument mutants mutmut cannot execute, unreachable branches, platform-equivalent
  mutants, and print wording the catalog pins where mutmut cannot run it.
- **`test_scaling.py::test_building_a_report_scales_with_the_failures_not_the_rows`
  is timing-flaky**: it asserts a clean 4,000-row frame builds a report faster than a
  messy one, and a cold first call has been seen to invert that (0.067s against 0.048s)
  in one isolated run, while passing in every full `long` run. Pre-existing, not caused
  by this branch; if it recurs, warm the call rather than loosening the assertion.
- **Neither branch is merged.** `jobcheck` is on `simplify`, jobchain on `simplify-port`,
  and jobchain finds the engine through `~/work/ai/jobcheck/src` — so whichever branch is
  checked out there is the one jobchain's own suite runs against. Checking out `claude`
  in jobcheck breaks `simplify-port`, and the reverse.

## Decisions worth knowing before changing things

**The project is `jobcheck` and the vocabulary is "check", deliberately.** It was renamed
to `pandas-row-validation` on 2026-09-09, package and words together, and renamed back on
2026-09-10 at the owner's instruction. The reason is concrete: a file named `test_*.py`
inside an adopter's package is collected by pytest, which imports it a second time under
its own rules and reports the registry's duplicate-code guard as a mysterious test failure.
So check files are `check_*.py` and the API is `CheckResult`, `CheckOutcome`,
`register_check`, `load_checks`, `CHECKS`. Do not "modernise" this.

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
- **Chasing the last 131 mutation survivors** — the default-argument ones are mutants
  mutmut's own trampoline cannot execute (verified by hand), several are unreachable
  branches or equivalent on this platform (`utf-8` and `\n` are what Linux gives anyway),
  and the rest are print-function wording that the catalog and golden files pin byte for
  byte while mutmut cannot run either. `docs/testing.md` carries the classification.
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

- **Performance baseline**, re-recorded after the simplification, 4,000-row frame,
  Python 3.12.14 on this machine, stored in the gitignored `.perf-baseline.json`:
  `validate` 6.250s (spread 8%), `validate_row` per row 6.174s (2%), `build_report`
  0.048s (123%), `render_report` 0.048s (8%), `summarise_outcomes` 0.020s (7%),
  `validate` with 50 rules over 1,000 rows 0.403s (14%). The gate is the machine's own measured spread doubled, floored at 35% and
  capped at 150%; verified by lowering a baseline and watching it report
  `6.15s against a limit of 2.06s`.
- **Where the time goes**: `explain_row` is about 85% of a validation run, and inside it
  the example checks' `dates_present` and `dates_in_order` are roughly 40% of the total,
  because both call `pandas.to_datetime` per row. That is example code, not library code.
- **Suite runtimes**: fast 15s, long ~320s, cov 25s, memory 72s, perf ~84s. A full
  mutation run took ~6 minutes at about 5 mutations/second on the larger tree.
- **Lost source sizes**, read from the `.pyc` headers: `run` 10,756 B, `lint` 14,326 B,
  `parallel` 15,072 B, `params` 7,173 B; the lost test modules total roughly 150 KB.

## Environment and housekeeping

- **Use `PYTHON=~/.conda/envs/pytesting/bin/python`** for anything but the fast suite. The
  default `python3` is anaconda 3.14.6 without hypothesis or mutmut.
- **Never install anything without asking.** Test tooling belongs in the `pytesting` env.
- Generated and gitignored: `mutants/` (19 MB after a run), `.build/` (the saved profile),
  `.mypy_cache/`, `.pytest_cache/`, `.perf-baseline.json` (962 bytes, machine-specific by
  design), `reviews/`.
- `reviews/` is empty: the review saved on 2026-09-10 was worked through and cleared.
- `.build/` is now gitignored; `.build/examples.prof` had been tracked because the
  pattern was `build/`, and it is untracked as of `fab967a`.
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
number. Delete the tree whenever the package layout changes — **which this branch did**,
so the first mutation run here must start from a clean tree.

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
