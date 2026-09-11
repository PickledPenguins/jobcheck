# Handoff

Written 2026-09-11. Branch `simplify`, commit `9fe2207`, 30 commits ahead of `main`, tree
clean apart from this file. Start at `README.md` and the documents its index links;
`CLAUDE.md` holds the project's own history, which is stranger than most, and its last two
sections are what this branch changed.

## State

Measured at `9fe2207` on 2026-09-11 with the conda `pytesting` environment
(`~/.conda/envs/pytesting/bin/python`, Python 3.12.14, pandas 3.0.5, PyYAML 6.0.3,
pytest 9.1.1, coverage 7.16.0, mypy 2.3.1, hypothesis 6.167.1, mutmut 3.5.0).

| Gate | Result |
|---|---|
| `./run-tests.sh` (fast, the commit gate) | 605 passed, 1 skipped, 19s, then mypy |
| `./run-tests.sh long` | 231 passed, 280s |
| `./run-tests.sh cov` | 100% of statements **and** branches (852 statements, 286 branches), floor 95 |
| `./run-tests.sh memory` | 3 passed, 78s |
| `./run-tests.sh perf` | 5 passed, 1 skipped, against `.perf-baseline.json`, 84s |
| `mypy` | clean, 57 source files |
| Mutation | 1,278 mutants, **1,144 killed, 134 survived, 0 timeouts (89.5%)** |

Mutation was run against this tree, after the last test was added, so the score is the
score rather than a floor. The classification of the survivors is in `docs/testing.md`.

The package is 1,868 lines, 1,021 of them executable (`~/work/ai/skills/bin/pyloc`), across
9 modules, exporting 47 names. 37 test modules.

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh all     # + long, then the profile
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh cov     # coverage against the floor
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh perf    # timing vs this machine
PYTHON=~/.conda/envs/pytesting/bin/python ./run-tests.sh memory  # peak-memory ceilings
~/.conda/envs/pytesting/bin/python -c "import pandas, sys; sys.argv=['mutmut','run']; \
    from mutmut.__main__ import cli; cli()"                      # mutation, see the traps
```

**Run anything past the fast suite through `~/work/ai/skills/bin/bgrun`**, which waits on
the process rather than on its log: `id=$(bgrun start -l long -- ./run-tests.sh long)` then
`bgrun wait "$id"`. Its log is at `/tmp/bgrun-1000/<id>/log` when `wait` times out and you
want the tally out of it.

## What this session changed

Two commits here, plus one in `~/work/ai/skills`.

- **`2bb4670` Cut the features and spellings that said one thing twice.** The feature and
  naming pass catalogued in `CLAUDE.md` under "The second simplification pass": features
  removed, `include` collapsed from three booleans to one three-level argument, `debug` and
  `data_columns` collapsed into one `extra_columns` across all five tables, an override
  rule's `description` became a required `message` that is actually printed, nine renames
  so one concept has one word, and American spelling throughout (`normalize_result`,
  `summarize_outcomes`). One behavior change: the report has its own `detail` column.
- **`9fe2207` Cover the new extra_columns mechanism, and re-record the mutation score.**
  The first mutation run after the pass scored 87.9%; 20 survivors were the new
  `extra_columns` selection and the "(none available)" message, which no test read back.
  Tests for those, for the refused bare-string paths, and for an unknown `include` level.
  Back to 89.5%, and coverage back to 100%.
- **`~/work/ai/skills`, branch `claude`, commit `d57f694`.** The American English rule is
  now in `agent-config/claude/CLAUDE.md` — the file `~/.claude/CLAUDE.md` links to — worded
  to cover identifiers and not only prose, because `normalise_result` and
  `summarise_outcomes` had shipped as public names before the preference was written down
  anywhere an agent reads.

## Not addressed — the real to-do list

- **jobchain's suite now fails against this branch.** `~/work/ai/jobchain` (branch
  `simplify-port`) reads `~/work/ai/jobcheck/src` live rather than a pinned commit, and
  five of its override-rule fixtures have no `message:` key, which this branch made
  required: three inline YAML strings in `tests/test_checks_unit.py`, one in
  `tests/examples/test_complex.py`, one in `tests/examples/test_moderate.py`. One line
  each; grep for `action: disable` and `action: enable` to find them. Its check files need
  nothing — they already return `PASS`/`CheckResult` only — and every name in
  `jobchain/checks.py:_ENGINE_NAMES` survived the renames untouched.
- **No review has run against this pass.** `reviews/` is empty. `/creview` then
  `/caddressreview` is the obvious next move.
- **`docs/*.md` code blocks are bound against real signatures but not executed.** Most are
  fragments with an undefined `df`, so executing them means making each self-contained,
  which would make them worse to read. The README's blocks *are* executed byte for byte.
  Pre-existing; revisit only if a doc example breaks in a way neither catches.
- **`recovery/README.md` is not reachable from the README index**, because the index test
  only walks `docs/`. It documents a recovery archive rather than current behavior, so it
  was left out deliberately rather than missed.

Settled by standing preference, not open: the work stays on the `simplify` branch and is
not merged; breaking the CLI or the Python API is acceptable and no compatibility shims are
wanted; there is no CI, and the pre-commit hook plus the release gates are what run the
suites; there is no changelog, because `git log` is the record; the licence is the owner's
to choose; **American English everywhere, identifiers included**.

## Considered and deliberately not done

`docs/future-work.md` carries the older list with its evidence. What this session closed:

- **Removing `extra_columns` from `build_report`** (it was `data_columns`). Proposed with
  the measurement — ~45 source lines, 103 test lines, and a 24-line guard function whose
  only job was catching ambiguity the feature itself creates — and **kept** by the owner.
  Do not re-propose: it is the one way to get business context onto a failure line without
  merging the report back to the frame.
- **Removing `on_error="raise"`**, and **removing wrapping from `format_table`**. Both
  measured (12 and 25 source lines) and kept. The wrapping removal would also have forced
  every golden file and catalog case to be regenerated, which is the expensive half.
- **Making `on_error` a bool.** Rejected: `fmt`, a rule's `action` and the new `include` are
  all lowercase string choices validated at the boundary, so a bool would be the odd one
  out.
- **`context_type=RowContext`, constructed per row**, instead of keeping `context_builder`
  as a callable. Rejected: jobchain deliberately builds **one** context outside the loop,
  holding the whole file and a per-column value-count map, which is the difference between
  linear and quadratic on a large file. A per-row class hook makes that pattern awkward.
- **Making a rule's `message` optional.** Rejected: the instruction was to match
  `Check.message`, which is required and non-empty. A rule nobody can justify is a rule
  nobody dares delete, and the message is now printed beside it.
- **Keeping `Check.description` alongside `message`.** Removed: it was the only thing in the
  package carrying a second text field, and the registry table now shows `message`, which
  every check must have anyway.
- **Leaving `outcomes`/`outcomes_per_row` alone.** They are `row_outcomes` and
  `frame_outcomes` now; the pair reads as deliberate rather than accidental.
- **Splicing `detail` into `message` and `comments`.** That was the old behavior and it is
  gone; see the decisions below.
- **Chasing the remaining mutation survivors.** Unchanged: default-argument mutants mutmut's
  trampoline cannot execute, platform equivalents, and print/message wording the catalog
  pins where mutmut cannot run it.

## Decisions worth knowing before changing things

**`CheckResult` resolves a bool before anything reads the value as an integer.** `True == 1
== Status.MISSING` and `False == 0 == Status.PASS`, so the order of those branches in
`__post_init__` is the whole reason `CheckResult(row["age"] > 0)` means what it says. Move
the bool branch below the integer check and every wrapped comparison inverts silently.

**A check returns `PASS` or a `CheckResult`, and nothing else.** Bare `True`, bare `False`
and a bare `Status` all raise now, naming the check. `CheckResult(condition)` is how a
comparison becomes a result, and `normalize_result` is a type check rather than a converter.

**`code` is a check identifier everywhere; `status` is the integer.** `CheckResult.status`
used to be `.code`, colliding with `Check.code`, `CheckOutcome.code` and
`register_check(code=)`. `CheckOutcome` already carried both correctly, which is what
settled the vocabulary.

**The report's `detail` column exists because `detail` used to be copied into `message`
*and* `comments`** for any outcome that did not evaluate the row. The same string appeared
in two columns and neither heading could be trusted. `message` is now empty for a check that
did not run, and `detail` empty for one that did.

**`extra_columns` is one argument with one meaning on five functions** — the report takes
names of *your frame's* columns; the registry and rule tables take names of *their own*
optional columns. `could_be_overridden_by` is only on offer where the rules were actually
passed in, since no other table can answer it. An unknown name raises, naming the table and
what is available. `_check_extra_columns` in `tables.py` is the shared validator and is
private deliberately: `test_api_contract.py` fails on any public callable `__init__` does
not export.

**`RowContext` is bare and has no `build` method.** The library defines the type and nothing
else; `validate(context_builder=...)` takes any callable, so where the adopter's build
method lives is their business. Without a builder every row is handed the same empty
instance, built once rather than per row.

**Both loaders refuse a bare string.** `load_checks("checks.py")` raises `TypeError` naming
the list form, rather than iterating the string's characters and reporting a missing file
called `c`.

**One key column, not several.** The `|` join and its collision rule are gone; a composite
key is a column the caller builds, where they decide how the parts join.

**Every failure at the shallowest layer is a root cause.** Unchanged — but `root_cause`
(singular) is gone. `root_causes(...)[0]` is the single label, and `tests/conftest.py` has a
`first_cause` helper for the tests that want one.

**`resolve_enabled_state` returns `(enabled, reason)` per code**, not a bool. The private
`_resolve_state` it used to wrap is gone. `tests/conftest.py::enabled_only` drops the reason
where a test only cares which codes are on.

## Measurements, so they are not re-derived

- **The size change this pass bought**: 1,888 → 1,868 source lines, 1,052 → 1,021
  executable, 51 → 47 exported names. Far less than the ~250 lines estimated up front: the
  removals landed, but the `extra_columns` mechanism, the bare-`RowContext` documentation
  and the `include` levels cost most of it back. **The win is in the surface, not the
  size** — judge any further pass the same way.
- **Mutation, first pass after the change: 87.9%** (1,278 mutants, 154 survived). Twenty of
  those were genuinely untested new code, all in the `extra_columns` selection. After the
  tests: **89.5%**. Survivors by module now: `report` 47, `registry_tables` 43, `engine` 18,
  `registry` 14, `rules` 10, `tables` 2.
- **Registry table widths, demo registry (11 checks, 3 rules)** — the measurement that
  killed `debug`: `print_registry` was 106 columns at `debug=0`, 148 at `debug=1`, **216**
  at `debug=2`, unreadable in any terminal. `debug=1` did nothing at all on three of the
  four tables. `print_override_rules` is 141 columns now that `message` is a base column,
  wrapped at 40.
- **Performance baseline**, unchanged by this pass, 4,000-row frame, Python 3.12.14 on this
  machine, in the gitignored `.perf-baseline.json`: `validate` 6.250s (spread 8%),
  `validate_row` per row 6.174s (2%), `build_report` 0.048s (123%), `render_report` 0.048s
  (8%), `summarize_outcomes` 0.020s (4%), `validate` with 50 rules over 1,000 rows 0.403s
  (14%).
- **Suite runtimes**: fast 19s, long 280s, cov 20s, memory 78s, perf 84s, a full mutation
  run about four minutes at ~6 mutations/second.

## Environment and housekeeping

- **Use `PYTHON=~/.conda/envs/pytesting/bin/python`** for anything but the fast suite. The
  default `python3` is anaconda 3.14.6 without hypothesis or mutmut.
- **Never install anything without asking.** Test tooling belongs in the `pytesting` env.
- Generated and gitignored: `mutants/` (19 MB after a run), `.build/`, `.mypy_cache/`,
  `.pytest_cache/`, `.hypothesis/`, `.perf-baseline.json` (machine-specific by design),
  `reviews/`.
- `scripts/install-hooks.sh` installs the fast suite as `.git/hooks/pre-commit`.
- `pyproject.toml` is the one dependency list; the test that used to read the file reads the
  metadata now, without `tomllib`, which arrived in 3.11 while the declared floor is 3.10.

## Things that will bite

**A `@dataclass` defined *inside* a test function fails when that test uses
`fresh_registry`.** The fixture's `clear_registry` evicts the registering module from
`sys.modules`, and `dataclasses` resolves annotations by looking the class's module up
there: `AttributeError: 'NoneType' object has no attribute '__dict__'`, raised from
`dataclasses.py`, nowhere near the cause. Define the dataclass at module level, or use a
plain subclass with an `__init__`. Cost this session twenty minutes.

**`.perf-baseline.json` still holds a stale `summarise_outcomes/4000` key** beside the new
`summarize_outcomes/4000`. Harmless — the gate looks up by the current name — but anyone
comparing keys will wonder. The file is gitignored and machine-local: delete it and
re-record if it bothers you.

**Long commands get killed at the foreground timeout.** `all`, the catalog, a mutation run
and `regen_catalog.py` all exceed two minutes. Use `~/work/ai/skills/bin/bgrun`; do not
write another loop that greps the log for a completion word.

**`mutmut` needs pandas imported before it starts.** Plain `mutmut run` dies in stats
collection with `RuntimeError: context has already been set` from `multiprocessing`. The
command in the State block works.

**A targeted `mutmut run <name>` throws away every other mutant's result.** Checking one
mutant after writing a test for it is the right move; just expect the score to be gone until
the next full run, and do not quote `mutmut results` in between.

**A stale `mutants/` tree lies about the score.** `rm -rf mutants .mutmut-cache` whenever the
package layout changes.

**mutmut runs the *whole* selected suite once per mutant.** `pyproject.toml` excludes the
files that shell out, the two that read `docs/`, and the slow suites; without those
exclusions a run takes days rather than four minutes.

**The perf gate fails if anything else is using the machine.** Run `perf` and `memory` in
sequence, never concurrently.

**`./run-tests.sh long` refuses to run without hypothesis.** Deliberate: a skipped property
suite reads as a pass.

**The catalog runs every case through a symlink** at `$TMPDIR/prv-catalog-root-<8-digit uid>`
so column widths do not depend on the clone's path length. A filesystem without symlinks
falls back to the real root, and one test skips.

**Regenerating is not the same as fixing.** `scripts/regen_catalog.py`, `regen_golden.py` and
`make_example_data.py` all rewrite files the suite compares byte for byte. Read the diff, or
a defect becomes a recorded expectation. This pass regenerated all of them, for the `detail`
column and the registry table's `message`; the diffs were read and held nothing else.
