# Handoff

Written 2026-09-11. Branch `simplify`, commit `6104170`, 24 commits ahead of `main`, tree
clean apart from this file. Start at `README.md` and the documents its index links;
`CLAUDE.md` holds the project's own history, which is stranger than most, and its last
section is what this branch changed.

## State

Measured at `6104170` on 2026-09-11 with the conda `pytesting` environment
(`~/.conda/envs/pytesting/bin/python`, Python 3.12.14, pandas 3.0.5, PyYAML 6.0.3,
pytest 9.1.1, coverage 7.16.0, mypy 2.3.1, hypothesis 6.167.1, mutmut 3.5.0).

| Gate | Result |
|---|---|
| `./run-tests.sh` (fast, the commit gate) | 602 passed, 16s, then mypy |
| `./run-tests.sh long` | 231 passed, 276s |
| `./run-tests.sh cov` | 100% of statements **and** branches (895 statements, 314 branches), floor 95 |
| `./run-tests.sh memory` | 3 passed, 88s |
| `./run-tests.sh perf` | 6 passed against `.perf-baseline.json`, 88s |
| `mypy` | clean, 57 source files |
| Mutation | 1,300 mutants, **1,169 killed, 131 survived, 0 timeouts (89.9%)** |

Mutation was measured at `8526f6d`; `src/` has not changed since (`git diff 8526f6d..HEAD
-- src/` is empty), and the commits after it only added tests, so the score is a floor
rather than an estimate. The classification of all 131 survivors is in `docs/testing.md`.

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh all     # + long, then the profile
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh cov     # coverage against the floor
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh perf    # timing vs this machine
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh memory  # peak-memory ceilings
~/.conda/envs/pytesting/bin/python -c "import pandas, sys; sys.argv=['mutmut','run']; \
    from mutmut.__main__ import cli; cli()"                      # mutation, see the traps
```

**Run anything past the fast suite through `~/work/ai/skills/bin/bgrun`**, which waits on
the process rather than on its log: `id=$(bgrun start -l long -- ./run-tests.sh long)` then
`bgrun wait "$id"`. Polling a log for a completion word misses the end of every run whose
last line is something else, which cost this session three stalled waits before the tool
existed.

The default `python3` here is anaconda 3.14.6 and has neither hypothesis nor mutmut, which
is why `PYTHON=` is in every line above. `./run-tests.sh long` refuses to run without
hypothesis rather than skipping the property tests quietly.

Catalog: 42 example cases (17 simple, 15 moderate, 10 complex) and 17 failure cases, all
driven through the real entry point in a subprocess.

## The package, after the simplification

Counted with `~/work/ai/skills/bin/pyloc` — blank lines, comments and docstrings excluded.

| Group | Was | Now |
|---|---|---|
| Package `src/jobcheck/` | 1,428 | **1,052** |
| Demo entry points | 188 (two files) | 89 (one) |
| Example check files | 166 (a package of suites) | 164 (four flat files) |

By module: `report` 230, `registry` 195, `rules` 138, `engine` 131, `__init__` 112,
`registry_tables` 103, `results` 90, `tables` 41, `context` 12. `run.py` is gone.

Smaller than the 1,428 it replaced, larger than the 660-700 the first analysis projected,
because two of the nine proposed strips were kept at the owner's instruction (the summary
views, 54 lines, and the extra registry tables, 59) and `validate` survives at about 25
lines rather than going with the rest of `run.py`.

## What this session changed

Six commits here, oldest first.

- `fab967a` — **the simplification**. `run.py`, `check_group`, the suite mechanism and the
  `suite` column, extensible statuses, two of the three override loaders, the second demo
  entry point and eight of its twelve flags, all gone. `CLAUDE.md`'s last section carries
  the table of what replaced what.
- `5addf23` — the handoff rewritten for the tree that resulted.
- `e6bfe27` — two more documentation tests, from a `creadme` audit: every check code a
  document shows must exist (`docs/reporting.md` was showing `AGE_IN_RANGE`, which nothing
  defines), and the exit-code table in `docs/cli.md` is now derived from the `SystemExit`
  constants in `examples/main.py`, both directions.
- `8526f6d` — the `ctesting` audit's findings. `tests/test_validate_unit.py` was documented
  and did not exist; restored, and then found to pass against a `validate` that reverses
  the frame, because every check it used gave every row the same verdict. Three catalog
  cases had byte-identical commands to another case. Mutation re-run and its nine real
  gaps killed.
- `6104170` — the friction log from building the catalog, saved to `reviews/` and acted on:
  `--rules` with no paths now means no overrides, `scripts/new_catalog_case.py` exists, and
  two documentation gaps are closed.

In `~/work/ai/jobchain`, branch `simplify-port` (commits `4ded386`, `d3e8e63`): ported to
this engine and handed off. 744 unit tests pass with nothing skipped, the 103-case
catalogue passes, coverage holds at 89% against its 89% floor.

**That suite reads whichever branch is checked out here**, since it finds the engine at
`~/work/ai/jobcheck/src` rather than at a pinned commit. Checking out `claude` in this
repository breaks `simplify-port` over there, and checking out `simplify` breaks the older
`claude-port`. There is no version constraint to lean on: the engine is a sibling clone,
not a released package.

In `~/work/ai/skills`, branch `claude` (commits `3166e97`, `0412662`, `d7b7e29`, `8d91f94`):
`bin/bgrun`, `bin/subst`, `bin/breaks-it` and `bin/pyloc`, and `ctesting` now saves its
friction log to `reviews/` instead of printing it and forgetting it.

## Not addressed — the real to-do list

- **Mutation has not been re-run since `8526f6d`.** Nothing in `src/` changed, so the score
  stands, but the next change to the package invalidates it. `rm -rf mutants .mutmut-cache`
  first, always.
- **`docs/*.md` code blocks are bound against real signatures but not executed.** Most are
  fragments with an undefined `df`, so executing them means making each self-contained,
  which would make them worse to read. The README's blocks *are* executed byte for byte.
  The new check-code test covers the rot that gap actually produced; revisit only if a doc
  example breaks in a way neither catches.
- **`recovery/README.md` is not reachable from the README index**, because the index test
  only walks `docs/`. It documents a recovery archive rather than current behaviour, so it
  was left out deliberately rather than missed.

Settled by standing preference, not open: the work stays on the `simplify` branch and is
not merged; breaking the CLI or the Python API is acceptable and no compatibility shims are
wanted; there is no CI, and the pre-commit hook plus the release gates are what run the
suites; there is no changelog, because `git log` is the record; the licence is the owner's
to choose.

## Considered and deliberately not done

`docs/future-work.md` carries the full list with the evidence. The ones most likely to be
re-proposed:

- **Dropping the summary views and the extra registry tables.** They were on the strip list
  with measured line counts (54 and 59) and the owner kept them. Do not re-propose.
- **Rebuilding `lint`, `parallel` or `params`** — nothing calls them; `recovery/README.md`
  records what each did and what would reopen it.
- **Chasing the last 131 mutation survivors** — classified in `docs/testing.md`: default
  arguments mutmut's own trampoline cannot execute, unreachable branches, platform
  equivalents, and print wording the catalog pins where mutmut cannot run it.
- **Mirroring the source tree in unit test filenames.** `engine.py` is covered by
  `test_validate_row_unit.py` and `test_validate_unit.py`, named for behaviour. Consistent,
  pre-existing, and renaming 33 files buys nothing.
- **Inferring a report's format from the file extension** — one flag, one meaning.
- **Accepting the check-era rule format** (a top-level `column`/`pattern` glob) — the parser
  rejects those keys as typos, and ignoring them would disable nothing while the author
  believed a code was switched off.
- **Lowering the coverage floor** — the floor is 95 and the suite runs at 100.

## Decisions worth knowing before changing things

**The project is `jobcheck` and the vocabulary is "check", deliberately.** A file named
`test_*.py` inside an adopter's package is collected by pytest, which imports it a second
time under its own rules and reports the registry's duplicate-code guard as a mysterious
test failure. So check files are `check_*.py` and the API is `CheckResult`, `CheckOutcome`,
`register_check`, `load_checks`, `CHECKS`. Do not "modernise" this.

**There is one loading mechanism and one whole-frame call.** `load_checks(paths)` and
`load_overrides(paths)` both take explicit paths and discover nothing; `validate(df, ...)`
returns one list of outcomes per row, in frame order. The second spellings of each — suites,
`collect_outcomes`, a `ValidationRun` object — were removed because two ways to say one
thing is what made this hard to read.

**A `skipped` outcome names only the prerequisite it directly waited for.** `check_group`'s
prerequisites were unconditional and were added to every check in the file, so the old
detail listed transitive ancestors too. Layers and skipping are unchanged; `tests/golden/`
pins the new wording.

**`RowContext` is empty by default.** `build_context` reads nothing out of the row. What
belongs in a context is the adopting pipeline's business.

**Every failure at the shallowest layer is a root cause**, not just the first evaluated.
`root_causes()` returns them all, `root_cause()` returns one for a caller wanting a single
label, and `is_root_cause` flags all of them. jobchain gained this in the port.

**A multi-column key holding `|` raises.** `("a|b","c")` and `("a","b|c")` used to render the
same label, which is the one thing a key column exists to prevent.

**`git log` starts on 2026-09-09 and that is an accident, not the project's age.** The
`.git` directory was removed by mistake and the repository re-initialised. Do not date
anything from the log; `CLAUDE.md` has the forensics.

**Four modules exist only as bytecode.** `lint`, `parallel`, `params` and their tests live
in `recovery/bytecode/`, tracked against `.gitignore`'s own rules by a negation at the
bottom of that file. A tidy-up of `.gitignore` can silently untrack the only copy.

## Measurements, so they are not re-derived

- **Performance baseline**, re-recorded after the simplification, 4,000-row frame, Python
  3.12.14 on this machine, in the gitignored `.perf-baseline.json`: `validate` 6.250s
  (spread 8%), `validate_row` per row 6.174s (2%), `build_report` 0.048s (123%),
  `render_report` 0.048s (8%), `summarise_outcomes` 0.020s (7%), `validate` with 50 rules
  over 1,000 rows 0.403s (14%).
- **Where the time goes**: `explain_row` is about 85% of a validation run, and inside it the
  example checks' `dates_present` and `dates_in_order` are roughly 40% of the total, because
  both call `pandas.to_datetime` per row. That is example code, not library code.
- **Suite runtimes**: fast 16s, long 276s, cov 22s, memory 88s, perf 88s, a full mutation
  run about four minutes at ~6 mutations/second.
- **Lost source sizes**, read from the `.pyc` headers: `run` 10,756 B, `lint` 14,326 B,
  `parallel` 15,072 B, `params` 7,173 B; the lost test modules total roughly 150 KB.

## Environment and housekeeping

- **Use `PYTHON=~/.conda/envs/pytesting/bin/python`** for anything but the fast suite. The
  default `python3` is anaconda 3.14.6 without hypothesis or mutmut.
- **Never install anything without asking.** Test tooling belongs in the `pytesting` env.
- Generated and gitignored: `mutants/` (19 MB after a run), `.build/`, `.mypy_cache/`,
  `.pytest_cache/`, `.perf-baseline.json` (machine-specific by design), `reviews/`.
- `reviews/` holds one report: the friction log from this session, every entry fixed. It is
  gitignored, so it is local to this clone — `cclean` will not remove it, since it is not a
  build artifact.
- `.build/` became gitignored at `fab967a`; `.build/examples.prof` had been tracked because
  the pattern was `build/`, and it is untracked now.
- `scripts/install-hooks.sh` installs the fast suite as `.git/hooks/pre-commit`.
- `pyproject.toml` is the one dependency list; the test that used to read the file reads the
  metadata now, without `tomllib`, which arrived in 3.11 while the declared floor is 3.10.

## Things that will bite

**Long commands get killed at the foreground timeout.** `all`, the catalog, a mutation run
and `regen_catalog.py` all exceed two minutes. Use `~/work/ai/skills/bin/bgrun`; do not
write another loop that greps the log for a completion word.

**`mutmut` needs pandas imported before it starts.** Plain `mutmut run` dies in stats
collection with `RuntimeError: context has already been set` from `multiprocessing`. The
command in the State block works.

**A targeted `mutmut run <name>` throws away every other mutant's result.** Checking one
mutant after writing a test for it is the right move; just expect the score to be gone until
the next full run, and do not quote `mutmut results` in between.

**A stale `mutants/` tree lies about the score.** After the package rename a run over the
existing tree reported an impossible result next to 100% branch coverage. `rm -rf mutants
.mutmut-cache` whenever the package layout changes — which this branch did.

**mutmut runs the *whole* selected suite once per mutant.** `pyproject.toml` excludes the
files that shell out (they never load the instrumentation), the two that read `docs/`, and
the slow suites; without those exclusions a run takes days rather than four minutes.

**The perf gate fails if anything else is using the machine.** Running `perf` and `memory`
concurrently failed `test_summarising_has_not_got_slower` on a tree that passes both when
they are run one at a time. Run the two gates in sequence.

**`./run-tests.sh long` refuses to run without hypothesis.** That is deliberate: a skipped
property suite reads as a pass.

**The catalog runs every case through a symlink** at `$TMPDIR/prv-catalog-root-<8-digit uid>`
so column widths do not depend on the clone's path length. A filesystem without symlinks
falls back to the real root, and one test skips.

**Regenerating is not the same as fixing.** `scripts/regen_catalog.py`, `regen_golden.py` and
`make_example_data.py` all rewrite files the suite compares byte for byte. Read the diff, or
a defect becomes a recorded expectation. `scripts/new_catalog_case.py` prints that warning
every time it writes a case, for the same reason.
