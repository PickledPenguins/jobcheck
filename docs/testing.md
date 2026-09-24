# Testing

Back to the [README](../README.md).

Tests run under pytest, split by marker into two suites and three separate gates.
`pytest` and `coverage` are development-only: nothing here is needed to *run* the
framework.

```sh
pip install -e ".[dev]"
./scripts/install-hooks.sh          # once per clone: installs the pre-commit gate
```

## Commands

| Command | Runs | Time |
|---|---|---|
| `./tests/run-tests.sh fast` | 723 tests: unit, smoke, interface, contract, documentation, regression, cheap pathological, safety, every error message — then mypy | 18s |
| `./tests/run-tests.sh long` | 253 tests: integration, load, concurrency, faults, scaling, packaging, fuzz, property, end-to-end catalogs — then the example profile | 100s |
| `./tests/run-tests.sh all` | 976 tests, then mypy and the profile | 120s |
| `./tests/run-tests.sh cov` | fast suite under coverage, gated at 95% lines and branches (it runs at 100%) | 23s |
| `./tests/run-tests.sh perf` | timing against this machine's baseline; its own gate | 21s |
| `./tests/run-tests.sh memory` | peak-memory ceilings under tracemalloc; its own gate | 13s |
| `./tests/run-tests.sh profile` | the example profile alone | 3s |
| `./tests/run-tests.sh types` | mypy alone | 8s |

Extra arguments pass through to pytest: `./tests/run-tests.sh fast -k dependency`,
`./tests/run-tests.sh long tests/test_load.py`. Each mode exits non-zero on any failure and
prints one summary line. `PYTHON=/path/to/python` selects the interpreter.

Markers are `fast`, `long`, `perf` and `memory`; `--strict-markers` is on, so a typo
fails rather than silently selecting nothing.

**The long suite refuses to run without `hypothesis`.** A skipped property suite reads
as a pass, and it is the one category that finds cases nobody wrote down, so its absence
fails the gate with a message naming the interpreter rather than printing `1 skipped`.

There is no CI. The pre-commit hook and the release gates below are what run these.

## Gates

- **Pre-commit** — `./tests/run-tests.sh fast`, installed by `./scripts/install-hooks.sh` into
  `.git/hooks/pre-commit`. Bypass with git's own `--no-verify`; there is no custom flag.
  Verified to block: breaking `format_table` and committing stops at the hook.
- **Pre-release** — `./tests/run-tests.sh all`, `./tests/run-tests.sh cov`, `./tests/run-tests.sh memory`
  and `./tests/run-tests.sh perf`. Coverage below 95% fails through
  `coverage report --fail-under`; a memory ceiling or a timing baseline exceeded fails
  its own run.

Each gate has been checked by breaking the thing it guards and watching it fail — the
coverage floor by deleting a test, the perf gate by lowering a stored baseline (a 4x
regression reported `6.15s against a limit of 2.06s`), the memory ceiling by holding the
outcomes the streaming path is supposed to release.

## What each file covers

Fast:

| File | Covers |
|---|---|
| `tests/test_registry_unit.py` | Registration and its duplicate guard, `clear_registry`, dependency validation, cycle detection, topological order and its cache. |
| `tests/test_load_files_unit.py` | `load_checks`: files named by path, repeats and reloads skipped, unique module names, prerequisites across files in one call, what a broken file leaves behind, and that no `__pycache__` appears beside the caller's file. Bundles -- a check file that loads check files -- have a section of their own: deferred validation, whose checks a failure drops, and the guard that stops a bundle naming itself from recursing. |
| `tests/test_validate_unit.py` | The whole-frame entry point: one list of outcomes per row **in its own position**, the checks that did not run kept, rules and the context builder passed through, and both `on_error` modes. |
| `tests/test_rules_unit.py` | Every rule-file rejection (19 parametrized cases asserting the exact message), the loader and its ordering, duplicate names, matching semantics, last-rule-wins precedence. |
| `tests/test_results_unit.py` | The fixed status vocabulary, `Verdict` truthiness and validation, and normalizing whatever a check returned. |
| `tests/test_validate_row_unit.py` | The per-row algorithm: outcomes and their reasons, enabled state, dependency skipping (failed, disabled, errored, transitive), signature adaptation, purity, `warn_missing_rule_columns`, root cause, layers, and the shipped checks at their boundaries. |
| `tests/test_report_unit.py` | Collection, the failure table and its columns, row keys, `include` levels, table and CSV rendering, writing files, explanations and summaries. |
| `tests/test_main_unit.py` | The entry point driven in this process: every flag, every early exit, the report and explain paths, and each error message with its exit code. |
| `tests/test_bundle_main_unit.py` | The bundle entry point in this process, and the shipped bundle it loads: the four members and their order, the printed sections, and the argument that names another bundle. |
| `tests/test_shipped_examples_unit.py` | `examples/` as a delivered artefact: every rule file loads alone and together, every rule names a real code and a column the data has, the three data files are the size and shape the documentation claims, and the generator still reproduces them byte for byte. |
| `tests/test_differential_jobchain.py` | What jobchain's own suite asserted of the pre-rename engine, restated against this one — layering, root cause, cross-row context, crashes, rule-driven disabling. |
| `tests/test_error_messages_unit.py` | Every message the library raises, compared word for word rather than by keyword: registration, loading, per-row evaluation, reporting and the whole-frame entry point. |
| `tests/test_perf_baseline_unit.py` | The baseline arithmetic itself: recording, comparing, the tolerance floor and cap, and discarding a baseline from another machine. |
| `tests/test_readme.py` | The README executed, plus the prose claims and the two-way CLI documentation contract: every flag has a section in `docs/cli.md`, and every documented flag exists. |
| `tests/test_docs_unit.py` | The rest of `docs/`, both directions: every code block runs, in a working directory holding the demo frame, outcomes, rules and the check files the blocks name; every call shown binds against the real signature and names something this package, pandas or the builtins provides; no document says a bare bool or status return is converted; every exported name appears in `interfaces.md` and nothing documented there is gone, every check code a document shows is one that exists, every exit code the entry point can return has a row in `docs/cli.md` and no row describes one it cannot, the README stays an index and links every document, no internal link or anchor is dead, the rule keys, statuses and outcome names are documented where they belong, and the suite sizes and catalog case counts stated in this document and in the README are the ones a collection and the case directories actually give. It also gates line width: no Python line in `src/`, `examples/` or `scripts/` exceeds the 100 characters `contributing.md` claims, and that document names the three directories the gate covers. |
| `tests/test_golden_output.py` | The report library's exact output, byte for byte, against the files in `tests/golden/`. |
| `tests/test_api_contract.py` | The public surface: every name in `__all__` importable, every public function exported, permanent `Status` values and outcome names, stable report and registry columns, and the default arguments of every exported function. |
| `tests/test_tables_unit.py` | `format_table` rendering, wrapping and empty frames; every column of the three registry tables. |
| `tests/test_context_unit.py` | `RowContext` as the base type an adopter subclasses. |
| `tests/test_paths_unit.py` | The step both loaders take before they open anything: an existing file resolved, a symlink followed, and each way a path that is not a file is refused -- relative, absolute and a directory -- word for word. |
| `tests/test_smoke.py` | The entry point starts, exits 0, and produces its main output. |
| `tests/test_interface_cli.py` | The CLI contract as a user meets it, in subprocesses: defaults, exit codes 0/1/2, stdout vs stderr routing, and the data-file flag. |
| `tests/test_pathological.py` | Malformed YAML, unicode, 1000 rules, empty and wide rows, duplicate column labels, a 200-deep dependency chain, a check that raises. |
| `tests/test_safety.py` | `safe_load` refuses `!!python/object`, patterns are never evaluated, loading writes nothing, validation does not mutate the frame, a check file name is a path and never a module name, a catastrophic regex stays bounded, and CSV reports neutralize cells a spreadsheet would run as a formula. |

Long:

| File | Covers |
|---|---|
| `tests/test_e2e_catalogs.py` | Every catalog case through the real entry point, plus the catalog's own rules: each case documents itself, states its level, and the level counts stay above their floors. |
| `tests/test_integration.py` | Real rule files on disk driving a whole DataFrame, precedence across directories, CSV export, a check file written at runtime and loaded by path, a written report re-read as a spreadsheet reader would. |
| `tests/test_concurrency.py` | Threads sharing one registry agree with one thread; separate processes do not share one; several processes loading the same file all succeed and leave no bytecode; a crashing process does not affect its neighbor. |
| `tests/test_faults.py` | The filesystem failing underneath: unreadable rule and check files, a directory where a file was expected, symlinks pointing nowhere, NUL bytes, a full disk mid-write, and a read-only output directory. |
| `tests/test_scaling.py` | The *shape* of the cost: four times the rows or the checks costs under eight times the time, a 100-deep dependency chain does not cost more than a flat registry, a frame with no failures costs the report a fraction of a failing one, and going row by row holds a quarter of what collecting holds. Every timing here is a ratio with room in it, and the one that compares two small measurements takes the best of five runs after a warm-up, so a busy machine does not fail a run. |
| `tests/test_load.py` | 20,000 rows within a time ceiling, correctness at volume, 500 checks × 200 rows, 500 rules × 200 rows, and a guard that the topological sort never runs inside the row loop. |
| `tests/test_packaging.py` | What an adopter gets: the package ships no tests of its own, `py.typed` is there, every module imports on its own, and a scratch adopter package outside this repository loads its check file and writes a report. |
| `tests/test_fuzz.py` | Generated input from a fixed seed: 300 rule files, 300 frames, 100 hostile comment payloads. |
| `tests/test_properties.py` | The same invariants explored by Hypothesis, which shrinks a failure to the smallest reproducing case. |

Own gates:

| File | Covers |
|---|---|
| `tests/test_perf.py` | Five timings against this machine's recorded baseline, plus rule resolution over 50 rules. |
| `tests/test_memory.py` | Peak memory for per-row validation, the report path, and the streaming path. |

## The example catalog

`tests/examples/` holds 45 cases at three levels — 19 simple, 16 moderate, 10 complex —
and `tests/failures/` holds 22, each asserting the exact message and exit code a user
sees. Both run through a real entry point in a subprocess — `examples/main.py`, or
`examples/bundle_main.py` for the bundle cases — so the documentation cannot drift from
the behavior.

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
the README, then records the output by running it. It refuses a command another case
already uses: two cases with one command are one case filed twice, and the duplicate is
invisible in a directory listing because the names differ — three got in that way when the
catalog was rebuilt by hand.

**Paths are rendered through a fixed-length root.** A case like
`verbosity/source-files-and-by-rule-table` prints absolute paths in a table whose column
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
python -c "import pandas; import sys; sys.argv=['mutmut','run']; from mutmut.__main__ import cli; cli()"
mutmut results      # survived / killed, per mutant
mutmut show <name>  # the diff for one survivor
```

**That incantation is not decoration.** Plain `mutmut run` fails during stats collection
here: mutmut runs pytest in its own process, and importing pandas inside that run trips
`RuntimeError: context has already been set` from `multiprocessing`. Importing pandas
before mutmut starts settles the context first. Two other things about the configuration
in `[tool.mutmut]`:

- `also_copy = ["examples/", "scripts/"]` — mutmut runs the suite against a copy of the
  tree under `mutants/`; the entry point and example check files the tests load live in
  `examples/`, and one test regenerates the example data from `scripts/` and compares.
- `pytest_add_cli_args_test_selection` excludes fourteen test files **from mutmut's runs
  only** — they still run in every normal suite. Four of them shell out to a subprocess,
  which never loads mutmut's instrumentation, so a mutant would always look like it
  survived; three assert on the module's own structure and on the doc tree, neither of
  which survives being copied into `mutants/`; the remaining seven (load, scaling, perf,
  memory, concurrency, property, fuzz) are excluded for cost, since mutmut runs the
  whole selection once per mutant and each of those is covered by a faster test of the
  same behavior. The list, with a reason beside each entry, is in `pyproject.toml`.

**`mutants/` is the one artifact in the project root.** Every other generated file lives
under `.build/` — the coverage data, the pytest and mypy caches, the hypothesis database,
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

Measured on 2026-09-21 on a tree cleaned first (`rm -rf mutants .mutmut-cache`), at
commit `b648bcf`: **1,304 mutants, 1,175 killed, 129 survived, 0 timeouts — 90.1%.**
The run takes about three and a half minutes at ~6 mutations/second.

That is a record of one commit, not the current score. Re-run before quoting a number,
and update this section with what comes back — the survivor counts by module below are
from the same commit.

Survivors by module: `report` 52, `registry_tables` 30, `engine` 20, `registry` 15,
`rules` 10, `tables` 2. The 47 outside the two print modules were read one by one: 7 are
default-argument mutants, 9 unreachable, 14 equivalent (the groups below), and 17 are
assertions the suite does not make — the second sentence of the bare-string-path
message in both loaders and the tail of `validate`'s non-DataFrame error, pinned by
substring rather than word for word; the separator between two unknown rule keys and
the rule-name prefix on match-block errors, pinned only through the failure catalog's
subprocess; and the
order cache after a check file fails part-way, where no test validates a row afterward.
The 82 in `report` and `registry_tables` are print wording. Each is listed with its
fix in the review report of the same date.

The earlier runs, for the shape of what a survivor tends to be. The 2026-09-11 run at
`9fe2207` scored 89.5%; its first pass scored 87.9%, and 20 of the survivors were the new
`add_columns` selection on the registry tables, where no test asked a table for
`source_file` and read it back, and the report's "(none available)" message for a
frame with nothing left to offer. Both are covered now. The four extra survivors in `rules` are the
wording of the new `message` and bare-string-path errors — the same gap the 2026-09-21
run still lists.

The 2026-09-10 run scored 89.2% on its first pass, and the difference then was
nine mutants that were real gaps, all in code the simplification had just
rewritten. What they were:

- **`register_check`, four.** The duplicate-code message names the *module* as
  well as the function, and only a check defined by `exec`, which has no module, was
  under test; `depends_on=[""]` was accepted, an empty code being a typo rather
  than a check with no name; and the required-keyword-argument message lists two
  arguments comma-separated, which one argument cannot show.
- **`explain_row`, four.** An `errored` outcome carries a layer and the check's
  message as well as its detail, and nothing asserted either. The layer is what
  decides which code a row reports as its root cause, so a check that raised at
  the wrong layer changes the answer rather than the wording.

The other four groups, which no assertion can reach:

- **Default-argument mutants — unkillable here.** mutmut's trampoline keeps the
  *original* function's defaults and forwards the caller's arguments, so a
  mutated default in the mutant body is never evaluated. Verified by hand on
  `validate(on_error="XXrecordXX")`, which behaves exactly like the original.
- **Unreachable branches.** `state.get(check.code, <default>)` in `explain_row`
  cannot miss: `resolve_enabled_state` builds an entry for every registered check.
  `passed.get(code, False)` cannot miss either, because the topological order
  evaluates prerequisites first and `validate_registry` rejects dangling ones.
- **Equivalent mutants.** `False` swapped for `None` where the value is only ever
  read through `not`; `write_report`'s `encoding="utf-8"` and `newline=""`, which
  are the platform defaults on a UTF-8 Linux box — they matter on Windows, and
  the tests that pin them (`test_a_written_report_is_utf_8`,
  `..._uses_unix_line_endings`) exist for that reason even though mutmut cannot
  show it here.
- **Print-function wording, the largest group.** `registry_tables` is entirely
  print functions, and most of `report`'s survivors are the same. Those outputs
  are pinned byte for byte by the example catalog and the golden files; the
  catalog shells out to a subprocess that never loads mutmut's instrumentation,
  so mutmut cannot run the thing that would kill them. The library's *error*
  messages are a different matter and are pinned word for word by
  `tests/test_error_messages_unit.py`.

Writing the message tests found a defect the suite had never noticed:
`register_check(depends_on="AGE_PRESENT")` did `list(depends_on or [])` before the guard
could see it, so a mistyped bare string became `['A', 'G', 'E', ...]` and the failure
arrived much later as a missing prerequisite called `'A'`. Fixed, with the message test as
its regression test.

## Performance and profiling

`./tests/run-tests.sh perf` compares five timings against `.build/perf-baseline.json`,
which is
**gitignored**: a baseline from another machine gates nothing. The first run on a clone
records it and says so; later runs fail when a median moves past the machine's own
measured noise (twice the observed spread, floored at 35% and capped at 150%).

Measured on 2026-09-21, Python 3.12.14, pandas 3.0.5, Linux 6.12 x86_64, 4,000-row
frame, after the example date checks stopped calling the scalar `pandas.to_datetime`
(on 2026-09-10 `validate/4000` was 6.250s and `validate_row/4000` 6.174s — 87% of it
date parsing in example code, which left the gate nearly blind to the engine):

| Measurement | Median | Spread |
|---|---|---|
| `validate/4000` | 1.340s | 16% |
| `validate_row/4000` | 1.245s | 20% |
| `build_report/4000` | 0.070s | 98% |
| `render_report/4000` | 0.061s | 37% |
| `summarize_outcomes/4000` | 0.024s | 19% |
| `validate/1000-rows-50-rules` | 0.501s | 35% |

`./tests/run-tests.sh long` and `all` end by running `scripts/profile_examples.py`, which
drives the same runs the catalog drives, in this process, and prints this project's own
functions by cumulative time. It is a description, not a gate — the assertions live in
`test_perf.py`. **It cannot see the catalog's own subprocesses:** interpreter start-up,
imports and argument parsing per case are outside the measurement.

Where the time goes today (2026-09-21): `explain_row` at 63% of the total, and inside it
the example check files' own functions — `row_not_all_null` alone is 23%, the four date
parses per row 8%. Until 2026-09-21 the date checks called the scalar
`pandas.to_datetime` per cell, which costs about 300 times `pandas.Timestamp` on the same
string and was 87% of a run; the example now uses `pandas.Timestamp`.

## Golden files

`tests/golden/` holds the exact text the report library produces — one view per file,
produced from the fixed frame in `tests/golden_fixture.py` and compared byte for byte.
They are tighter than the catalog: the catalog pins everything an entry point prints,
while these isolate one view each, so a diff points straight at what changed.

`test_a_written_file_is_byte_for_byte_the_golden_csv` compares the bytes on disk, not
just the string, which is what pins the encoding and keeps `csv`'s `\r\n` from creeping
back into written reports.

Regenerate with `python3 scripts/regen_golden.py` and read the diff, exactly as with the
catalog.
