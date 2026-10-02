# Contributing

Back to the [README](../README.md).

Changing this project itself: where a change goes, and what enforces what.

## Where a change goes

| Change | Where |
|---|---|
| A new check for row data | Your own package, not this one. This library ships no checks — see [writing-checks.md](writing-checks.md). |
| What checks exist: registration, file loading, the dependency graph | `src/jobcheck/registry.py` |
| What happens to a row, and to a whole frame: on/off state, evaluation order, outcomes | `src/jobcheck/engine.py` |
| Every view: the report and its root causes, a row's explanation, the summary, the registry and rules tables | `src/jobcheck/views.py` |
| The rule-file format and its parser | `src/jobcheck/rules.py` — it never reaches into the registry; the codes that exist are handed to it |
| What a check may return, and the status vocabulary | `src/jobcheck/results.py` |
| The columns every table shows by default, table titles, null handling | `src/jobcheck/tables.py` |
| How a named path becomes a file, and what a missing one says | `src/jobcheck/paths.py` |
| A demo of any of the above | `examples/`, never the package |
| A dependency | `pyproject.toml` only — there is no requirements.txt to keep in step |

One layout rule a test enforces: the package ships no tests of its own
(`tests/test_packaging.py` checks that from a subprocess with only `src/` importable).
Two more are conventions nothing checks: a unit file is named for what it covers,
`tests/test_<module>_unit.py` where one module is the subject, and generated artifacts
go under `.build/`, never the project root.

## What enforces what

Nothing here relies on remembering. Each rule below fails a run when it is broken.

| Rule | Enforced by |
|---|---|
| The fast suite passes before every commit | `.git/hooks/pre-commit`, installed by `scripts/install-hooks.sh` |
| 95% statements and branches | `./tests/run-tests.sh cov`, through `coverage report --fail-under` |
| Every public function and class is exported, sorted, and documented in `interfaces.md` — each function with its real signature, each type with its fields or members | `tests/test_api_contract.py`, `tests/test_docs_api_unit.py` |
| Every flag and argument of the three entry points has a section in `docs/cli.md` and every documented one exists; the usage lines, the run-file table and the exit codes are the real ones | `tests/test_docs_cli_unit.py` |
| Every Python block in `docs/` runs and prints the output shown after it, and every call shown matches the real signature | `tests/test_docs_blocks_unit.py`, `tests/test_docs_api_unit.py` |
| The README runs and prints exactly what it shows | `tests/test_readme.py` |
| The README stays an index (300 lines), every document is reachable from it, no dead link or anchor | `tests/test_docs_structure_unit.py` |
| What a document copies from the code matches it: the shipped rule file, the rule and setup keys, the module and script tables | `tests/test_docs_structure_unit.py` |
| Every message a user can meet — a raised error, an example script's `error:` line, a warning — is quoted in the document that owns it | `tests/test_docs_messages_unit.py` |
| Every superscript cross-reference is a row of its document's `## References` table, and every row is cited | `tests/test_docs_references_unit.py` |
| Every catalog case documents itself and states its level, and each level keeps its floor | `tests/test_e2e_catalogs.py` |
| The shipped rule files load together and name real codes and columns | `tests/test_shipped_examples_unit.py` |
| The example data is what its generator produces | `tests/test_shipped_examples_unit.py` |
| Timing has not regressed against this machine's baseline | `./tests/run-tests.sh perf` |
| Peak memory stays under its ceilings | `./tests/run-tests.sh memory` |
| The tests notice at least 94% of mutations to the code | `./tests/run-tests.sh mutation`, through `scripts/mutation_score.py` |
| Types check | `mypy`, run by `./tests/run-tests.sh fast`, `all` and `types` |

## Style

The bar is a junior developer reading this for the first time, and it is the
reason several obvious-looking shortcuts are absent:

- **No lambdas.** A named function says what it is for. The package holds two, in
  `engine._context_caller`; a new one is a review comment.
- **No dense one-liners.** A comprehension with two conditions, or one indexing
  into a nested structure, gets unpacked into a named value or a plain loop.
- **Lines stay under 100 characters** in `src/`, `examples/` and `scripts/`, and a
  test enforces it there, naming the file, the line and its width. There is no
  linter here; the check is twenty lines in `tests/test_docs_structure_unit.py`, beside the
  others that keep a document honest about the code. A long error message is
  wrapped as adjacent string literals rather than run out to 120. `tests/` is
  exempt: its long lines are table rows, pinned messages and parametrize entries,
  where wrapping costs more than it buys.
- **A line is either obvious or carries a brief comment saying what it does.**
  Docstrings say what a function is for and why it exists, in less space than the
  function takes; the detail of arguments, return shapes and errors lives in
  [interfaces.md](interfaces.md), which a test keeps in step with the code.
- **A leading underscore means "outside the public surface", not "inside this
  file".** `tables.py`'s `_format_cell` and `_reject_unknown_columns` are imported by
  `rules.py` and `views.py` on purpose. What the underscore rules out is a *user* calling them: a function or
  class without one has to be in `__all__`, which `tests/test_api_contract.py`
  enforces for every module but `paths`, and anything exported needs a use case a
  user outside this package actually has.

## Writing the documents

Each subject has one owning document, and the others point to it rather than restate
it. A term used in one document and explained in another carries a superscript number
linking straight to the explanation:

```
Zero is a pass; every other value is a failure.<sup>[1](concepts.md#rows)</sup>
```

and the document ends with a `## References` table, one row per number: where it points,
and what a reader finds there.

```
## References

| # | Section | What it covers |
|---|---|---|
| 1 | [concepts.md: Rows](concepts.md#rows) | what a root cause is |
```

The number stays out of the reader's way; the table shows at a glance what else to read.
Number the rows 1, 2, 3 in the order they are first cited, cite a number again rather
than adding a second row to the same place, and keep the table the last section. Add a
reference where a reader could otherwise conclude something is undocumented — a term
defined elsewhere, a behavior whose reason lives in another document — not on every
mention of a name. A plain inline link stays right where the link is the point of the
sentence ("see [reporting.md](reporting.md)").

A message the code can show a user is quoted, not paraphrased: the table in the owning
document (`interfaces.md`, `configuration.md` or `cli.md`) holds its text, with `<...>`
for the values that vary, because a user holding the message searches for its words.
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
python3 scripts/regen_docs.py [name]      # the output shown after each Python block in docs/ and the README
```

Each regenerator rewrites files the suite compares byte for byte. Read the diff before
committing: a blind regeneration turns a failing test into a recorded bug.
