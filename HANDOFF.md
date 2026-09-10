# Handoff

Written 2026-09-10. Branch `claude`, eight commits ahead of `main`, tree clean.
Read `CLAUDE.md` first — it holds the forensics on the 2026-09-09 accident and the
rename, and this file assumes them. `recovery/README.md` is the second thing to read
if anything about the lost modules matters.

## State

Measured on 2026-09-10, Python 3.14.6, pandas 2.x, on the `claude` branch.

| Gate | Result |
|---|---|
| `./run-tests.sh` (fast, the commit gate) | 529 passed, 1 skipped, 94 deselected, 22s |
| `./run-tests.sh long` | 94 passed, 1 skipped, 153s |
| `./run-tests.sh all` | 623 passed, 1 skipped, 150s |
| `./run-tests.sh cov` | 100% of statements and branches, against a 95% floor |
| `./run-tests.sh types` (mypy) | clean, 47 source files |

The one skip is `tests/test_properties.py`, which needs hypothesis.

## What this session changed

The repository was in the state the accident left it: healthy on its own terms, missing
two entry points it used to have, with the only copy of the lost code sitting in
`__pycache__` under rules that ignore `*.pyc`.

- **`recovery/`** now tracks that bytecode — `src/jobcheck/__pycache__` whole, the
  `cpython-312` generation of `tests/__pycache__`, and `examples/checks/__pycache__` —
  with a `.gitignore` exception. A tarball also sits outside the repository at
  `~/work/ai/jobcheck-bytecode-backup-2026-09-10.tar.gz`.
  `scripts/read_bytecode_api.py` reads names, parameters and docstrings out of a `.pyc`
  with `marshal` and generates `recovery/recovered-api.md` and
  `recovery/recovered-tests-api.md`.
- **`load_test_files(paths)`** in `registry.py`, rebuilt from the check-era `load_checks`.
  Files named explicitly, nothing discovered, repeats skipped, dependencies validated at
  the end of the call, a unique module name per file, no `__pycache__` written beside the
  caller's file. `loaded_files()` reports them; `clear_registry()` forgets them.
- **`run.py`**, rebuilt from `recovery/bytecode/jobcheck/run.cpython-312.pyc`: `validate`,
  the streaming `iter_traces`, and `ValidationRun` / `RowTrace` / `RunStats`.
  `ValidationRun.errors` is new rather than recovered.
- **`tests/test_differential_jobchain.py`**: what jobchain's suite asserted of the
  check-era engine, restated here. All of it holds.
- Docs follow: `README.md` gained a worked `validate` block, `docs/interfaces.md` the new
  calls, and `docs/architecture.md`'s module table was listing two files that do not exist
  while omitting five that do.
- `CLAUDE.md` was untracked. It is committed now, and updated where this session changed
  its answers.
- `~/work/ai/jobchain` was ported on its own branch `claude-port`: 744 tests pass with
  nothing skipped (it was 724 passing, 20 skipped), the 103-case example catalogue passes,
  and its coverage gate went from 85% failing an 89% floor to 89% passing it.

## Not addressed — the real to-do list

- **`lint`, `parallel` and `params` are still only bytecode.** The decision and the reason
  to revisit each is in `recovery/README.md`. `lint` is the one with obvious value: rule
  files that parse but can never fire, fire everywhere, or were superseded.
- **The eleven lost test modules have not been rebuilt.** `recovery/recovered-tests-api.md`
  lists what each asserted, by name and docstring. `test_error_messages` (10,991 B) and
  `test_rules_unit` (7,997 B) cover surfaces that still exist here.
- **One catalog case is path-length dependent.**
  `tests/examples/verbosity/source-files-and-by-rule-table` renders absolute paths; the
  `<project>` substitution in `tests/catalog.py` fixes the text but not the column widths,
  which were computed from the full path. Regenerated so the suite is green here, and it
  will fail on a clone at a path of a different length. The fix is to render through a
  fixed-length root, in the catalog machinery.
- **jobchain's `claude-port` branch is unmerged**, as is this one.

## Considered and deliberately not done

- **Installing a decompiler.** `pycdc` would have to be built from source and nothing here
  reads 3.12 bytecode; `uncompyle6`/`decompyle3` stop at 3.8. Reading the interface out
  with `marshal` and writing the bodies again was enough for `run` and `load_checks`, and
  is the documented route for the rest.
- **Deleting `src/jobcheck/`.** It is the original of what `recovery/` now copies. Left in
  place; deleting it is a decision to make once, deliberately.
- **Keeping a `load_checks` alias.** The vocabulary here is "test"; an alias in the old
  vocabulary would outlive its reason.
- **Renaming jobchain's `JOBCHECK` / `JOBCHECK_SRC` variables.** They point at
  `~/work/ai/jobcheck`, which is still the directory's name.
- **Making jobchain's rule files load unchanged.** The check-era format's keys are
  rejected as typos here, which is right: ignoring them would disable nothing while the
  caller believed a code was switched off. jobchain's files were rewritten instead.

## Decisions worth knowing before changing things

- **A path-loaded test file lands in `BASE_SUITE`.** `_infer_suite` maps a module name with
  fewer than three dotted parts there, and `load_test_files` gives each file a flat name.
  That is deliberate: the base suite is always loaded, so a file named by path always runs.
- **`validate` is a layer over `explain_row`, not a second engine.** `collect_outcomes`
  and `iter_traces` call the same per-row function; there is one implementation of the
  algorithm and three ways to spend memory on its results.
- **The differential tests are evidence about lineage, not just a regression suite.** They
  are the standing experiment on whether this tree or the 09-07 tree was later.

## Measurements, so they are not re-derived

- Source sizes of the lost modules, from the `.pyc` headers: `run` 10,756 B, `lint`
  14,326 B, `parallel` 15,072 B, `params` 7,173 B. The lost test modules total roughly
  150 KB.
- `marshal.loads` under Python 3.14 reads a 3.12 code object fine; `dis` on the same
  object raises `IndexError` (the opcodes moved). That is why the reader script prints
  names and docstrings rather than disassembly.
- Two details put the "test" vocabulary before the evening of the rename: check-era
  `params` already defines `TestParams`, and check-era `run` already imports `TestRecord`.
- The check-era rule format was `RULE_KEYS = {name, action, codes, column, pattern}`,
  matched with `fnmatchcase`. Today's is a `match:` list of regex criteria. Whichever tree
  is later overall, this file format is later here.

## Things that will bite

- **`git log` starts on 2026-09-09 and that is an accident, not the project's age.** Do
  not date anything from it.
- **`src/jobcheck/` is on the path if you add `src/` to it.** It holds no modules, so
  `import jobcheck` succeeds as an empty namespace package and then fails at the first
  attribute. jobchain guards against exactly this in `_import_engine`.
- **`recovery/bytecode/` is tracked against `.gitignore`'s own rules** — the negation at
  the bottom of `.gitignore` is what keeps it. A tidy-up of that file can silently make
  the only copy of the lost code untracked again.
- **The registry is process-global.** Every test that registers anything takes the
  `fresh_registry` fixture, which now saves and restores `_LOADED_FILES` as well.
