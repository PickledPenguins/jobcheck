# Testing

Back to the [README](../README.md).

Tests run under pytest, split by marker into two suites and three separate gates.
`pytest` and `coverage` are development-only: nothing here is needed to *run* the
framework.

```sh
pip install -e ".[dev]"
./scripts/install-hooks.sh          # once per clone: installs the pre-push gate, switched off
```

## Commands

| Command | Runs | Time |
|---|---|---|
| `./tests/run-tests.sh fast` | 655 tests: unit, interface, contract, documentation, regression, cheap pathological, safety, every error message — then ruff and mypy | 18s |
| `./tests/run-tests.sh long` | 191 tests: integration, load, concurrency, faults, scaling, packaging, fuzz, property, end-to-end catalogs — then the example profile | 100s |
| `./tests/run-tests.sh all` | 846 tests, then ruff, mypy and the profile | 120s |
| `./tests/run-tests.sh cov` | fast suite under coverage, gated at 99% lines and branches (it runs at 99.5%) | 23s |
| `./tests/run-tests.sh perf` | timing against this machine's baseline; its own gate | 21s |
| `./tests/run-tests.sh memory` | peak-memory ceilings under tracemalloc; its own gate | 3s |
| `./tests/run-tests.sh profile` | the example profile alone | 3s |
| `./tests/run-tests.sh mutation` | a clean `mutmut run`, scored by `scripts/mutation_score.py`, gated at 97% (it runs at 98.6%) | 200s |
| `./tests/run-tests.sh types` | ruff and mypy alone | 8s |

Extra arguments pass through to pytest: `./tests/run-tests.sh fast -k dependency`,
`./tests/run-tests.sh long tests/test_load.py`. Each mode exits non-zero on any failure and
prints one summary line. With no mode, `fast` runs; an unknown mode prints the usage line
and exits 2. `PYTHON=/path/to/python` selects the interpreter. The suite points
`HYPOTHESIS_STORAGE_DIRECTORY` at `.build/hypothesis` unless it is already set.

Markers are `fast`, `long`, `perf` and `memory`; `--strict-markers` is on, so a typo
fails rather than silently selecting nothing.

**The long suite refuses to run without `hypothesis`.** A skipped property suite reads
as a pass, and it is the one category that finds cases nobody wrote down, so its absence
fails the gate with a message naming the interpreter rather than printing `1 skipped`.

There is no CI. The pre-push hook and the release gates below are what run these.

## Gates

- **Pre-push** — `./tests/run-tests.sh fast` on each commit being pushed, in a clean checkout
  of it, so uncommitted edits neither fail nor pass it. `scripts/pre-push`, linked into
  `.git/hooks/pre-push.off` (switched off) by `./scripts/install-hooks.sh`; renaming the link
  to `pre-push` switches it on. Bypass with git's own `--no-verify`;
  there is no custom flag. Commits are never gated: work in progress can be committed.
- **Pre-release** — `./tests/run-tests.sh all`, `./tests/run-tests.sh cov`, `./tests/run-tests.sh memory`,
  `./tests/run-tests.sh perf` and `./tests/run-tests.sh mutation`. Coverage below 99% fails
  through `coverage report --fail-under`; a memory ceiling or a timing baseline exceeded
  fails its own run; a mutation score below 97% (set in `tests/run-tests.sh`)
  fails the mutation run, and so does a run that left any mutant unchecked. Run mutation
  last and alone: it contends with the timing tests.

Each gate has been checked by breaking the thing it guards and watching it fail — the
coverage floor by deleting a test, the perf gate by lowering a stored baseline (a 4x
regression reported `6.15s against a limit of 2.06s`), and the row-by-row memory test in
`test_scaling.py` by holding the outcomes the per-row loop is supposed to release
(rechecked 2026-10-03).

## What each file covers

Fast:

| File | Covers |
|---|---|
| `tests/test_registry_unit.py` | Registration and its duplicate guard, `clear_registry`, dependency validation, cycle detection, topological order and its cache. |
| `tests/test_load_files_unit.py` | `load_checks`: files named by path, repeats and reloads refused, module names unique per path and the same every load, prerequisites across files in one call and from an earlier call, that a broken file's error propagates and `clear_registry` recovers, and that no `__pycache__` appears beside the caller's file while a module it imports still gets one. |
| `tests/test_engine_validate_unit.py` | The whole-frame entry point: one list of outcomes per row **in its own position**, rules and the context builder passed through, and both `on_error` modes. |
| `tests/test_engine_repeat_unit.py` | Copies of a row under `validate(repeat_key=...)`: a check that does not repeat runs on the first copy only and is recorded `shared` on the rest, with status `PASS` and a `detail` saying where; `repeat=True` and its dependents run on every copy, each with its own context, reading a shared prerequisite's result from the first copy; rules match every copy, a copy disabling a check records `disabled`, and a check disabled on the first copy runs on the next copy that enables it; copies need not be adjacent; a shared failure is reported and counted once; every refused `repeat_key` and `repeat` value. |
| `tests/test_rules_unit.py` | Every rule-file rejection (24 parametrized cases asserting the exact message), the loader and its ordering, duplicate names, matching semantics, last-rule-wins precedence. |
| `tests/test_results_unit.py` | The fixed status vocabulary, `Verdict` truthiness and validation, and normalizing whatever a check returned. |
| `tests/test_engine_explain_unit.py` | The per-row algorithm, `_explain`: outcomes and their reasons, enabled state, dependency skipping (failed, disabled, errored, transitive), signature adaptation, purity, `warn_missing_rule_columns`, root cause, layers, and the shipped checks at their boundaries. |
| `tests/test_views_unit.py` | The failure table and its columns, row keys and added data columns, `include` levels, titles, explanations and summaries. |
| `tests/test_main_unit.py` | The entry point driven in this process: every flag, every early exit, the report and explain paths, and each error message with its exit code. |
| `tests/test_run_from_config_unit.py` | The run-file entry point in this process: the shipped run's tables in order, paths resolved against the run file, repeated tables, every rejection of a malformed run file word for word, and that a table the library refuses prints none of the run. |
| `tests/test_shipped_examples_unit.py` | `examples/` as a delivered artifact: the rule files load together, which refuses a duplicate rule name or an unknown code, every rule matches a column the data has, the three data files are the size and shape the documentation claims, and the generator still reproduces them byte for byte. |
| `tests/test_differential_jobchain.py` | What jobchain's own suite asserted of the pre-rename engine, restated against this one — layering, root cause, cross-row context, crashes, rule-driven disabling. |
| `tests/test_error_messages_unit.py` | Every message the library raises, compared word for word rather than by keyword: registration, loading, per-row evaluation, reporting and the whole-frame entry point. |
| `tests/test_perf_baseline_unit.py` | The baseline arithmetic itself: recording, comparing, the tolerance floor and cap, and discarding a baseline from another machine. |
| `tests/test_readme.py` | The README executed, byte for byte, plus the prose claims: dependencies, install, the scope limits, the check files it names. |
| `tests/test_docs_api_unit.py` | The documents against the public API, both directions: every call shown binds against the real signature and names something this package, pandas or the builtins provides; every exported function has its real signature in `interfaces.md` -- names, order and defaults -- and every exported type its fields or members; nothing documented there is gone; every check code a document shows is one that exists; no document says a bare bool or status return is converted. |
| `tests/test_docs_blocks_unit.py` | Every Python block under `docs/` runs, in a working directory holding the demo frame, its outcomes, the rules and the check files the blocks name, and prints byte for byte the output shown after it. One collected test per block, plus the fence rule the blocks are read by. |
| `tests/test_regen_docs_unit.py` | `scripts/regen_docs.py`: a stale shown output rewritten and nothing else touched, a right one left alone, a raising block named with its output kept, the world the documents assume, the README run as one session, and the document filter. |
| `tests/test_docs_cli_unit.py` | `docs/cli.md` against the three entry points, both directions: a heading for every flag and argument each parser takes and none for anything else, the usage line argparse prints, every exit code the scripts can return and no other, the run-file table and keys, and the null markers `--data` lists against the ones pandas applies. |
| `tests/test_docs_structure_unit.py` | The documents as a set: the README stays an index and links every document, no internal link or anchor is dead, the rule and setup keys and statuses are documented where they belong, what a document copies from the code matches it -- the shipped rule file, a row in `architecture.md` for every module, entry point and script, a row here for every test module, every list of the summary columns -- and the suite sizes and catalog case counts stated in this document and in the README are the ones a collection and the case directories actually give. It also gates line width: no Python line in `src/`, `examples/` or `scripts/` exceeds the 115 characters `contributing.md` claims, and that document names the three directories the gate covers. |
| `tests/test_mutation_score_unit.py` | `scripts/mutation_score.py`: detected over total across every `.meta` file, the floor boundary, an unfinished run refused, no results refused. |
| `tests/test_docs_messages_unit.py` | Every message a user can meet is quoted in the document that owns it: each exception raised with a message in `src/` and `examples/`, each `error:` line an example script prints, and each warning line, read from the source rather than a list. `interfaces.md`, `configuration.md` and `cli.md` own them, by source file; a new source file that speaks to a user must be given an owner. |
| `tests/test_docs_references_unit.py` | The superscript cross-references agree with each document's `## References` table: every citation is a row, every row is cited, rows are numbered 1, 2, 3 and point to distinct places, and the table is the last section. |
| `tests/doc_files.py` | Not a test: the documents and public names the six `test_docs_*` files share, and the Python blocks, their shown output and the world they run in, which `scripts/regen_docs.py` shares with the blocks test and the README test. |
| `tests/test_golden_output.py` | The report library's exact tables, written as CSV, byte for byte against the files in `tests/golden/`, and the report read back by a CSV reader into the same columns and values. |
| `tests/test_api_contract.py` | The public surface: every name in `__all__` importable, every public function exported, `__all__` equal to the list written in the test so a new export is a decision, permanent `Status` values and outcome names, and the report's column order. Signatures and defaults are checked against `docs/interfaces.md` by `test_docs_api_unit.py`. |
| `tests/test_tables_unit.py` | `is_null` (true for a missing value pandas reads as truthy, false for any container), and every column of the registry and rules tables. |
| `tests/test_context_unit.py` | `RowContext` as the base type an adopter subclasses. |
| `tests/test_paths_unit.py` | The step both loaders take before they open anything: an existing file resolved, a symlink followed, and each way a path that is not a file is refused -- relative, absolute and a directory -- word for word. |
| `tests/test_interface_cli.py` | The parser's defaults, and what only a subprocess shows: running from another directory, the exit code reaching the shell, results on stdout and an error as one line on stderr. The rest of the entry point is in `test_main_unit.py`, and in the catalogs byte for byte. |
| `tests/test_pathological.py` | A rule file that is not YAML, naming itself; a check that raises, shown as the line in the check's own file -- through a helper, with no message, and wrapped in `functools.partial`. |
| `tests/test_safety.py` | the safe YAML loader refuses `!!python/object`, patterns and comments are never evaluated, loading writes nothing, a catastrophic regex stays bounded, and a rule error quotes the offending value, not the file. |

Long:

| File | Covers |
|---|---|
| `tests/test_e2e_catalogs.py` | Every catalog case through the real entry point, plus the catalog's own rules: each case documents itself, states its level, and the level counts stay above their floors. |
| `tests/test_integration.py` | The shipped rule files driving a whole DataFrame, the split files saying what the single file says, precedence across directories in both orders, and a row's explanation matching its lines of the full report. |
| `tests/test_concurrency.py` | Threads sharing one registry agree with one thread, on rows and on whole frames, and leave the registry unchanged; several processes loading the same file all succeed and leave no bytecode. |
| `tests/test_faults.py` | The filesystem failing underneath: an unreadable rule file stops the whole load, an unreadable check file or one Python cannot compile registers nothing. |
| `tests/test_scaling.py` | The *shape* of the cost: four times the rows or the checks costs under eight times the time, a 100-deep dependency chain does not cost more than a flat registry, a frame with no failures costs the report a fraction of a failing one, and going row by row holds nothing between rows: four times the rows raise the peak by under 2 MB. Every timing here is a ratio with room in it, and the one that compares two small measurements takes the best of five runs after a warm-up, so a busy machine does not fail a run. |
| `tests/test_load.py` | The long suite's one absolute ceiling (5,000 rows validated, reported and summarized), 500 rules × 200 rows, and a guard that the topological sort never runs inside the row loop. |
| `tests/test_packaging.py` | What an adopter gets: the package ships no checks of its own, `py.typed` is there, every module imports on its own, importing registers nothing, a scratch adopter package outside this repository loads its check file and writes a report, and nothing uses a standard library name newer than the declared 3.10 floor. |
| `tests/test_fuzz.py` | Generated input from a fixed seed: 300 rule files written as data and 300 written as YAML text (repeated keys, unquoted booleans, tags, bytes that are not UTF-8), 300 frames, 100 hostile comment payloads. |
| `tests/test_properties.py` | The same invariants explored by Hypothesis, which shrinks a failure to the smallest reproducing case; and, over random graphs, `repeat` flags, copy groupings and per-copy rules, copies under `repeat_key`: a check that does not repeat is called at most once per key and settled on the first copy enabling its chain, a `shared` outcome passes and names an earlier copy that did it, a check is `disabled` exactly where a rule disables it, and when every check repeats, `repeat_key` changes nothing. |

Own gates:

| File | Covers |
|---|---|
| `tests/test_perf.py` | Three timings against this machine's recorded baseline (`validate`, the report, the summary), plus rule resolution over 50 rules. |
| `tests/test_memory.py` | Peak memory for `validate` plus the report on a large frame. |

## The example catalog

`tests/examples/` holds 50 cases at three levels — 19 simple, 16 moderate, 15 complex —
and `tests/failures/` holds 24, each asserting the exact message and exit code a user
sees. Both run through a real entry point in a subprocess — `examples/main.py`,
`examples/run_from_config.py` for the
run-file cases, or a script inside the case where no entry point reaches the feature (a
context builder) — so the documentation cannot drift from the behavior.

Nothing is faked. The entry point, the library, the rule files and the data files are the
real ones; the only normalization is the absolute project root, replaced by `<project>`
so the expected output does not pin the catalog to one machine's path.

The data files come from `scripts/make_example_data.py` and are committed:

| File | Rows | What it is for |
|---|---|---|
| `examples/data/customers.csv` | 49 | One of every problem in a majority of valid rows: blanks, a decimal age, a sentinel 999, an age spelled in words, addresses with no `@` and no dot, reversed dates, a duplicate id, a name holding a comma, a non-ASCII name, an entirely blank row, and a cell a spreadsheet would run as a formula. |
| `examples/data/customers_clean.csv` | 24 | Nothing wrong, so a passing run has something to show. |
| `examples/data/customers_large.csv` | 2,000 | Volume: about one row in six carries a problem. |

Regenerate expected output after an intended change with
`python3 scripts/regen_catalog.py [substring ...]`, then **read the diff** — a blind
regeneration defeats the catalog.

Add a case with `scripts/new_catalog_case.py`, which writes the directory, the `cmd` and
the README, then records the output by running it. A case that carries its own input
files — a rule file, a run file, check files — gets them put in its directory first; the
script accepts a directory that holds no case files yet and refuses one that does. It refuses a command another case
already uses: two cases with one command are one case filed twice, and the duplicate is
invisible in a directory listing because the names differ — three got in that way when the
catalog was rebuilt by hand.

**Paths are rendered through a fixed-length root.** A case like
`rules/rules-table-one-row-per-rule` prints absolute paths in a table whose column
widths are computed *before* `<project>` replaces them, so a clone at a longer path would
produce the same words with different padding and fail for no reason anybody could act
on. `tests/catalog.py` therefore runs every case through a symlink at
`$TMPDIR/prv-catalog-root-<8-digit uid>-<8-hex-digit hash of the clone's path>`, which is
the same length on every machine and distinct per clone, so two clones run at once by
one user do not flip each other's link. A
filesystem that refuses symlinks falls back to the real root, and the one test that
depends on the arrangement skips.

## Mutation testing

Coverage says every line ran; it says nothing about whether the assertion after it would
notice the line being wrong. `mutmut` answers that by changing the code and checking a
test fails.

```sh
./tests/run-tests.sh mutation   # clean run + score against the 97% floor (the gate)
python -c "import pandas; import sys; sys.argv=['mutmut','run']; from mutmut.__main__ import cli; cli()"
python scripts/mutation_score.py --floor 97   # score the results a run left
mutmut results      # survived / killed, per mutant
mutmut show <name>  # the diff for one survivor
```

**The floor is 97%, set 2026-10-03 against a measured 97.8%** (it was 94% from
2026-09-26, against 95.7%). The score is detected over total: killed, caught by the type
check, or timed out. The 97.8% of `cc22f4b` is 0.8 points, about 11 of its 1,479
mutants, above the floor -- room for a change that adds a few untested lines, not for a
module losing its tests. None of today's 20 survivors can be killed (below), so new code
keeps the score only with nearly all of its own mutants killed. Raise the floor when the
score rises and stays there; lower it only with the survivors read and recorded below,
never to make a run pass. The coverage floor follows the same rule: 99%, against 99.5%.

**That incantation is not decoration.** Plain `mutmut run` fails during stats collection
here: mutmut runs pytest in its own process, and importing pandas inside that run trips
`RuntimeError: context has already been set` from `multiprocessing`. Importing pandas
before mutmut starts settles the context first. Two other things about the configuration
in `[tool.mutmut]`:

- `also_copy = ["examples/", "scripts/"]` — mutmut runs the suite against a copy of the
  tree under `mutants/`; the entry point and example check files the tests load live in
  `examples/`, and one test regenerates the example data from `scripts/` and compares.
- `pytest_add_cli_args_test_selection` excludes eighteen test files **from mutmut's runs
  only** — they still run in every normal suite. Three of them shell out to a subprocess,
  which never loads mutmut's instrumentation, so a mutant would always look like it
  survived; eight assert on the module's own structure or read the documents
  (`test_api_contract.py`, `test_readme.py` and the six `test_docs_*` files), neither of
  which survives being copied into `mutants/`; the remaining seven (load, scaling, perf, memory, concurrency, property, fuzz) are excluded for cost,
  since mutmut runs the whole selection once per mutant and each of those is covered by
  a faster test of the same behavior. The list, with a reason beside each entry, is in
  `pyproject.toml`.

**`mutants/` is the one artifact in the project root.** Every other generated file lives
under `.build/` — the coverage data, the pytest, ruff and mypy caches, the hypothesis database,
the profile and the performance baseline. `mutmut` hardcodes `Path('mutants')` relative to
the working directory and takes no setting for it, so that tree appears beside the project
and is gitignored. It is transient: `rm -rf mutants .mutmut-cache` when a run is finished,
which is also what a stale tree needs before the next one.

**A targeted re-run discards every other result.** `mutmut run <mutant-name>` re-runs that
one mutant and drops the stored results for all the others, so the score it was being
measured against is gone and the only way back to a number is a full run. Check individual
mutants freely while closing a gap — that is the fastest way to confirm a new test kills
the thing it was written for — but expect to re-run the whole set afterwards, and do not
read `mutmut results` in between as the suite's score.

Surviving mutants are a to-do list, not a failure: each one is a change to the code that
no test noticed.

Measured on 2026-10-09, on the tree after the review fixes of that day: **1,478 mutants,
1,458 killed, 20 survived, 0 timeouts — 98.6%**, in about four minutes. That is a record
of one tree, not the current score: re-run before quoting a number, and update this
paragraph with what comes back. Earlier scores, oldest first: 89.2% (2026-09-10), 89.5%
(09-11), 94.6% (09-25), 95.7% (09-26), 96.6% (09-28), 97.1% (10-02), 96.9% and 97.8%
(10-03), 97.9% (10-09, before the fixes), 98.5% (10-09, before the `Verdict.status`
test). Each run's reading of its survivors is in `git log -p docs/testing.md`.

Survivors by module: `registry` 8, `engine` 6, `paths` 4, `views` 2. All 20 were read on
2026-10-09. They fall into three classes:

- **Default arguments (2) — unkillable here.** mutmut's trampoline keeps the
  *original* function's defaults and forwards the caller's arguments, so a
  mutated default in the mutant body is never evaluated. The two: `deep` of
  `construct_mapping` (1), `_mode` of `_NoBytecodeLoader.set_data` (1).
- **Equivalent (15).** A change Python, pandas or PyYAML reads the same way: `False`
  swapped for `None` where the value is only read for truth — `passed[code]` (3),
  `required=` (1), `itertuples(index=)` (1); the YAML loader passing `deep` as `None` or
  not at all (2); `itertuples` yielding namedtuples instead of plain tuples, read by
  position either way (1); the letter case of `"utf-8"` (1); `getattr(fn, "__module__")`
  without its fallback, on functions that always have one (1); `clear_registry` leaving
  `_TOPO_ORDER` as `""`, which orders the empty registry to nothing just as `None` does
  and is reset by the next registration (1); `spec_from_file_location` without the
  location or the loader (4), since the module is run by `loader.exec_module`, which
  reads the path the loader holds.
- **Python-version only (3).** The `add_note` stand-in for Python 3.10; the suite runs
  on 3.12, which has the method.

Writing the message tests found a defect the suite had never noticed:
`register_check(depends_on="AGE_PRESENT")` did `list(depends_on or [])` before the guard
could see it, so a mistyped bare string became `['A', 'G', 'E', ...]` and the failure
arrived much later as a missing prerequisite called `'A'`. Fixed, with the message test as
its regression test.

## Performance and profiling

`./tests/run-tests.sh perf` compares four timings against `.build/perf-baseline.json`,
which is
**gitignored**: a baseline from another machine gates nothing. The first run on a clone
records it and says so; later runs fail when a median moves past the machine's own
measured noise (twice the observed spread, floored at 35% and capped at 150%).

Measured on 2026-09-21, Python 3.12.14, pandas 3.0.5,
Linux 6.12 x86_64, 4,000-row
frame, after the example date checks stopped calling the scalar `pandas.to_datetime`
(on 2026-09-10 `validate/4000` was 6.250s and `validate_row/4000`, a gate since removed with that function, 6.174s — 87% of it
date parsing in example code, which left the gate nearly blind to the engine):

| Measurement | Median | Spread |
|---|---|---|
| `validate/4000` | 1.340s | 16% |
| `build_report/4000` | 0.070s | 98% |
| `summarize_outcomes/4000` | 0.024s | 19% |
| `validate/1000-rows-50-rules` | 0.501s | 35% |

`./tests/run-tests.sh long` and `all` end by running `scripts/profile_examples.py`, which
drives the same runs the catalog drives, in this process, and prints this project's own
functions by cumulative time. It is a description, not a gate — the assertions live in
`test_perf.py`. **It cannot see the catalog's own subprocesses:** interpreter start-up,
imports and argument parsing per case are outside the measurement.

Where the time goes (2026-09-26, 2.0s in all): `validate` 88% of the total and
its per-row evaluation (then `explain_row`, now `engine._explain`) 68%, and inside it the example check files' own functions —
`row_not_all_null` alone is 24%, `dates_present` 5%. Until 2026-09-21 the date checks
called the scalar `pandas.to_datetime` per cell, which costs about 300 times
`pandas.Timestamp` on the same string and was 87% of a run; the example now uses
`pandas.Timestamp`.

## Golden files

`tests/golden/` holds the exact tables the report library builds, written as CSV — one
view per file, produced from the fixed frame in `tests/golden_fixture.py` and compared
byte for byte.
They are tighter than the catalog: the catalog pins everything an entry point prints,
while these isolate one view each, so a diff points straight at what changed.

The golden files hold `\n` line endings, so a `\r\n` from `csv` creeping back into the
output fails the comparison.

Regenerate with `python3 scripts/regen_golden.py` and read the diff, exactly as with the
catalog.
