# Concepts

The words the other documents use, each defined once. The names are the code's own.

Back to the [README](../README.md).

## Checks

- **check** — one function registered under a code with `register_check`. It reads a
  row, and the row's context if it asks for one, and returns a verdict. Checks live in
  your own files, never in this package: [writing-checks.md](writing-checks.md).
- **code** — a check's permanent identifier, such as `AGE_PRESENT`. Rule files and saved
  reports refer to codes, so a code is never renumbered or reused.
- **message** — the text a person reads when the check fails; one per check.
- **prerequisite** — a code named in a check's `depends_on`. A check runs on a row only
  when every prerequisite passed on that row.
- **layer** — how deep a check sits among its prerequisites: 0 with none, otherwise one
  more than its deepest prerequisite. Computed, never declared.
- **registry** — every check loaded in this process, in one process-global list.
  `load_checks` fills it, `clear_registry` empties it, `registry_table` shows it.
- **check file**, **bundle** — a `.py` file `load_checks` imports by path; a bundle is a
  check file that loads other check files, so a caller names one path for all of them.

## What a check says, and what the engine records

Three questions, and three types that answer them:

- **verdict** — what a check returns: `OK`, or a `Verdict` holding a status and
  comments. `Verdict(condition)` wraps a comparison.
- **status** — what is wrong with the *value*, as a `Status`: `PASS` 0, `MISSING` 1,
  `MALFORMED` 2, `INVALID` 3, or `ERROR` 9, which only the engine records, for a check
  that raised.
- **outcome** — what happened to the *check* on one row, as an `Outcome`: `passed`,
  `failed`, `errored` (it raised), `disabled` (a rule or its default switched it off) or
  `skipped` (a prerequisite did not pass). The engine records one `CheckOutcome` per
  check per row: code, outcome, status, layer, message, detail and comments.
- **comments** — the evidence a check attaches to its verdict, a mapping the report
  prints as `key=value; key=value`.
- **detail** — why a check gave no verdict: the rule that disabled it, the prerequisite
  that blocked it, or the exception it raised.

"Fine" has three names, one per question: a check returns `OK`, the engine records
`Outcome.PASSED`, and the status is `Status.PASS`. That is why a table shows
`passed | PASS (0)`, and why a `skipped` or `disabled` line shows `PASS (0)` as well:
the status says something only beside a failure.

## Rows

- **root cause** — a row's failures at its shallowest failing layer: the ones to read
  first. A deeper failure is never downstream of one — a check runs only once its
  prerequisites passed, so every failure is the root of its own chain — it is simply read
  after. Two failures at the same depth are two root causes. `root_causes` returns them.
- **context** — per-row state that is not a column: a `RowContext` subclass, built for
  each row by the `context_builder` handed to `validate`. A check asks for it by taking
  `(row, context)`.

## Configuration

- **rule** — a YAML instruction to `enable` or `disable` codes for the rows it matches.
  Rules only switch existing checks, and for a given row the last matching rule wins:
  [configuration.md](configuration.md).
- **rule file** — a flat YAML list of rules. `load_rules` reads a list of rule files, in
  precedence order.
- **setup file** — one YAML file naming the check files and the rule files to load;
  `load_setup` loads both.
- **run file** — the format of the demo entry point `examples/run_from_config.py`: a
  setup file, the data and the tables to print. Not the library's: [cli.md](cli.md).

## Output

- **report** — one line per failure per data row, built by `build_report`:
  [reporting.md](reporting.md).
- **table** — every view the library builds (the report, a row's explanation, the
  summary, the registry and rules tables) is a DataFrame carrying its title in
  `attrs["title"]`.
- **render** — `render(table)` draws any table as bordered text under its title, or as
  CSV with the cells a spreadsheet would run as formulas escaped.
