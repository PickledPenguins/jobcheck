# Handoff

Written 2026-09-15. Branch `simplify`, commit `b648bcf`, 41 commits ahead of `main`, tree
clean apart from this file. Start at `README.md` and the documents its index links; `.claude/CLAUDE.md` holds the
project's history, which is stranger than most. This session was a review session: four
`creview` passes (package, tests twice, catalog), one `creadme` audit, one `caddressreview`
run. Two commits, no new features.

## State

Measured with the conda `pytesting` environment (`~/.conda/envs/pytesting/bin/python`,
Python 3.12.14, pandas 3.0.5, pytest 9.1.1, mypy 2.3.1, hypothesis 6.167.1).

| Gate | Result | Observed |
|---|---|---|
| `./tests/run-tests.sh fast` | 610 passed, 18s, then mypy clean (57 files) | 2026-09-15 against `b648bcf` |
| `./tests/run-tests.sh long` | 235 passed, 289s, 56 pandas `RuntimeWarning`s from `test_fuzz.py` datetime casts (benign) | 2026-09-15 against `b648bcf` |
| `cov`, `perf`, `memory` | **not run this session**; the 2026-09-12 handoff recorded 100% / passing at `966c9ff` | unverified since |
| Mutation | **not run**; `docs/testing.md` records 89.5% at `9fe2207`, now seven source commits back | stale, labeled as such in the doc |
| pyflakes | clean on `tests/`, `examples/`, `scripts/`; one hit in `src/jobcheck/registry.py:24`, a deliberate re-export of `MatchCriterion` | 2026-09-15 |

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh long    # + the profile, ~5 min
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh cov
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh perf
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh memory
~/.conda/envs/pytesting/bin/python -c "import pandas, sys; sys.argv=['mutmut','run']; \
    from mutmut.__main__ import cli; cli()"                      # mutation, see the traps
```

Run anything past the fast suite through `~/work/ai/skills/bin/bgrun` and wait on the
process: `id=$(bgrun start -l long -- env PYTHON=... ./tests/run-tests.sh long); bgrun wait "$id" -t 900`.
Its log is at `/tmp/bgrun-1000/<id>/log`.

## What this session changed

- **`ac773d9` Make the docs say what the code does, and run their blocks to keep it so.**
  Three documents described the pre-rename design: bare bool/`Status` returns "converted"
  (`normalize_result` refuses both), statuses "extensible from 10" (fixed at five), groups,
  suites inferred from module paths, a "one module" engine. `writing-checks.md` showed
  `@group(...)`, which raises `NameError`. Every `docs/*.md` Python block now executes
  inside a seeded world (`tests/test_docs_unit.py::documented_world`: demo frame, outcomes,
  rules, the illustrative check paths written as copies of shipped checks); a second test
  pins that a bare bool return raises and no document says otherwise.
- **`b648bcf` A failed check file registers nothing, and the tests that could not fail
  now can.** Package: `load_checks` drops a failing file's own registrations (per file,
  not per call — `test_faults.py::test_the_good_files_of_a_failed_call_still_registered`
  pins that earlier files stay); `validate` refuses a bad `on_error` before the loop and a
  non-DataFrame with a pointer to the per-row calls. Suite: the rule fuzzer had generated
  a `description` key and accepted zero rules in 300 cases — it now draws each key valid
  four times in five and asserts on rules accepted (36 with the seed); the export guard
  walks the package instead of a hand list that missed `engine` and `registry_tables`;
  two ordering tests, one memory test and one misnamed test that could not fail now can;
  `test_pathological.py` had six double-encoded UTF-8 strings; the catalog symlink is per
  clone as well as per user; two catalog cases pointed at rows their rules did not touch;
  one byte-identical case dropped, three added (misspelled key, missing message,
  column-not-in-data warning). 25 unused imports removed.

## In flight — where the session stopped

Nothing mid-edit. The session ended with `caddressreview` having applied every silent fix
and the owner deciding to **leave all eleven held findings open in the reports**. The next
concrete step is that decision: read the four reports in `.agent/reviews/` and approve or
decline each held item. Nothing is tentative in the code.

## Not addressed — the real to-do list

The eleven held findings, all still in `.agent/reviews/` with their evidence. The owner has
seen the list and chose to hold, not decline, so they are open rather than rejected:

- **`print_report(fmt="csv")` on an empty report prints `No failures.`, not a CSV header.**
  `report.py:219`. Two catalog READMEs (`data/clean-file-as-csv`,
  `complex/clean-file-every-rule-csv`) promise the header and their recorded output shows
  the prose. Decide which is right; the catalog cases are the test either way.
- **Rule patterns never match an integer column in an all-numeric frame.** `rules.py:213`.
  `iterrows` upcasts to float, `cell_text` sees `102.0`, `^102$` fails silently. Fix shape:
  render whole floats without `.0` in `cell_text` (share `report._format_cell` via
  `tables.py`), document in `configuration.md`, and add the regression test through
  `validate` on a numeric frame — `test_non_string_values_are_matched_as_text` builds its
  Series by hand, which is why this escaped.
- **`validate` hands checks `RowContext()`; `validate_row`/`explain_row` hand `None`.**
  `engine.py:113`. `test_ctx_defaults_to_none` (`test_validate_row_unit.py:101`) and
  `test_context_unit.py:48` pin both sides. Fix: substitute in `explain_row`, flip the one
  test, note in `interfaces.md`.
- **The internal-test exemption case shows nothing.** `qa@internal.test` passes both email
  checks on its own, so `overrides/internal-test-accounts-exempted` is byte-identical to
  `data/validate-a-csv-file`. Fix is in `scripts/make_example_data.py` (give one internal
  row a domain the check rejects), then regenerate the data, the catalog and the golden
  files and read the diff — roughly twenty expected outputs move.
- Lows: newline inside an unwrapped cell breaks the table (`tables.py:47`); the deep-chain
  error's `deepest declared depends_on: N` is width, not depth (`registry.py:352`, one
  exact-text test); `test_scaling.py:67` uses single measurements where `fastest()` exists
  (+1–2 min long suite); 55 test names still say `test` for check; example READMEs are
  split on stating `exit 0`; seven large-export catalog cases (1.1 MB of 1.6); and
  `scripts/new_catalog_case.py` dedupes commands but not outputs.
- **Mutation has not run since `9fe2207`.** Seven source commits later. The first test
  review found the fast gate blind to `root_cause_counts` ordering — that would have been
  a survivor nobody classified. Read the survivors in `report.py` and `engine.py` as logic,
  not wording.
- **`rules.py` matching has no timeout** (carried from the last handoff).
  `test_safety.py` now says plainly that its regex test pins survivability of a 23-char
  value, not safety.
- **jobchain's suite still fails against this branch** (carried; unchanged): five of its
  override-rule fixtures lack `message:`.
- **`test_docs_unit.py` is 473 lines carrying six concerns** — the next split candidate.

Settled by standing preference, not open: work stays on `simplify` and is not merged;
breaking the CLI or the Python API is acceptable, no shims; no CI; no changelog; the
license is the owner's; **American English everywhere, identifiers included**.

## Considered and deliberately not done

- **Whole-call rollback in `load_checks`** (snapshot before the loop, restore on any
  failure). Proposed by the package review, rejected on the sniff test because
  `test_the_good_files_of_a_failed_call_still_registered` pins that files loaded before a broken one stay loaded — "loading is
  not transactional, and the loaded files say so". The fix landed per file instead.
- **Adding `pyflakes tests` to the fast gate.** Not done; the imports were cleaned once.
  Reopen if they come back.
- **`docs/*.md` blocks as a cumulative session like the README's.** Rejected: the blocks
  are independent fragments (two load `check_age.py`), so each runs standalone in a fresh
  registry inside the seeded world.
- The earlier handoff's closed items still hold: no narrowing of the registry table by
  breaking words or counting rules, no docstring rationale moved to `architecture.md`, no
  `explain_row` split, no shared path-guard helper, no shared empty-table print.

## Decisions worth knowing before changing things

- **A failed check file loads nothing; earlier files in the same call stay.** Both halves
  are tested (`test_load_files_unit.py::test_a_file_that_raises_after_registering_leaves_none_of_its_checks_behind`,
  `test_faults.py::test_the_good_files_of_a_failed_call_still_registered`).
- **The suite was right and the docs were wrong about bare returns.** `test_results_unit.py`
  had always pinned that `True` and `Status.MISSING` raise; three documents said otherwise.
  When a document and a test disagree here, check the test first.
- **`documented_world` lays down the files the docs name.** `my_checks/check_age.py` and
  `runs/2026-09-10/inputs/checks.py` do not exist in the repository; the test writes copies
  of shipped checks at those paths in a tmp cwd so the blocks run rather than being
  excused. Add a new illustrative path to `ILLUSTRATIVE_CHECK_FILES` when a doc uses one.
- **Catalog stable root is `prv-catalog-root-<uid>-<8-hex sha1 of the clone path>`.**
  Fixed length still; `test_cases_run_through_a_root_of_a_fixed_length` asserts 17+8+1+8.
- **The rule fuzzer's `VALID`/`INVALID` tables are the schema, restated.** A new rule key
  must be added to both or every generated rule fails on it and the accepted-rules floor
  (20) trips — which is the point.

## Measurements, so they are not re-derived

- **Fuzzer, seed 20260902, 300 files**: before the fix 0 rules accepted (138 files rejected
  for the `description` key); after, 36 rules accepted, 186 files rejected across nine
  distinct messages including the regex branch.
- **`test_row_by_row_memory_does_not_grow_with_the_frame`**, frames built outside the trace:
  clean engine peaks 0.2 MB (2,000 rows) and 0.6 MB (8,000); an engine leaking every
  outcome peaks 5.0 MB and 19.8 MB. Bound is `large - small < 2 MB`.
- **`test_interface_cli.py`**: nine identical default subprocess runs at ~0.6s each
  replaced by one module fixture; fast suite 21s → 18s.
- **Catalog**: 61 cases (42 examples: 17 simple, 15 moderate, 10 complex; 19 failures),
  1.6 MB, 1.1 MB of it the seven `large-export` cases.
- Suite runtimes this session: fast 18s, long 289s. `cov`, `perf`, `memory` not measured.

## Environment and housekeeping

- **Use `PYTHON=~/.conda/envs/pytesting/bin/python`** for anything but the fast suite. The
  default `python3` is anaconda 3.14.6 without hypothesis or mutmut; the pre-commit hook
  runs the fast suite under it (one test skips there).
- **Never install anything without asking.**
- Generated and gitignored: everything under `.build/`, plus `.agent/reviews/` and
  `mutants/`.
- **`.agent/reviews/` holds four reports**, all with open held findings; `caddressreview`
  keeps a report until every finding in it has an outcome. Newest first:
  `2026-09-15T10-57-59` (catalog), `10-38-42` (tests pass 2), `02-44-26` (tests pass 1),
  `00-46-18` (package). Eleven held items across the four, some cited in two reports;
  the silent fixes in each are already applied at `b648bcf`.
- A sibling clone `~/work/ai/jobcheck-main/` exists; the catalog symlink change is what
  makes running both suites at once safe for the catalog (timing gates still are not).

## Things that will bite

Every trap from the 2026-09-12 handoff still applies: a `@dataclass` defined inside a test
function under `fresh_registry` (the docs-block test registers a throwaway module in
`sys.modules` for exactly this reason); `mutmut` needs pandas imported first; a targeted
`mutmut run <name>` discards every other result; a stale `mutants/` lies; the exclusions in
`pyproject.toml` are load-bearing; `long` refuses to run without hypothesis; regenerating
is not fixing — read the diff; do not run two timing suites at once; long commands die at
the foreground timeout — use `bgrun`. Added this session:

- **`scripts/new_catalog_case.py` runs the case immediately.** Write the fixture
  `rules.yaml` *before* creating a case that names it, or the recorded output is a
  `FileNotFoundError` and the exit code is wrong; `regen_catalog.py <substring>` repairs it.
  Also refuses an existing directory, so do not `mkdir` the case first.
- **`test_the_documented_suite_sizes_are_the_real_ones` fails on any test count change.**
  Every test added or removed means editing the two rows in `docs/testing.md` (fast, long,
  all). It is doing its job; it is also the first thing to break after any suite edit.
- **Sniff-test findings against the file, not against remembered output.** One finding
  this session (`test_context_unit.py:68` "asserts the registry is empty") came from
  reading two concatenated command outputs as one; the test was fine.
- **`pytest -p no:cacheprovider` prints an `Unknown config option: cache_dir` warning** —
  harmless, but noisy in `tail -1` checks. Leave the cache plugin on.
- **`grep -o "exit [0-9]"` on catalog READMEs** matched nothing for 33 examples: they do
  not state an exit code. That is the open low, not a broken test.
