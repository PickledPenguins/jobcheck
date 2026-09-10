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
| `./run-tests.sh fast` | 652 tests: unit, smoke, interface, contract, documentation, regression, cheap pathological, safety, every error message — then mypy | 28s |
| `./run-tests.sh long` | 250 tests: integration, load, concurrency, faults, scaling, packaging, fuzz, property, end-to-end catalogs — then the example profile | 265s |
| `./run-tests.sh all` | 902 tests, then mypy and the profile | 286s |
| `./run-tests.sh cov` | fast suite under coverage, gated at 95% lines and branches | 40s |
| `./run-tests.sh perf` | timing against this machine's baseline; its own gate | 85s |
| `./run-tests.sh memory` | peak-memory ceilings under tracemalloc; its own gate | 40s |
| `./run-tests.sh profile` | the example profile alone | 12s |
| `./run-tests.sh types` | mypy alone | 8s |

Extra arguments pass through to pytest: `./run-tests.sh fast -k dependency`,
`./run-tests.sh long tests/test_load.py`. Each mode exits non-zero on any failure and
prints one summary line. `PYTHON=/path/to/python` selects the interpreter.

Markers are `fast`, `long`, `perf` and `memory`; `--strict-markers` is on, so a typo
fails rather than silently selecting nothing.

**The long suite refuses to run without `hypothesis`.** A skipped property suite reads
as a pass, and it is the one category that finds cases nobody wrote down, so its absence
fails the gate with a message naming the interpreter rather than printing `1 skipped`.

There is no CI. The pre-commit hook and the release gates below are what run these.

## Gates

- **Pre-commit** — `./run-tests.sh fast`, installed by `./scripts/install-hooks.sh` into
  `.git/hooks/pre-commit`. Bypass with git's own `--no-verify`; there is no custom flag.
  Verified to block: breaking `format_table` and committing stops at the hook.
- **Pre-release** — `./run-tests.sh all`, `./run-tests.sh cov`, `./run-tests.sh memory`
  and `./run-tests.sh perf`. Coverage below 95% fails through
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
| `tests/test_registry_unit.py` | Registration and its duplicate guard, suite inference, suite loading and its no-ops, `clear_registry`, dependency validation, cycle detection, topological order and its cache. |
| `tests/test_load_files_unit.py` | `load_test_files`: files named by path, repeats and reloads skipped, unique module names, the base suite, prerequisites across files in one call, what a broken file leaves behind, and that no `__pycache__` appears beside the caller's file. |
| `tests/test_run_unit.py` | The whole-frame entry point: trace shape and positions, root causes, `RunStats`, `ValidationRun`'s views and `from_records`, `iter_traces`, progress reporting, and `on_error` reaching `explain_row`. |
| `tests/test_overrides_unit.py` | Every rule-file rejection (19 parametrised cases asserting the exact message), the three loaders and their ordering, duplicate names, matching semantics, last-rule-wins precedence. |
| `tests/test_results_unit.py` | The status vocabulary, registering project statuses, `TestResult` truthiness and validation, and normalising whatever a test returned. |
| `tests/test_validate_row_unit.py` | The per-row algorithm: outcomes and their reasons, enabled state, dependency skipping (failed, disabled, errored, transitive), signature adaptation, purity, `check_rule_columns`, root cause, layers, and the shipped tests at their boundaries. |
| `tests/test_groups_unit.py` | `test_group` defaults, prerequisites unioned with a test's own, suite and default-state overrides, and the registration guards. |
| `tests/test_report_unit.py` | Collection, the failure table and its columns, row keys, `include_skipped`/`include_passed`, table and CSV rendering, writing files, explanations and summaries. |
| `tests/test_main_unit.py` | Both entry points driven in this process: every flag, every early exit, the report and explain paths, and each error message with its exit code. |
| `tests/test_shipped_examples_unit.py` | `examples/` as a delivered artefact: every rule file loads alone and together, every rule names a real code and a column the data has, the three data files are the size and shape the documentation claims, and the generator still reproduces them byte for byte. |
| `tests/test_differential_jobchain.py` | What jobchain's own suite asserted of the pre-rename engine, restated against this one — layering, root cause, cross-row context, crashes, rule-driven disabling. |
| `tests/test_error_messages_unit.py` | Every message the library raises, compared word for word rather than by keyword: registration, loading, per-row evaluation, reporting and the whole-frame entry point. |
| `tests/test_perf_baseline_unit.py` | The baseline arithmetic itself: recording, comparing, the tolerance floor and cap, and discarding a baseline from another machine. |
| `tests/test_readme.py` | The README executed, plus the prose claims and the two-way CLI documentation contract: every flag has a section in `docs/cli.md`, and every documented flag exists. |
| `tests/test_golden_output.py` | The report library's exact output, byte for byte, against the files in `tests/golden/`. |
| `tests/test_api_contract.py` | The public surface: every name in `__all__` importable, every public function exported, permanent `Status` values and outcome names, stable report and registry columns, and the default arguments of every exported function. |
| `tests/test_tables_unit.py` | `format_table` rendering, wrapping and empty frames; every column of the three registry tables. |
| `tests/test_context_unit.py` | `RowContext` defaults and `build_context`. |
| `tests/test_smoke.py` | Both entry points start, exit 0, and produce their main output. |
| `tests/test_interface_cli.py` | The CLI contract as a user meets it, in subprocesses: flag flattening, defaults, `-v` counting, exit codes 0/1/2, stdout vs stderr routing, and the data-file flags. |
| `tests/test_pathological.py` | Malformed YAML, unicode, 1000 rules, empty and wide rows, duplicate column labels, a 200-deep dependency chain, a check that raises. |
| `tests/test_safety.py` | `safe_load` refuses `!!python/object`, patterns are never evaluated, loading writes nothing, validation does not mutate the frame, suite names cannot import unrelated modules, directory loading does not recurse, a catastrophic regex stays bounded, and CSV reports neutralise cells a spreadsheet would run as a formula. |

Long:

| File | Covers |
|---|---|
| `tests/test_e2e_catalogs.py` | Every catalog case through the real entry point, plus the catalog's own rules: each case documents itself, states its level, and the level counts stay above their floors. |
| `tests/test_integration.py` | Real rule files on disk driving a whole DataFrame, all three loaders, precedence across directories, CSV export, a suite package created at runtime, a written report re-read as a spreadsheet reader would. |
| `tests/test_concurrency.py` | Threads sharing one registry agree with one thread; separate processes do not share one; several processes loading the same file all succeed and leave no bytecode; a crashing process does not affect its neighbour. |
| `tests/test_faults.py` | The filesystem failing underneath: unreadable rule and test files, a directory where a file was expected, symlinks pointing nowhere, NUL bytes, a full disk mid-write, and a read-only output directory. |
| `tests/test_scaling.py` | The *shape* of the cost: four times the rows or the tests costs under eight times the time, a 100-deep dependency chain does not cost more than a flat registry, and streaming holds a quarter of what collecting holds. |
| `tests/test_load.py` | 20,000 rows within a time ceiling, correctness at volume, 500 tests × 200 rows, 500 rules × 200 rows, and a guard that the topological sort never runs inside the row loop. |
| `tests/test_packaging.py` | What an adopter gets: the package ships no tests of its own, `py.typed` is there, every module imports on its own, and a scratch adopter package outside this repository loads its suite and writes a report. |
| `tests/test_fuzz.py` | Generated input from a fixed seed: 300 rule files, 300 frames, 100 hostile comment payloads. |
| `tests/test_properties.py` | The same invariants explored by Hypothesis, which shrinks a failure to the smallest reproducing case. |

Own gates:

| File | Covers |
|---|---|
| `tests/test_perf.py` | Five timings against this machine's recorded baseline, plus rule resolution over 50 rules. |
| `tests/test_memory.py` | Peak memory for per-row validation, the report path, and the streaming path. |

## The example catalog

`tests/examples/` holds 48 cases at three levels — 20 simple, 18 moderate, 10 complex —
and `tests/failures/` holds 18, each asserting the exact message and exit code a user
sees. Both run through the real entry point in a subprocess, so the documentation cannot
drift from the behaviour.

Nothing is faked. The entry point, the library, the rule files and the data files are the
real ones; the only normalisation is the absolute project root, replaced by `<project>`
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

**Known fragility.** `tests/examples/verbosity/source-files-and-by-rule-table` prints
absolute paths in a table whose column widths were computed before `<project>` was
substituted, so the case only passes on a path of the same length as the one that
generated it. Making it portable means rendering through a fixed-length root, which is a
change to `tests/catalog.py` rather than to the case.

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

- `also_copy = ["examples/"]` — mutmut runs the suite against a copy of the tree under
  `mutants/`, and the entry points and example suites the tests load live in `examples/`.
- `pytest_add_cli_args_test_selection` excludes six test files **from mutmut's runs
  only** — they still run in every normal suite. Four of them shell out to a subprocess,
  which never loads mutmut's instrumentation, so a mutant would always look like it
  survived; the other two assert on the module's own structure and on the doc tree,
  neither of which survives being copied into `mutants/`.

Surviving mutants are a to-do list, not a failure: each one is a change to the code that
no test noticed.

Measured on 2026-09-10, after the tests written against the first run:
**1,602 mutants, 1,450 killed, 152 survived, 0 timeouts — 90.5%.**

The first run scored 87%, and every survivor was read. What they were:

- **Real gaps, now killed.** Every survivor in `run.py` (`on_error` never reaching
  `explain_row`, `progress` and `progress_every` dropped, `seconds` computed as
  `perf_counter() + started`, the overrides list not carried onto the run), four in
  `load_test_files` (the module missing from `sys.modules`, the bytecode flag not
  restored exactly, a file registering no tests never evicted), `collect_outcomes`
  ignoring its `context_builder`, `format_table` breaking long words and hyphens,
  `row_explanation` losing its columns on an empty frame, and `cell_text` treating a
  null cell as text.
- **21 default-argument mutants: unkillable here, and not a gap.** mutmut's trampoline
  keeps the *original* function's defaults and forwards the caller's arguments, so a
  mutated default in the mutant body is never evaluated. Verified by hand on
  `collect_outcomes(on_error="XXrecordXX")`, which behaves exactly like the original.
- **Environment-equivalent mutants.** `write_report`'s `encoding="utf-8"` and
  `newline=""` can be dropped without effect on a UTF-8 Linux box: the platform default
  is the same. They would matter on Windows, and the tests that pin them
  (`test_a_written_report_is_utf_8`, `..._uses_unix_line_endings`) exist for that reason
  even though mutmut cannot show it here.
- **Equivalent mutants.** `break_long_words=None` for `False`, `wrap=wrap` dropped where
  the callee's default is the same 48, `itertuples(index=None)` for `index=False`.
- **46 string-wording mutants in the print functions.** Those outputs are pinned by the
  example catalog and the golden files, neither of which mutmut can run -- the catalog
  shells out to a subprocess that never loads the instrumentation. The library's *error*
  messages are a different matter and are pinned word for word by
  `tests/test_error_messages_unit.py`.

Writing the message tests found a defect the suite had never noticed:
`register_test(depends_on="AGE_PRESENT")` did `list(depends_on or [])` before the guard
could see it, so a mistyped bare string became `['A', 'G', 'E', ...]` and the failure
arrived much later as a missing prerequisite called `'A'`. Fixed, with the message test as
its regression test.

## Performance and profiling

`./run-tests.sh perf` compares five timings against `.perf-baseline.json`, which is
**gitignored**: a baseline from another machine gates nothing. The first run on a clone
records it and says so; later runs fail when a median moves past the machine's own
measured noise (twice the observed spread, floored at 35% and capped at 150%).

Measured on 2026-09-10, Python 3.12.14, Linux 6.12 x86_64, 4,000-row frame:

| Measurement | Median | Spread |
|---|---|---|
| `collect_outcomes/4000` | 6.118s | 5% |
| `iter_traces/4000` | 5.941s | 2% |
| `build_report/4000` | 0.064s | 77% |
| `render_report/4000` | 0.053s | 4% |
| `summarise_outcomes/4000` | 0.021s | 3% |
| `collect_outcomes/1000-rows-50-rules` | 0.393s | 27% |

`./run-tests.sh long` and `all` end by running `scripts/profile_examples.py`, which
drives the same runs the catalog drives, in this process, and prints this project's own
functions by cumulative time. It is a description, not a gate — the assertions live in
`test_perf.py`. **It cannot see the catalog's own subprocesses:** interpreter start-up,
imports and argument parsing per case are outside the measurement.

Where the time goes today: `explain_row` at 85% of the total, and inside it the example
suites' own test functions — `dates_present` and `dates_in_order` together are about 40%,
because both parse dates with `pandas.to_datetime` per row.

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
