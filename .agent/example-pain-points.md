# Pain points met while writing complex catalog examples

Started 2026-09-26. Each entry: what hurt, where, and what might address it. Nothing here
is built; it is a list to survey with the owner.

## Survey before writing

- **Every existing complex case runs the same four shipped check files.** The ten
  `tests/examples/complex/` cases vary data, rule files and output flags only
  (`main.py` hard-codes `CHECK_FILES`). No catalog case shows an errored check, a
  check with two prerequisites, prerequisites across files, a context builder, or a
  rule disabling a presence check. The vehicle for any of those is
  `examples/run_from_config.py` with a case-local setup file -- which works, but is
  not how the catalog README says cases are built (`--entry` exists on
  `new_catalog_case.py`, undocumented in `tests/examples/README.md`).

## Case: complex/order-lines-two-root-causes-at-once

Own checks (three files, the dependent one named first), a diamond prerequisite, one rule.

- **Root cause is row-wide shallowest layer, not per dependency chain.** Row 6 has a
  blank `total` (layer 0) and a price `abc` (layer 1). The two are unrelated -- neither
  check depends on the other -- yet `PRICE_NOT_A_NUMBER` gets `is_root_cause False`
  and `root_cause_rows 0`. A reader fixing root causes first will fix the total, rerun,
  and only then meet the price. `engine.root_causes` (`src/jobcheck/engine.py:174`).
  Alternative: a failure is a root cause unless one of its (transitive) prerequisites
  failed on the row -- but a failed prerequisite means the dependent was skipped, so
  under that reading *every* failure is a root cause and the column says nothing.
  The layer rule is really "fix these first", which is defensible; the docs call it
  "downstream of", which it is not here (`docs/concepts.md`, root cause; `engine.py:178`
  docstring "Deeper failures are downstream of these").
- **Summary ties sort by `skipped`, not by layer or root cause.** Among checks failing
  once, `QTY_NOT_POSITIVE` / `TOTAL_MISMATCH` (layer 2) print above `PRICE_PRESENT`
  (layer 0, the root cause), and `PRICE_NOT_A_NUMBER` (0 root-cause rows) above
  `PRICE_PRESENT` (1). `report.py:232` sorts `failed, errored, skipped, code`. The
  registry table sorts by layer ascending, so the two tables disagree on what reads first.
- **The report's key column is headed `row`, whatever `key_column` names.** With
  `key_column: id` the header says `row`, not `id`; with `add_columns: [sku]` the
  column beside it keeps its own name. A reader of a CSV export cannot tell whether
  `row` is a position or the id. (Check: `build_report` renames on purpose?)
- **Comments show what the check computed, not what the file said.** `value=-1.0` for a
  cell `-1`, `expected=6.0`. Every numeric check converts to `float` first, so every
  comment is a float. Nothing in the library helps -- a check author has to remember to
  keep the raw cell for the comment. `writing-checks.md` "Comments" could say so.
- **`disabled` beats `skipped` in the counts.** `PROMO-2` has a blank quantity *and*
  matches the rule disabling `TOTAL_MISMATCH`: counted `disabled`, not `skipped`. Right,
  I think (the rule is the reason it could never have run), but not documented.
- **Writing a case-local check file means writing `_number` again.** Third copy of the
  same try-float helper in the tree (`examples/checks/check_age.py`, the nested-bundles
  case, this one). Not a library concern -- the library ships no checks -- but a
  reader copying examples copies it every time.

## Case: complex/a-broken-check-among-real-failures

A layer-0 check that calls `.upper()` on a blank (`NaN`) cell and raises on three rows,
alongside real failures on the same rows.

- **A broken check steals root cause from real data failures.** `errored` counts as
  `failed` for root causes (`CheckOutcome.failed`, `src/jobcheck/results.py:158`). Row
  S4 has a genuine delivered-before-shipped failure (layer 2); the broken layer-0 carrier
  check marks it `is_root_cause False`. "Fix the root cause first" sends the reader to a
  bug in the check, not the data. Options: root causes from `FAILED` only, or errors as
  their own tier. Owner decision; the current rule is at least consistent.
- **`root_cause_rows` can exceed `failed`.** Summary: `CARRIER_KNOWN failed 1,
  root_cause_rows 4, errored 3`. The count includes errored rows, the `failed` column
  does not. Reads as an arithmetic mistake until you know. `docs/reporting.md` does not
  say `root_cause_rows` counts errors.
- **An errored line carries the check's failure message.** S3 reads `ERROR (9) |
  errored | Carrier is not one we ship with` -- the message claims a verdict on the data
  that the check never reached. `reporting.md:54` documents it; still misleading in a
  report handed to a non-developer. Blank message, or "check raised", for errored lines?
- **No entry point can stop at the first broken check.** `on_error="raise"` exists on
  `validate`/`validate_row`/`explain_row`; neither `main.py` nor the run file can ask
  for it, and both exit 0 with errored checks in the report. A pipeline gating on exit
  status cannot tell a broken check from a clean run. (Demo scripts, so maybe fine --
  but the catalog is the documented reference.)
- **A run file cannot explain a row.** `run_from_config.py` offers registry, rules,
  report, summary; `row_explanation` (the view that shows `skipped` with the blocking
  prerequisite) is only on `main.py --explain`, which runs the four shipped check files.
  So a case with its own checks cannot show why a check did not fire. A `report` with
  `include: blocked` is the nearest substitute.
- **The exception text names no column.** `AttributeError: 'float' object has no
  attribute 'upper'` -- the reader has to know `NaN` is a float. The `KeyError` case gets
  the column for free; this common one does not. Nothing the library can add cheaply
  beyond the troubleshooting line; worth an entry in `writing-checks.md` Troubleshooting
  ("an `errored` outcome with `'float' object has no attribute`: a blank cell").

## Case: complex/excusing-a-blank-field-silences-its-checks

`main.py` with the shipped checks, a case-local CSV and one rule: disable `AGE_PRESENT`
for LEGACY_B rows, meaning "a blank age is fine there".

- **Rules cannot say "optional here".** The only lever is disable, and disabling a
  presence check blocks its whole chain, so LEGACY_B ages of `-3`, `forty` and `212`
  pass silently. Documented (`writing-checks.md`, "A disabled prerequisite blocks its
  dependents ... check the skipped column"), but the documented remedy is to *notice*,
  not to fix. The actual fix is in Python: the presence check itself reads
  `source_system`. That is outside what a non-developer editing rules can do -- the
  audience rules exist for. Possible: a third action (`allow_blank`? "pass" instead of
  "disable" -- record the check as passed so dependents run), or a per-check
  "disabled means passed" flag. Both widen the rule format the owner keeps shallow.
- **Nothing warns.** `warn_shadowed_rules` finds rules shadowed by a later `match: all`;
  nothing finds "this rule disables a check other checks depend on", which is cheap to
  compute from the registry (codes with dependents) and always worth a line. The rules
  table under `--rules-table` prints no warning here.
- **The registry understates a rule's reach.** `could_be_overridden_by` lists
  `legacy_b_has_no_age` against `AGE_PRESENT` only; the four age checks below it show
  `-` though the rule switches them off on the same rows. Likewise `codes_hit_count 1`
  in the rules table. Transitive reach would be one graph walk.
- **The report is silent about what did not run.** The default report (`include:
  failures`) has two lines, both MODERN rows; the LEGACY_B rows are absent, the same as
  clean rows. Only the summary's `skipped`/`disabled` counts give it away, and they are
  per check, not per row. `main.py` has no `--include` flag to show blocked lines
  (`build_report(include="blocked")` exists; the run file exposes it).
- **`codes_hit_count`** is an odd column name for "how many codes this rule lists"; it
  reads like a count of hits on data. (`registry_tables._RULES_COLUMNS`.)

## Case: complex/job-manifest-with-per-row-paths

Checks taking `(row, context)`; a builder `(row, args)` deriving per-row paths, with a
cross-row "who writes this output" map passed once through `context_args`. The owner's
row-scoped-constants use case (the reason C was rejected).

- **No shipped entry point can pass a context builder.** `main.py` and the run file
  both call `validate(df, rules=rules)`. So the catalog case carries its own script,
  with its own `sys.path` bootstrap (`HERE.parents[3] / "src"`, depth-fragile) -- the
  F.21 pattern once more. The one feature the owner defended hardest has no catalog
  coverage until now and no CLI route at all.
- **A builder that raises aborts the whole `validate`.** A blank `run_dir` makes
  `Path / float` raise `TypeError` in the builder: uncaught traceback, no report, every
  other row lost. A check raising the same way becomes one `errored` line and the run
  carries on. Inconsistent, and undocumented: `writing-checks.md` "Per-row context"
  and `interfaces.md` `validate` say what a builder may *look like*, not what happens
  when it raises. Options: record every context-taking check on that row as `errored`
  with the builder's exception (honors `on_error`); or document that a builder must not
  raise. Priority high-ish: one bad cell loses a whole large run.
- **Forgetting the builder errors every context check on every row.** Without
  `context_builder`, each row gets a bare `RowContext`; `context.run_dir` raises
  `AttributeError` per check per row -- a report as long as the frame, root cause on
  every row. Nothing ties a check to the context type it expects, so nothing can refuse
  up front. A check could declare it (`register_check(..., context=JobContext)`) and
  `validate` refuse a mismatched builder once -- new API surface; survey before building.
- **Checks see `context` untyped.** `def check(row, context)` gets a `RowContext`
  statically; `context.run_dir` is unknown to mypy and an IDE unless the author
  annotates `context: JobContext` by hand. Minor; convention only.
- **Rows with a missing run directory still build every path.** The builder runs before
  any check, for every row, whether or not a context-taking check will run there. Cheap
  here; costly if the builder stats files or reads them. Laziness would be the builder's
  job (a `functools.cached_property` on the subclass) -- worth one sentence in the docs.

## Process: adding cases

- **One case means editing three counts in two documents.** `docs/testing.md` catalog
  line (total and per level), the `long` and `all` suite sizes in its table, and the
  README's "N-case" total. Each is enforced by a test that fails with the real number,
  so it is mechanical, but four cases took three fast/long rounds to find them all
  (the `all` row only fails after `long` is fixed). `new_catalog_case.py` could print
  the new counts, or the documents could stop stating them.
- **`new_catalog_case.py` needs a bare `--` even with no arguments** (the context case
  runs its own script with none). Works; the usage line does not show it.
- **Catalog README lists the dimensions covered by hand** and has to be edited per new
  kind of case; `docs/testing.md` also names each entry point a case may run.
- **Case-local `.py` files join mypy's tree.** File names must be unique across
  `tests/` (the known "two same-named files under one root" trap) -- chose
  `check_order_*`, `check_shipment_*`, `check_job_paths` for that reason.
