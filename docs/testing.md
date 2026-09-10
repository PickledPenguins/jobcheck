# Testing

Back to the [README](../README.md).

Tests run under pytest, split into two suites by marker. `pytest` and `coverage` are
development-only: nothing here is needed to *run* the framework.

```sh
pip install -e ".[dev]"
./scripts/install-hooks.sh          # once per clone: installs the pre-commit gate
```

## Commands

| Command | Runs | Time |
|---|---|---|
| `./run-tests.sh fast` | 463 tests: unit, smoke, interface, contract, documentation, regression, cheap pathological, safety — then mypy | 35s |
| `./run-tests.sh long` | 93 tests: integration, load, packaging, fuzz, end-to-end catalogs | 160s |
| `./run-tests.sh all` | both, then mypy | 185s |
| `./run-tests.sh cov` | fast suite under coverage, gated at 95% lines and branches | 40s |

Extra arguments pass through to pytest: `./run-tests.sh fast -k dependency`,
`./run-tests.sh long tests/test_load.py`. Each mode exits non-zero on any failure and
prints one summary line.

Markers are `fast` and `long`; `--strict-markers` is on, so a typo fails rather than
silently selecting nothing.

CI runs the same three commands on every push and pull request
(`.github/workflows/ci.yml`), on the stated Python floor and on current Python, so
a clone without the hook installed is still covered.

## Gates

- **Pre-commit** — `./run-tests.sh fast`, installed by `./scripts/install-hooks.sh` into
  `.git/hooks/pre-commit`. Bypass with git's own `--no-verify`; there is no custom flag.
  Verified to block: breaking `format_table` and committing stops at the hook.
- **Pre-release** — `./run-tests.sh all` plus `./run-tests.sh cov`. Coverage below 95%
  fails the run through `coverage report --fail-under`.

## What each file covers

Fast:

| File | Covers |
|---|---|
| `tests/test_registry_unit.py` | Registration and its duplicate guard, suite inference, suite loading and its no-ops, `clear_registry`, dependency validation, cycle detection, topological order and its cache. |
| `tests/test_overrides_unit.py` | Every rule-file rejection (19 parametrised cases asserting the exact message), the three loaders and their ordering, duplicate names, matching semantics, last-rule-wins precedence. |
| `tests/test_results_unit.py` | The status vocabulary, registering project statuses, `TestResult` truthiness and validation, and normalising whatever a test returned. |
| `tests/test_validate_row_unit.py` | The per-row algorithm: outcomes and their reasons, enabled state, dependency skipping (failed, disabled, errored, transitive), signature adaptation, purity, `check_rule_columns`, root cause, layers, and the shipped tests at their boundaries. |
| `tests/test_groups_unit.py` | `test_group` defaults, prerequisites unioned with a test's own, suite and default-state overrides, and the registration guards. |
| `tests/test_report_unit.py` | Collection, the failure table and its columns, row keys, `include_skipped`/`include_passed`, table and CSV rendering, writing files, explanations and summaries. |
| `tests/test_readme.py` | The README executed: every Python block runs, the worked session prints exactly the output shown, the template block registers a test that actually validates a row, the example codes do not collide with the shipped ones, and the prose claims (dependencies, no package build, one line per failure, rules cannot define tests) are each checked against the code. |
| `tests/test_golden_output.py` | The report library's exact output, byte for byte, against the five files in `tests/golden/`: the table, the CSV, the include-skipped view, a row explanation and a summary — plus the bytes `write_report` puts on disk. |
| `tests/test_api_contract.py` | The public surface: every name in `__all__` importable, every public function exported, permanent `Status` values and outcome names, stable report and registry columns, and the default arguments of every exported function. |
| `tests/test_tables_unit.py` | `format_table` rendering, wrapping and empty frames; every column of the three registry tables, including the empty-registry paths. |
| `tests/test_context_unit.py` | `RowContext` defaults and `build_context`. |
| `tests/test_smoke.py` | Both entry points start, exit 0, and produce their main output. |
| `tests/test_interface_cli.py` | The CLI contract: flag flattening, defaults, `-v` counting, exit codes 0/1/2, stdout vs stderr routing, which tables each verbosity prints. |
| `tests/test_pathological.py` | Malformed YAML, unicode, 1000 rules, empty and wide rows, duplicate column labels, a 200-deep dependency chain, a check that raises. |
| `tests/test_safety.py` | `safe_load` refuses `!!python/object`, patterns are never evaluated, loading writes nothing, validation does not mutate the frame, suite names cannot import unrelated modules, directory loading does not recurse, a catastrophic regex stays bounded, errors do not quote unrelated rules, and CSV reports neutralise cells a spreadsheet would run as a formula. |

Long:

| File | Covers |
|---|---|
| `tests/test_packaging.py` | What an adopter gets: the package ships no tests of its own, `py.typed` is there, every module imports on its own, and a scratch adopter package outside this repository loads its suite, validates a frame and writes a report — all in subprocesses with only `src/` importable. |
| `tests/test_fuzz.py` | Generated input, seeded from a constant: 300 rule files through the parser (each either loads or raises a ValueError naming the file), 300 frames through the engine asserting its three invariants, and 100 hostile comment payloads through both renderers. |
| `tests/test_properties.py` | The same three engine invariants, explored by Hypothesis rather than a fixed seed, so it shrinks a failure to the smallest reproducing case. `hypothesis` is in the `dev` extra, so a normal development install runs these; the import guard only covers a bare runtime install, and a contract test asserts the dependency stays declared. |
| `tests/test_integration.py` | Real rule files on disk driving a whole DataFrame, all three loaders, precedence across directories, CSV export of the `errors` column, a suite package created at runtime, a written report re-read as a spreadsheet reader would, and the report agreeing with the per-row explanation. |
| `tests/test_load.py` | 20,000 rows within a 60s ceiling, correctness at volume, a 64 MB peak-memory ceiling for validation and 256 MB for the report path, rendering and summarising 5,000 rows within their ceilings, and a guard that the topological sort never runs inside the row loop. |
| `tests/test_e2e_catalogs.py` | Runs every catalog case through the real entry point. |

## Mutation testing

Coverage says every line ran; it says nothing about whether the assertion after it
would notice the line being wrong. `mutmut` answers that, by changing the code
and checking a test fails:

```sh
mutmut run          # long: thousands of mutants, resumable from its cache
mutmut results      # survived / killed, per mutant
mutmut show <name>  # the diff for one survivor
```

Configured in `[tool.mutmut]` in `pyproject.toml`. Two parts of that config are
worth understanding before changing them:

- `also_copy = ["examples/"]` — mutmut runs the suite against a copy of the tree
  under `mutants/`, and the entry points and example suites the tests load live
  in `examples/`, not in the package.
- `pytest_add_cli_args_test_selection` excludes six test files **from mutmut's
  runs only** — they still run in every normal suite. Four of them
  (`test_interface_cli.py`, `test_smoke.py`, `test_packaging.py`,
  `test_e2e_catalogs.py`) shell out to a subprocess, which never loads mutmut's
  instrumentation, so a mutant would always look like it survived. The other two
  (`test_api_contract.py`, `test_readme.py`) assert on the module's own structure
  and on the doc tree, neither of which survives being copied into `mutants/`
  with the generated trampoline functions in place.

Surviving mutants are a to-do list, not a failure: each one is a change to the
code that no test noticed. Known cluster as of the last run: the registry's
debug-print functions, whose tests check individual cells rather than pinning the
whole rendered table.

## Golden files

`tests/golden/` holds the exact text the report library produces — one view per
file, produced from the fixed frame in `tests/golden_fixture.py` and compared byte
for byte. They are tighter than the catalog: the catalog pins everything `examples/main.py`
prints (9-15 KB per case, registry tables included), while these isolate one view
each, so a diff points straight at what changed.

`test_a_written_file_is_byte_for_byte_the_golden_csv` compares the bytes on disk,
not just the string, which is what pins the encoding and keeps `csv`'s `\r\n`
from creeping back into written reports.

Regenerate with `python3 scripts/regen_golden.py` and read the diff, exactly as
with the catalog.

## Catalogs

`tests/examples/` and `tests/failures/` are worked examples and a troubleshooting
reference that execute as tests, so they cannot drift from behaviour. One directory per
case: `cmd`, `README.md`, the expected output, and `exit_code`.

- 10 example cases across suite selection, override loading and precedence, verbosity,
  and both entry points. stdout is compared byte for byte.
- 11 failure cases covering the mistakes a user actually makes. Each asserts the exact
  final line of stderr and the exit code.

Only two normalisations are applied, both documented in `tests/catalog.py`: the absolute
project root becomes `<project>`, and failure cases compare the last stderr line rather
than traceback frames whose line numbers move with any edit.

After an intended behaviour change, regenerate with `python3 scripts/regen_catalog.py`
(optionally with a case-name substring) and **read the diff** — a blind regeneration
defeats the catalog. A new flag or feature needs a new case before it ships.

## Coverage

100% of lines and branches in `src/pandas_row_validation/`, measured on the fast suite (long-suite
coverage would flatter the number). Enforced at 95% by `./run-tests.sh cov`, which fails
rather than warns.

```
Name                                Stmts   Miss Branch BrPart   Cover
src/pandas_row_validation/registry.py   310      0    126      0    100%
src/pandas_row_validation/report.py     142      0     64      0    100%
src/pandas_row_validation/results.py    102      0     28      0    100%
src/pandas_row_validation/rules.py       96      0     52      0    100%
src/pandas_row_validation/tables.py      37      0     16      0    100%
...
TOTAL                                   849      0    322      0    100%
```

Measured 2026-09-01. There are no coverage exclusions beyond `pragma: no cover` and
`if __name__ == "__main__":`, and nothing currently uses the pragma.

## Adding a test

- Put it in the file that owns the behaviour, marked `fast` unless it needs volume, real
  time, or a subprocess journey.
- Name it for the behaviour: `test_dependent_is_not_run_when_the_prerequisite_fails`, not
  `test_validate_row_3`.
- Assert the value, the message, or the exact codes a row produces — never that something
  ran. The dependency tests use a `calls` list precisely so "ran and passed" is
  distinguishable from "was skipped".
- Take the `fresh_registry` fixture (or `example_suites`) whenever the test registers or
  loads anything: the registry is process-global, and the fixture restores it afterwards
  so tests pass in any order or subset.
- No logic in the test — write expected values literally, or parametrise.
- Nothing in the suite mocks or monkeypatches a collaborator. The one substitution is in
  `test_load.py`, which wraps `_topological_order` in a counter to prove the sort never runs
  inside the row loop, then restores it.
- A bug gets a regression test named for it, with a one-line comment on the cause, before
  the fix. Two are in `test_registry_unit.py` and one in `test_tables_unit.py`.
