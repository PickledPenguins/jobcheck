# Concepts

The words the other documents use, each defined once. The names are the code's own.

Back to the [README](../README.md).

## Checks

- **check** — one function registered under a code with `register_check`. It reads a
  row, and the row's context if it asks for one, and returns a verdict. Checks live in
  your own files, never in this package: [writing-checks.md](writing-checks.md).
- **code** — a check's permanent identifier, such as `AGE_PRESENT`. Rule files and saved
  reports refer to codes, so a code is never renumbered or reused.<sup>[1](writing-checks.md#codes-are-permanent)</sup>
- **message** — the text a person reads when the check fails; one per check.
- **prerequisite** — a code named in a check's `depends_on`. A check runs on a row only
  when every prerequisite passed on that row.<sup>[2](writing-checks.md#layering-one-problem-one-error)</sup>
- **layer** — how deep a check sits among its prerequisites: 0 with none, otherwise one
  more than its deepest prerequisite. Computed, never declared.
- **registry** — every check loaded in this process, in one process-global list.
  `load_checks` fills it, `clear_registry` empties it, `registry_table` shows it.<sup>[3](interfaces.md#the-registry)</sup>
- **check file**, **bundle** — a `.py` file `load_checks` imports by path; a bundle is a
  check file that loads other check files, so a caller names one path for all of them.<sup>[4](writing-checks.md#bundles-one-file-that-loads-the-rest)</sup>

## What a check says, and what the engine records

Three questions, and three types that answer them:

- **verdict** — what a check returns: `OK`, or a `Verdict` holding a status and
  comments. `Verdict(condition)` wraps a comparison.<sup>[5](writing-checks.md#what-to-return)</sup>
- **status** — what is wrong with the *value*, as a `Status`: `PASS` 0, `MISSING` 1,
  `MALFORMED` 2, `INVALID` 3, or `ERROR` 9, which only the engine records, for a check
  that raised. There is no "failed" status: *that* a check failed is its outcome, and the
  status says which kind of failure — every status but `PASS` is one.<sup>[6](writing-checks.md#statuses)</sup>
- **outcome** — what happened to the *check* on one row, as an `Outcome`: `passed`,
  `failed`, `errored` (it raised), `disabled` (a rule or its default switched it off),
  `skipped` (a prerequisite did not pass) or `shared` (the row is a copy, and the check
  ran on the first copy instead). The engine records one `CheckOutcome` per
  check per row: code, outcome, status, layer, message, detail and comments.<sup>[7](interfaces.md#checkoutcome)</sup>
- **comments** — the evidence a check attaches to its verdict, a mapping the report
  prints as `key=value; key=value`.<sup>[8](writing-checks.md#comments)</sup>
- **detail** — why a check gave no verdict: the rule that disabled it, the prerequisite
  that blocked it, or the exception it raised.

"Fine" has three names, one per question: a check returns `OK`, the engine records
`Outcome.PASSED`, and the status is `Status.PASS`. That is why a table shows
`passed | PASS (0)`, and why a `skipped`, `disabled` or `shared` line shows `PASS (0)`
as well: the status says something only beside a failure.<sup>[9](reporting.md#diagnosing-one-row)</sup>

## Rows

- **root cause** — a row's failures at its shallowest failing layer: the ones to read
  first. A deeper failure is never downstream of one — a check runs only once its
  prerequisites passed, so every failure is the root of its own chain — it is simply read
  after. Two failures at the same depth are two root causes. Data failures come first: a
  check that raised counts only on a row with no data failure. `build_report(...,
  include="root_causes")` keeps only them.<sup>[10](interfaces.md#build_reportframe_outcomes-df-key_columnnone-add_columnsnone-includefailures---dataframe)</sup>
- **context** — per-row state that is not a column: a `RowContext` subclass, built for
  each row by the `context_builder` handed to `validate`. A check asks for it by taking
  `(row, context)`.<sup>[11](writing-checks.md#per-row-context)</sup>

## Configuration

- **rule** — a YAML instruction to `enable` or `disable` codes for the rows it matches.
  Rules only switch existing checks, and for a given row the last matching rule wins:
  [configuration.md](configuration.md).
- **rule file** — a flat YAML list of rules. `load_rules` reads a list of rule files, in
  precedence order.
- **setup file** — one YAML file naming the check files and the rule files to load;
  `load_setup` loads both.<sup>[12](configuration.md#setup-files-naming-the-checks-and-the-rules-at-once)</sup>
- **run file** — the format of the demo entry point `examples/run_from_config.py`: a
  setup file, the data and the tables to print. Not the library's: [cli.md](cli.md).

## Output

- **report** — one line per failure per data row, built by `build_report`:
  [reporting.md](reporting.md).
- **table** — every view the library builds (the report, a row's explanation, the
  summary, the registry and rules tables) is a DataFrame carrying its title in
  `attrs["title"]`.<sup>[13](reporting.md#every-table-names-itself)</sup>
- **text** — pandas turns any table into text: `to_string()` for a terminal, `to_csv()`
  for a file. Nothing is wrapped or escaped.<sup>[14](reporting.md#writing-the-tables-to-files)</sup>

## References

| # | Section | What it covers |
|---|---|---|
| 1 | [writing-checks.md: Codes are permanent](writing-checks.md#codes-are-permanent) | what a reused code would break |
| 2 | [writing-checks.md: Layering](writing-checks.md#layering-one-problem-one-error) | how prerequisites keep one blank field to one error |
| 3 | [interfaces.md: The registry](interfaces.md#the-registry) | what each registered check holds |
| 4 | [writing-checks.md: Bundles](writing-checks.md#bundles-one-file-that-loads-the-rest) | writing one, and where its paths resolve |
| 5 | [writing-checks.md: What to return](writing-checks.md#what-to-return) | every form a check may return, and what is refused |
| 6 | [writing-checks.md: Statuses](writing-checks.md#statuses) | which status to choose for a failure |
| 7 | [interfaces.md: CheckOutcome](interfaces.md#checkoutcome) | the recorded fields, and `Outcome`'s members |
| 8 | [writing-checks.md: Comments](writing-checks.md#comments) | what to put in them |
| 9 | [reporting.md: Diagnosing one row](reporting.md#diagnosing-one-row) | a row's explanation, where these lines appear |
| 10 | [interfaces.md: Root causes](interfaces.md#build_reportframe_outcomes-df-key_columnnone-add_columnsnone-includefailures---dataframe) | the rule in full, errored checks included |
| 11 | [writing-checks.md: Per-row context](writing-checks.md#per-row-context) | writing a context and its builder |
| 12 | [configuration.md: Setup files](configuration.md#setup-files-naming-the-checks-and-the-rules-at-once) | the two keys, and where their paths resolve |
| 13 | [reporting.md: Every table names itself](reporting.md#every-table-names-itself) | titles, and giving your own frame one |
| 14 | [reporting.md: Writing the tables to files](reporting.md#writing-the-tables-to-files) | a CSV recipe per table, and what the writers do not do |
