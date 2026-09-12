# Handoff

Written 2026-09-12. Branch `simplify`, commit `966c9ff`, 37 commits ahead of `main`, tree
clean apart from this file. Start at `README.md` and the documents its index links;
`CLAUDE.md` holds the project's own history, which is stranger than most. This session was
a review-and-readability pass: six commits, no new features.

## State

Measured at `966c9ff` on 2026-09-12 with the conda `pytesting` environment
(`~/.conda/envs/pytesting/bin/python`, Python 3.12.14, pandas 3.0.5, PyYAML 6.0.3,
pytest 9.1.1, coverage 7.16.0, mypy 2.3.1, hypothesis 6.167.1, mutmut 3.5.0).

| Gate | Result |
|---|---|
| `./tests/run-tests.sh` (fast, the commit gate) | 607 passed, 21s, then mypy |
| `./tests/run-tests.sh long` | 231 passed |
| `./tests/run-tests.sh all` | 838 passed, 305s |
| `./tests/run-tests.sh cov` | 100% of statements **and** branches (872 statements, 292 branches), floor 95 |
| `./tests/run-tests.sh memory` | 3 passed, 86s |
| `./tests/run-tests.sh perf` | 6 passed, 98s, against `.build/perf-baseline.json` |
| `mypy` | clean, 57 source files |
| Mutation | **not re-run this session.** The 89.5% in `docs/testing.md` was measured at `9fe2207`, five commits back, and the code under it has been rewritten since |

The package is 1,726 lines, 1,059 of them executable (`~/work/ai/skills/bin/pyloc`), across
9 modules, exporting 48 names. 33 test modules.

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh all     # + long, then the profile
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh cov     # coverage against the floor
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh perf    # timing vs this machine
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh memory  # peak-memory ceilings
~/.conda/envs/pytesting/bin/python -c "import pandas, sys; sys.argv=['mutmut','run']; \
    from mutmut.__main__ import cli; cli()"                      # mutation, see the traps
```

**Run anything past the fast suite through `~/work/ai/skills/bin/bgrun`**, which waits on
the process rather than on its log: `id=$(bgrun start -l long -- ./tests/run-tests.sh long)` then
`bgrun wait "$id"`. Its log is at `/tmp/bgrun-1000/<id>/log` when `wait` times out and you
want the tally out of it.

## What this session changed

Six commits, all on `simplify`. A `/creview`, a `/caddressreview`, a second `/creview`
weighted to maintainability, its `/caddressreview`, and a `/creadme` audit.

- **`cd4a05a` Close the review's findings: key labels, wrap width, deep chains.** A
  duplicated `key_column` made `df[key_column]` a table, so every report line was labelled
  with the column *name* and `zip` truncated the report — refused now. `wrap_width=0`
  silently meant "do not wrap" while `-1` raised; both refused. A dependency chain too deep
  for the ordering walk raised a bare `RecursionError`; it names the registry now. Also the
  dead `KEY_SEPARATOR`, the `report.csv` a documentation run left in the root, and the
  suite sizes and catalog counts in the docs, which had drifted by five, three, eight and
  one — with a test that compares them against a collection so they cannot drift silently.
- **`ef146ee` One registry printer, and a heading that fits its data.**
  `print_registry_with_overrides` is gone; its `override_rules` and `effective_state` are
  `print_registry` extras, and `could_be_overridden_by` names each rule with its action.
  `default_state` is `default`.
- **`3f1c2e4` Stop the report-scaling check failing on a busy machine.**
  `test_building_a_report_scales_with_the_failures_not_the_rows` asserted `quick < slow` on
  two single ~50ms measurements and failed twice under load. Best of five after a warm-up,
  bound is `slow / quick > 2` against a measured 4.2.
- **`a653ea5` Registration validation is one function, not a wall in the decorator.**
  `_reject_bad_registration` holds the five guards; the decorator went 42 lines to 26.
- **`8b0baa5` Make the package read the way its own standard says it should.**
  `format_table` is two named passes with `_cell_lines` and `_padded_line`; the four lambdas
  are named functions; `build_report`'s setup is `available` and `_extra_values`; docstrings
  trimmed from 563 lines to about 340 beside 1,046 of code; `registry.snapshot`/`restore`
  replace the four private globals `tests/conftest.py` was saving; the example checks use
  the exported `is_null`; `docs/contributing.md` states the style rules.
- **`966c9ff` Say which commit the mutation score describes, and what refuses a key
  column.** Documentation only.

## Not addressed — the real to-do list

- **Mutation has not run since `9fe2207`.** Five commits of source change later, the
  recorded 89.5% and the per-module survivor counts in `docs/testing.md` describe code that
  no longer exists. `rm -rf mutants .mutmut-cache` first, run the command in the State
  block (~4 minutes), then rewrite that section with what comes back. The owner chose to
  label the stale score rather than re-run it this session; the label says the same.
- **The test suite has never been reviewed for readability.** It is 33 modules and about
  three times the package, it is what a junior developer reads to learn what the code
  promises, and both reviews this session judged only the package.
  `tests/test_tables_unit.py` and `tests/test_report_unit.py` are the two to start with.
- **`rules.py` matching has no timeout.** A rule file whose regex backtracks catastrophically
  (`(a+)+$` against a long cell) runs inside `rule_matches` for every row with nothing to
  stop it. `tests/test_fuzz.py` already throws 300 generated rule files at the parser; what
  is missing is adversarial *regex* input. `ctesting` is the skill for it.
- **`docs/testing.md` says the fast suite is 15s; it is 21s.** Measured end to end this
  session. About 3.4s of the growth is the new suite-size test, which spawns two pytest
  collections. The owner was asked and chose to leave the timing column alone.
- **jobchain's suite still fails against this branch** — unchanged from the last handoff.
  `~/work/ai/jobchain` (branch `simplify-port`) reads this `src` live, and five of its
  override-rule fixtures have no `message:` key. One line each; grep for `action: disable`
  and `action: enable`. Nothing this session touched changes that list, and
  `jobchain/checks.py:_ENGINE_NAMES` names nothing that moved.
- **`docs/*.md` code blocks are bound against real signatures but not executed.**
  Pre-existing; the README's blocks *are* executed byte for byte.

Settled by standing preference, not open: the work stays on `simplify` and is not merged;
breaking the CLI or the Python API is acceptable and no compatibility shims are wanted;
there is no CI; there is no changelog, because `git log` is the record; the license is the
owner's to choose; **American English everywhere, identifiers included**.

## Considered and deliberately not done

`docs/future-work.md` carries the older list with its evidence, and gained three entries
this session. What was closed here:

- **Narrowing the registry table by breaking long words** (138 columns) **or by replacing
  the rule names with a count** (107). Both measured and rejected: a broken identifier
  cannot be copied out of the output, and the names are the reason the column exists. A
  `format_table` default wrap width was measured too and saves **nothing** — the binding
  constraint is a 48-character rule name in `examples/rules/`, not the wrap. What was taken
  was the free 6 columns from renaming `default_state`; the table is 150 wide.
- **Shortening the demo rule names.** Not done, but worth remembering before concluding the
  table cannot be narrower: the width comes from data in `examples/rules/`, not the library.
- **Moving docstring rationale into `docs/architecture.md`.** Proposed by the review and
  rejected by the owner: the rationale belongs next to the code as a brief comment, not in
  a document. What was done instead is the trim — a docstring says what a thing is for and
  why, in less room than the code takes, and `interfaces.md` owns arguments, return shapes
  and errors.
- **Splitting `explain_row`** (69 lines, the longest function). Left whole: it is the one
  per-row algorithm read top to bottom, and breaking the four branches into helpers makes a
  junior reader jump four times to follow one loop.
- **A shared helper for the bare-string path guard** duplicated in `registry.load_checks`
  and `rules.load_overrides`. Rejected: five lines saved, and the only module both can
  import is `rules.py`, the rule-file parser, which is the wrong home.
- **A shared helper for the empty-table print** at four sites. Rejected: about eight lines
  saved for one more indirection between a reader and the output they are looking at.

## Decisions worth knowing before changing things

The decisions from the last handoff still hold — `CheckResult` resolving a bool before
anything reads it as an integer, `code` as a check identifier against `status` as the
integer, the report's own `detail` column, one key column, `RowContext` being bare. New
ones:

**`print_registry` is the only registry printer, and `overrides` feeds exactly two optional
columns.** Passing rules without asking for `could_be_overridden_by` or `effective_state`
prints the same table as passing none. That surprised the owner this session and is worth
stating: the table always prints, it is the rule columns that are opt-in.

**`registry.snapshot()` and `restore(state)` own what registry state *is*.** Four private
globals were being saved by hand in `tests/conftest.py`, so a fifth piece of state would
have been silently un-restored. Add to the snapshot dict, not to the fixture.

**`format_table` renders in two passes on purpose.** Every cell is wrapped before anything
is printed, because a column's width is not known until the last cell in it has been
wrapped. `_cell_lines` never breaks inside a word, so a long identifier overflows its
column rather than being mangled — that is what keeps codes greppable in saved output.

**`_number` in `examples/checks/check_age.py` has no missing-value guard.** Every check that
calls it depends on `AGE_PRESENT`, so it only runs on a row that has an age. The guard that
used to be there became unreachable when the example switched to `is_null`, and coverage
caught it.

**The style rules are written down in `docs/contributing.md`:** no lambdas, no dense
one-liners, lines under 100 columns, and a line is either obvious or carries a brief
comment. The package has no lambdas left; a new one is a review comment.

## Measurements, so they are not re-derived

- **Registry table width**, demo registry, 11 checks and 3 rules: 105 columns before
  `could_be_overridden_by` was asked for, 156 with it, 150 after `default_state` became
  `default`. Breaking long words would give 138, a count column 107, a default wrap width
  156 — no change, since a 48-character rule name is the constraint.
- **`build_report` on 4,000 rows**: a frame with no failures costs about a quarter of a
  failing one (measured 4.2x), best of five after a warm-up. Not "almost nothing" — the
  rows are still walked and their root causes resolved to produce no lines at all.
- **Docstrings**: 563 lines against 1,004 of code before the trim, about 340 against 1,046
  after. Inline comments went from 54 lines to 67.
- **Function lengths after the pass**: `explain_row` 69, `load_checks` 46, `parse_rule` 45,
  `build_report` 44, `format_table` 35 across three functions now.
- **Suite runtimes on this machine**: fast 21s, long ~290s, all 305s, cov 26s, memory 86s,
  perf 98s, profile 9s.
- **Performance baseline**, unchanged this session, 4,000-row frame, in the gitignored
  `.build/perf-baseline.json`: `validate` 6.250s, `validate_row` per row 6.174s, `build_report`
  0.048s, `render_report` 0.048s, `summarize_outcomes` 0.020s, `validate` with 50 rules over
  1,000 rows 0.403s.

## Environment and housekeeping

- **Use `PYTHON=~/.conda/envs/pytesting/bin/python`** for anything but the fast suite. The
  default `python3` is anaconda 3.14.6 without hypothesis or mutmut.
- **Never install anything without asking.** Test tooling belongs in the `pytesting` env.
- Generated and gitignored: everything under `.build/` -- the coverage data, the pytest
  and mypy caches, the hypothesis storage, `examples.prof` and `perf-baseline.json`
  (machine-specific by design) -- plus `.agent/reviews/`, and `mutants/` (19 MB after a
  run), the one artifact mutmut insists on writing beside the project.
- `scripts/install-hooks.sh` installs the fast suite as `.git/hooks/pre-commit`.
- `.agent/reviews/` is empty: both reviews this session were worked through and their
  reports cleared.
- The agent files are out of the project root: this record is `.agent/HANDOFF.md`, the
  guidance is `.claude/CLAUDE.md`, and the test entry point is `tests/run-tests.sh`.

## Things that will bite

The traps from the last handoff all still apply: a `@dataclass` defined inside a test
function fails under `fresh_registry`; `mutmut` needs pandas imported before it starts; a
targeted `mutmut run <name>` throws away every other mutant's result; a stale `mutants/`
tree lies about the score; `mutmut` runs the whole selected suite once per mutant, so the
exclusions in `pyproject.toml` are load-bearing; `./tests/run-tests.sh long` refuses to run
without hypothesis; the catalog runs every case through a symlink of fixed length; and
regenerating is not the same as fixing — read the diff. Added this session:

**Do not run two suites at once.** `tests/test_scaling.py` failed twice this session purely
because a second pytest was running beside it, and `perf` and `memory` are worse. The
scaling check is noise-proof now (best of five after a warm-up) but the timing gates are
not, and cannot be.

**`.build/perf-baseline.json` still holds a stale `summarise_outcomes/4000` key** beside the new
`summarize_outcomes/4000`. Harmless — the gate looks up by the current name — but anyone
comparing keys will wonder. Gitignored and machine-local: delete it and re-record if it
bothers you.

**A readability change can move coverage without changing behavior.** Switching
`examples/checks/check_age.py` to `is_null` rerouted the non-scalar case from an `if` to the
`except` below it and left the `if` unreachable, which showed up as 99% rather than as a
failure. Coverage is the thing that noticed; run `cov` after a refactor, not just `fast`.

**Long commands get killed at the foreground timeout.** `all`, the catalog, a mutation run
and `regen_catalog.py` all exceed two minutes. Use `~/work/ai/skills/bin/bgrun`; do not
write another loop that greps the log for a completion word.
