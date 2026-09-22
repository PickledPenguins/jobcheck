# Handoff

Written 2026-09-21. Branch `simplify`, commit `3500999`, 42 commits ahead of `main`, tree
clean. Start at `README.md` and the documents its index links; `.claude/CLAUDE.md` holds the
project's history, which is stranger than most. This session was a gate-and-ledger session:
one `creview` (of the uncommitted handoff), one `ctesting` audit with every gate run and
mutation re-measured, one `creadme` audit, one `caddressreview` that worked all six reports
to an outcome. One commit, no new features.

## State

Measured 2026-09-21 against `b648bcf` (and the fast and long suites again against the
working tree that became `3500999`) with the conda `pytesting` environment
(`~/.conda/envs/pytesting/bin/python`, Python 3.12.14, pandas 3.0.5, pytest 9.1.1,
mypy 2.3.1, hypothesis 6.167.1, mutmut 3.5.0), one gate at a time.

| Gate | Result | Observed |
|---|---|---|
| `./tests/run-tests.sh fast` | 612 passed, 17.8s, mypy clean (57 files) | 2026-09-21, tree of `3500999` (610 at `b648bcf`) |
| `./tests/run-tests.sh cov` | 100% lines and branches: 880 statements, 296 branches, 0 missed; floor 95 | 2026-09-21 at `b648bcf` |
| `./tests/run-tests.sh long` | 235 passed, 299s, 56 pandas `RuntimeWarning`s from `test_fuzz.py` (benign); profile printed | 2026-09-21, tree of `3500999` (294s at `b648bcf`) |
| `./tests/run-tests.sh perf` | 6 passed, 91s, against `.build/perf-baseline.json` | 2026-09-21 at `b648bcf` |
| `./tests/run-tests.sh memory` | 3 passed, 80s | 2026-09-21 at `b648bcf` |
| Mutation | 1,304 mutants, 1,175 killed, 129 survived, 0 timeouts — 90.1%, 208s at 6.0/s | 2026-09-21 at `b648bcf`; the new assertions in `3500999` kill at least four more (each checked with `breaks-it`), not re-run |
| pyflakes | clean on the three test files touched | 2026-09-21 at `3500999` |

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh long    # + the profile, ~5 min
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh cov
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh perf
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh memory
rm -rf mutants .mutmut-cache && ~/.conda/envs/pytesting/bin/python -c \
    "import pandas, sys; sys.argv=['mutmut','run']; from mutmut.__main__ import cli; cli()"
```

Run anything past the fast suite through `~/work/ai/skills/bin/bgrun` and wait on the
process: `id=$(bgrun start -l long -- env PYTHON=... ./tests/run-tests.sh long); bgrun wait "$id" -t 900`.
Its log is at `/tmp/bgrun-1000/<id>/log`. Never two timing suites at once: this session ran
long, then mutation, then perf, then memory, in sequence.

## What this session changed

- **`3500999` Pin four messages word for word, and the checks that survive a failed
  load.** Suite: `test_error_messages_unit.py` gains the bare-string-path message of both
  loaders and `validate`'s non-DataFrame error in full; `test_overrides_unit.py` asserts two
  unknown keys as a sorted comma list and every match-block rejection opening with
  `rule 'r' in <path>: `; `test_faults.py`'s partial-load test calls `explain_row` afterward
  so a stale order cache on the failure path would show as zero checks run. Each new
  assertion was checked with `breaks-it` against the mutant it was written for. Docs:
  `testing.md` carries the 2026-09-21 mutation figures, per-module survivors, the
  classification of the 47 non-print survivors, the measured gate timings and the suite
  sizes 612/847; `future-work.md` gains F.4 through F.16. The 2026-09-15 handoff, which had
  never been committed, went in with three wording fixes.

## In flight — where the session stopped

Nothing mid-edit. `.agent/reviews/` is empty: every finding in all six reports has an
outcome (fixed at `b648bcf`, fixed at `3500999`, rejected, or recorded in `future-work.md`
by the owner's decision). The next concrete step is whichever of F.4–F.16 the owner picks;
each entry says where to start.

## Not addressed — the real to-do list

- **`docs/future-work.md` F.4–F.16** are the thirteen items the owner chose on 2026-09-21
  to record rather than build: csv header on an empty report (F.4), the float-upcast id
  match (F.5, reproduced: any float column makes `iterrows` render an int id as `101.0`;
  an all-int frame is fine), `RowContext()` vs `None` (F.6, reproduced), newline in an
  unwrapped cell (F.7), deep-chain width vs depth (F.8), the regex bound (F.9, two shapes
  given), `clear_registry` eviction of plain-import modules (F.10, root of the dataclass
  trap), the internal-test catalog case (F.11), exit codes in 33 READMEs (F.12),
  large-export size (F.13), output dedupe in `new_catalog_case.py` (F.14), single-measure
  ratios in `test_scaling.py` (F.15), 55 `test`-vocabulary names (F.16). Each has the fix
  written beside it; F.5 and F.6 are the two a user can hit.
- **Mutation survivors still worth a look: the 82 in `report` and `registry_tables`.**
  Classified by function name this session (print wording, catalog-pinned), not read one
  by one. Of the 17 real gaps among the 47 read, `3500999` closes four; the rest are F.10
  and message wording.
- **jobchain's suite still fails against this branch** — not checked this session;
  recorded 2026-09-12 at `966c9ff`: `~/work/ai/jobchain` (branch `simplify-port`) reads
  this `src` live and five of its override-rule fixtures lack `message:`. One line each;
  grep for `action: disable` and `action: enable`.
- **`test_docs_unit.py` is 473 lines carrying six concerns** — the next split candidate.
  Unchanged this session.
- **No gate on the mutation score.** `docs/testing.md`'s section is the only record and no
  test covers it, so it drifts again after the next source change. A floor in the runner
  would be a release gate (208s), not a commit one. Raised by the ctesting audit; not
  decided.

Settled by standing preference, not open: work stays on `simplify` and is not merged;
breaking the CLI or the Python API is acceptable, no shims; no CI; no changelog; the
license is the owner's; **American English everywhere, identifiers included**; held
review findings go to `future-work.md`, not into code, until the owner names one.

## Considered and deliberately not done

- **A fifth whole-tree `creview` at `b648bcf`.** Not run: four reports at that commit were
  still open with eleven held findings, so the review scoped itself to the one dirty file
  (the handoff) and said so. Reopen after F.4–F.16 move the code.
- **Silently fixing F.7 (newline cell) and F.5 (float id).** Both have one obvious fix
  shape and a wrong output, which is the silent column — but the owner had held them on
  2026-09-15 and on 2026-09-21 chose future-work for everything non-silent. Not a
  rejection of the fixes; a rejection of building them unasked.
- **Deleting the 2026-09-10/09-11 mutation history from `docs/testing.md`.** Reworded to
  read as history and kept; `creadme` does not own records and removing them is the
  owner's call.
- Carried from 2026-09-15 and 2026-09-12, still closed: whole-call rollback in
  `load_checks` (per-file landed instead; `test_the_good_files_of_a_failed_call_still_registered`
  pins it); `pyflakes tests` in the fast gate; `docs/*.md` blocks as one cumulative
  session; narrowing the registry table by breaking words or counting rules; docstring
  rationale moved to `architecture.md`; an `explain_row` split; a shared path-guard
  helper; a shared empty-table print. `future-work.md` "Considered and deliberately not
  done" holds the evidence for each.

## Decisions worth knowing before changing things

- **A failed check file loads nothing; earlier files in the same call stay, and they
  run.** Pinned by `test_a_file_that_raises_after_registering_leaves_none_of_its_checks_behind`
  and `test_the_good_files_of_a_failed_call_still_registered` (which since `3500999` also
  validates a row afterward).
- **Library error messages are pinned word for word in `tests/test_error_messages_unit.py`.**
  A new message goes there in full, not as a substring elsewhere — the three from
  `b648bcf` were the substring kind and survived nine mutants until this session.
- **`_get_topo_order` tests `is None`** (`registry.py:384`), so every path that
  invalidates the cache must set `None`, not a falsy value. The failed-load path is now
  the one that is pinned.
- **The suite was right and the docs were wrong about bare returns** (2026-09-15). When a
  document and a test disagree, check the test first.
- **`documented_world` lays down the files the docs name** (2026-09-15). Add a new
  illustrative path to `ILLUSTRATIVE_CHECK_FILES` when a doc uses one.
- **Catalog stable root is `prv-catalog-root-<uid>-<8-hex sha1 of the clone path>`**
  (2026-09-15); `test_cases_run_through_a_root_of_a_fixed_length` asserts 17+8+1+8.
- **The rule fuzzer's `VALID`/`INVALID` tables are the schema, restated** (2026-09-15). A
  new rule key must be added to both.

## Measurements, so they are not re-derived

- **Mutation survivors at `b648bcf`, 129**: `report` 52, `registry_tables` 30, `engine` 20,
  `registry` 15, `rules` 10, `tables` 2. Of the 47 outside the print modules, read as
  diffs: 7 default-argument (unkillable through the trampoline), 9 unreachable, 14
  equivalent, 17 real assertion gaps — four of which `3500999` closes (messages ×9
  mutants, unknown-keys join, match-block rule name, failed-load cache); the rest are
  F.10 and print wording.
- **Float upcast** (F.5): on pandas 3.0.5, `pd.DataFrame({"id":[101,102],"age":[1,2]})`
  keeps `id` as `101` through `iterrows`; adding one float or one blank to `age` makes it
  `101.0` and `^102$` stops matching.
- **Context types** (F.6): the same check sees `RowContext` from `validate` and `NoneType`
  from `validate_row` and `explain_row`.
- Gate runtimes 2026-09-21: fast 17.8s, cov 23s, long 294–299s, perf 91s, memory 80s,
  mutation 208s.
- Carried from 2026-09-15 at `b648bcf`: fuzzer seed 20260902, 300 files, 36 rules
  accepted, 186 files rejected across nine messages; memory test clean engine 0.2 MB
  (2,000 rows) / 0.6 MB (8,000), leaking engine 5.0 / 19.8 MB, bound `large - small < 2 MB`;
  catalog 61 cases (42 examples: 17 simple, 15 moderate, 10 complex; 19 failures), 1.6 MB,
  1.1 MB in the seven `large-export` cases.
- Carried from 2026-09-12 at `966c9ff`: perf baseline on a 4,000-row frame, `validate`
  6.250s, `validate_row` 6.174s, `build_report` 0.048s, `render_report` 0.048s,
  `summarize_outcomes` 0.020s, `validate` with 50 rules over 1,000 rows 0.403s. The
  baseline file still holds a stale `summarise_outcomes/4000` key beside the current one
  (seen 2026-09-21); harmless, gitignored.

## Environment and housekeeping

- **Use `PYTHON=~/.conda/envs/pytesting/bin/python`** for anything but the fast suite. The
  default `python3` is anaconda 3.14.6 without hypothesis or mutmut; the pre-commit hook
  runs the fast suite under it (one test skips there — observed 2026-09-21 at the
  `3500999` commit).
- **Never install anything without asking.**
- Generated and gitignored: everything under `.build/`, plus `.agent/reviews/` (empty
  now) and `mutants/` (removed after this session's run).
- A sibling clone `~/work/ai/jobcheck-main/` exists; the catalog symlink is per clone,
  so both suites can run at once for the catalog (timing gates still cannot).
- Tools used this session from `~/work/ai/skills/bin/`: `bgrun` for every long run,
  `subst` for every doc and test edit, `breaks-it` to confirm each new assertion fails on
  its mutant.

## Things that will bite

Every trap from the 2026-09-15 and 2026-09-12 handoffs still applies: a `@dataclass`
defined inside a test function under `fresh_registry` fails because `clear_registry`
evicts the test module (now F.10); `mutmut` needs pandas imported first; a targeted
`mutmut run <name>` discards every other result; a stale `mutants/` lies; the exclusions
in `pyproject.toml` are load-bearing; `long` refuses to run without hypothesis;
regenerating is not fixing — read the diff; do not run two timing suites at once; long
commands die at the foreground timeout — use `bgrun`;
`scripts/new_catalog_case.py` runs the case immediately and refuses an existing
directory; `test_the_documented_suite_sizes_are_the_real_ones` fails on any test count
change (edit the fast and all rows in `docs/testing.md`); sniff-test findings against the
file, not remembered output; `pytest -p no:cacheprovider` prints a harmless
`Unknown config option: cache_dir` warning; 33 catalog READMEs state no exit code (F.12).
Added this session:

- **`test_no_document_names_a_public_function_that_is_gone` rejects any backticked
  `name()` in `docs/` that is not a package, pandas or builtin name** — a test helper
  such as `fastest()` fails it. Write `fastest` helper, without the parentheses.
- **`mutmut results` output is 1,304 lines; `mutmut show <name>` is one process each.**
  Filter `results` to `survived`, strip `__mutmut_N` and `uniq -c` to get survivors by
  function before opening any; showing the 47 logic-module diffs took a few minutes.
- **The pytest tally in `bgrun wait` output can be lost by `tail -N`** on the long suite:
  the profile prints after pytest's summary line. Grep the log for `passed` instead.
