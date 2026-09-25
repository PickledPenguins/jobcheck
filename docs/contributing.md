# Contributing

Back to the [README](../README.md).

Changing this project itself: where a change goes, and what enforces what.

## Where a change goes

| Change | Where |
|---|---|
| A new check for row data | Your own package, not this one. This library ships no checks — see [writing-checks.md](writing-checks.md). |
| What checks exist: registration, file loading, the dependency graph | `src/jobcheck/registry.py` |
| What happens to a row, and to a whole frame: on/off state, evaluation order, outcomes, root causes | `src/jobcheck/engine.py` |
| How the registry and the rules are displayed | `src/jobcheck/registry_tables.py` |
| Anything about the report: columns, formats, files | `src/jobcheck/report.py` |
| The rule-file format and its parser | `src/jobcheck/rules.py` — it never reaches into the registry; the codes that exist are handed to it |
| What a check may return, and the status vocabulary | `src/jobcheck/results.py` |
| Table rendering and null handling | `src/jobcheck/tables.py` |
| How a named path becomes a file, and what a missing one says | `src/jobcheck/paths.py` |
| A demo of any of the above | `examples/`, never the package |
| A dependency | `pyproject.toml` only — there is no requirements.txt to keep in step |

Layout rules the tests enforce: unit files mirror the module they cover
(`tests/test_<module>_unit.py`), generated artifacts stay out of the project root, and the
package ships no tests of its own (`tests/test_packaging.py` checks that from a
subprocess with only `src/` importable).

## What enforces what

Nothing here relies on remembering. Each rule below fails a run when it is broken.

| Rule | Enforced by |
|---|---|
| The fast suite passes before every commit | `.git/hooks/pre-commit`, installed by `scripts/install-hooks.sh` |
| 95% statements and branches | `./tests/run-tests.sh cov`, through `coverage report --fail-under` |
| Every public name is exported, sorted, and documented | `tests/test_api_contract.py`, `tests/test_docs_api_unit.py` |
| Every entry-point flag has a section in `docs/cli.md`, and every documented flag exists | `tests/test_readme.py` |
| Every code block in `docs/` runs, and every call shown matches the real signature | `tests/test_docs_blocks_unit.py`, `tests/test_docs_api_unit.py` |
| The README runs and prints exactly what it shows | `tests/test_readme.py` |
| The README stays an index (300 lines), every document is reachable from it, no dead link or anchor | `tests/test_docs_structure_unit.py` |
| Every catalog case documents itself and states its level, and each level keeps its floor | `tests/test_e2e_catalogs.py` |
| The shipped rule files load together and name real codes and columns | `tests/test_shipped_examples_unit.py` |
| The example data is what its generator produces | `tests/test_shipped_examples_unit.py` |
| Timing has not regressed against this machine's baseline | `./tests/run-tests.sh perf` |
| Peak memory stays under its ceilings | `./tests/run-tests.sh memory` |
| Types check | `mypy`, run by `./tests/run-tests.sh fast`, `all` and `types` |

## Style

The bar is a junior developer reading this for the first time, and it is the
reason several obvious-looking shortcuts are absent:

- **No lambdas.** A named function says what it is for; there are none in the
  package, and a new one is a review comment.
- **No dense one-liners.** A comprehension with two conditions, or one indexing
  into a nested structure, gets unpacked into a named value or a plain loop.
- **Lines stay under 100 characters** in `src/`, `examples/` and `scripts/`, and a
  test enforces it there, naming the file, the line and its width. There is no
  linter here; the check is twenty lines in `tests/test_docs_structure_unit.py`, beside the
  others that keep a document honest about the code. A long error message is
  wrapped as adjacent string literals rather than run out to 120. `tests/` is
  exempt: 74 of its lines are over, and they are table rows, pinned messages and
  parametrize entries where wrapping costs more than it buys.
- **A line is either obvious or carries a brief comment saying what it does.**
  Docstrings say what a function is for and why it exists, in less space than the
  function takes; the detail of arguments, return shapes and errors lives in
  [interfaces.md](interfaces.md), which a test keeps in step with the code.
- **A leading underscore means "outside the public surface", not "inside this
  file".** `tables.py`'s `_format_cell` and `_reject_unknown_columns` are imported by
  three other modules on purpose. What the underscore rules out is a *user*
  calling them: a name without one has to be in `__all__`, which
  `tests/test_api_contract.py` enforces, and anything exported needs a use case a
  user outside this package actually has.

## Adding to the suite

Read [testing.md](testing.md) for what each file covers and which suite it belongs to.
Two conventions worth stating here:

- **Assert the value, not that something happened.** A test that only proves a call
  returned is worth nothing; check that it would fail if the code were wrong.
- **A bug gets a test named for the bug**, committed with the fix. Several tests in
  `tests/test_load_files_unit.py` and `tests/test_error_messages_unit.py` say in their docstring
  which surviving mutant or which defect they were written against; that is the pattern.

## Regenerating what is committed

```sh
python3 scripts/make_example_data.py      # examples/data/*.csv
python3 scripts/regen_catalog.py [name]   # tests/examples, tests/failures expectations
python3 scripts/regen_golden.py           # tests/golden
```

Each regenerator rewrites files the suite compares byte for byte. Read the diff before
committing: a blind regeneration turns a failing test into a recorded bug.
