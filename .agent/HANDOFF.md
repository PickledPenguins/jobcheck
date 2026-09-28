# Handoff

Written 2026-09-27. Branch `simplify`, commit `dd2b631`, 110 commits ahead of `main`.
**The tree is not clean**, and most of what is uncommitted is not this session's work
(see "Uncommitted"). Start at `README.md` and the documents its index links;
`.claude/CLAUDE.md` holds the project's history. Then read the three review reports this
session saved under `.agent/reviews/` (gitignored), oldest first:

- `2026-09-27T14-13-04.claude-opus-5-5.md` — the uncommitted catalog work (diff scope).
- `2026-09-27T14-40-45.claude-opus-5-5.md` — `93941cf..dd2b631`, the commits since the
  2026-09-25 `src/` review, plus the mutation survivors in `engine`, `registry`, `rules`.
- `2026-09-27T15-11-05.claude-opus-5-5.md` — all of `src/`, function by function, with
  hand probes.

This session made no code changes and no commits. It reviewed three times, and was
asked to implement "all silent issues" and to put the rest in `docs/future-work.md`. It
stopped before editing anything (see "In flight").

## State

Observed this session, with `~/.conda/envs/pytesting/bin/python` (Python 3.12.14, pandas
3.0.5, PyYAML 6.0.3, mutmut 3.5.0). All against `dd2b631` plus the uncommitted tree
described below.

| Gate | Result | Observed |
|---|---|---|
| `./tests/run-tests.sh fast` | 815 passed, mypy clean (87 files), ~22s | 2026-09-27 |
| `./tests/run-tests.sh long` | 272 passed, 94.7s, then the profile | 2026-09-27, load ~0.6 |
| `./tests/run-tests.sh mutation` | 1,369 mutants, 1,310 killed, 59 survived, 95.7% vs 94% floor, PASS | 2026-09-27 (`src/` unchanged since `61bb827`, so identical to the previous handoff's run) |
| `doc-counts --list` (skills `bin/`) | 9 numbers, 0 drifted | 2026-09-27 |
| `doc-examples` check on `docs/*.md` with `--setup tests/doc_files.py:documented_world` | 6 blocks, 0 different, 3s | 2026-09-27 |
| jobchain `tests/test_checks_unit.py` + `tests/examples` against this `src` | 136 passed, 52s | 2026-09-27, jobchain `0d0975a` |
| pyflakes on the 6 new case-local `.py` files | clean | 2026-09-27 |

Not run this session: `cov`, `perf`, `memory`, `profile` alone. Their last figures are in
the previous handoff (2026-09-26): cov 100% lines and branches, perf 6 passed at
`d7dc3c7`, memory 3 passed at `c4d6b0b`. They were not re-run, because `src/` has not
changed since `61bb827`.

Survivors by module (2026-09-27): `engine` 22, `registry` 13, `tables` 8, `report` 8,
`rules` 6, `registry_tables` 2. This session read the engine, registry and rules
survivors (findings in report 2). The rest were read on 2026-09-26.

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh long
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh cov
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh perf
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh memory
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh mutation   # ~4 min
~/work/ai/skills/bin/mutmut-survivors --python ~/.conda/envs/pytesting/bin/python \
    --preload pandas [--diffs] [-m jobcheck.engine]
~/work/ai/skills/bin/doc-counts --python ~/.conda/envs/pytesting/bin/python [--write]
~/work/ai/skills/bin/doc-examples --python ~/.conda/envs/pytesting/bin/python \
    --setup tests/doc_files.py:documented_world --path src --path examples --path tests docs/*.md
cd ~/work/ai/jobchain && JOBCHECK=~/work/ai/jobcheck/src \
    ~/.conda/envs/pytesting/bin/python -m pytest tests/test_checks_unit.py tests/examples -q
```

## What changed since the previous handoff

Commits, made by an earlier session after the previous handoff was written; neither
handoff recorded them:

- **`f068452`** Docs match the code again, and the doc tests now hold them to it. It
  rewrote about 1,100 lines of `docs/` and added `docs/concepts.md`, whose root-cause
  line contradicts `reporting.md` (report 1).
- **`dd2b631`** Adds `scripts/regen_docs.py`. Skills `bin/doc-examples` was committed 29
  seconds later to replace it (report 2).

### Uncommitted — another session's work, not this one's

Left by a session that wrote complex catalog cases on 2026-09-26. All tests pass with it
in place.

- `tests/examples/complex/{order-lines-two-root-causes-at-once,
  a-broken-check-among-real-failures, excusing-a-blank-field-silences-its-checks,
  job-manifest-with-per-row-paths}/` — four catalog cases (untracked). They carry their
  own checks, data and rules, and the last one has its own script with a context
  builder.
- `README.md`, `docs/testing.md` — counts for those cases: 76 cases in all, long 272,
  all 1087, catalog 50 = 19 simple / 17 moderate / 14 complex.
- `tests/examples/README.md` — a paragraph on the four cases. It misdescribes three of
  them (report 1).
- `pyproject.toml` — a `[tool.doc-counts]` block for skills `bin/doc-counts`, which is
  still **untracked in the skills repo**.
- `.agent/example-pain-points.md` — a friction log from writing those cases, untracked
  and not ignored, so a `git clean` deletes it. Its 25 entries were checked in report 1:
  the real ones became findings, and the rest were judged deliberate or documented.
- `.agent/HANDOFF.md` — this file.

This session also left `mutants/` from its mutation run in the project root. It is
gitignored, and goes stale with the next `src/` change.

## In flight — where the session stopped

The owner's last instruction was: **"Implement all silent issues, add the rest to future
work."** Nothing is edited yet. The session had sorted every finding across the three
reports and was reading `docs/future-work.md`'s layout. That layout is: bold-titled
paragraphs numbered F.nn, a "Known gaps" section, then "Considered and deliberately not
done". The last number used is F.45, so new entries start at F.46.

**Silent, to implement.** "Silent" means something goes wrong with no signal. The
classification is this session's reading of the instruction and has not been confirmed
with the owner.

1. Duplicate YAML keys: PyYAML keeps the last one, silently. This affects rule files
   (`rules.py:174`), setup files (`registry.py:451`) and the example run file
   (`examples/run_from_config.py`). The plan: one duplicate-refusing `SafeLoader`, as
   `_read_yaml` beside `resolve_input_file` in `paths.py`, used by both library loaders.
   The example needs its own small copy, because examples use only the public API.
2. Unknown keys in a `match` criterion are ignored (`rules.py:82-99`); a `negate: true`
   loaded and inverted the rule's intent. Refuse any key but `column` and `pattern`.
3. `_EMPTY_CONTEXT` (`engine.py:31`) is shared and mutable, so a check that caches a
   value on it leaks that value across rows and calls. Plan: `__slots__ = ()` on
   `RowContext` (`context.py:14`). First grep the tests and jobchain for code that sets
   attributes on a bare `RowContext()`.
4. A disable rule on a check with dependents silently switches off the whole chain.
   Plan: a new public warning, probably `warn_blocking_rules(rules)` in
   `registry_tables.py`, because it needs the dependency graph and `rules.py` must not
   import the registry. It should report dependents the rule does not itself disable:
   the shipped `error_rules.yaml` disables both `EMAIL_MISSING_AT` and its dependent, so
   it should stay silent. `main.py --rules-table` and the run file print it beside the
   shadow warnings. Add a sentence to `docs/configuration.md`. As a new export it needs
   an entry in `PUBLIC_NAMES` (`tests/test_api_contract.py`), a section in
   `interfaces.md`, and a catalog case that shows it. **It changes the uncommitted
   excusing case's output and its README's point ("warns about nothing").**
5. `rules` passed as a generator applies to the first row only. Add
   `rules = list(rules or [])` in `validate`, `registry_table` and `warn_shadowed_rules`.
6. `summarize_outcomes` (and `build_report` with `include` other than `"failures"`) given
   `validate_row` lists reports wrong counts silently. Plan: refuse rows whose outcome
   lists differ in length, which is cheap. Mind the perf gate, since
   `summarize_outcomes/4000` has only about 30% headroom. Also fix the docs.
7. Registering a `functools.partial` evicts `functools` from `sys.modules` on
   `clear_registry` (`registry.py:195`). Record `fn.func.__module__` for a partial, and
   skip names in `sys.stdlib_module_names`.
8. Concurrent `load_checks` can let a broken load succeed while another caller fails,
   and leaves `sys.dont_write_bytecode` stuck `True` (`registry.py:286-298`). Plan: a
   module-level `threading.RLock` around the whole call.
9. Escape sequences in data cells reach the terminal raw (`tables.py:82`). Plan: render
   C0/C1 control characters, other than the handled breaks and tab, visibly in
   `_cell_lines`, and leave the CSV data alone.
10. `scripts/regen_docs.py` with a filter that matches nothing exits 0. It should exit 2
    with a message.
11. Test gaps that let silent regressions through:
    - `validate_row` passing its context: assert `seen[0] is context` in
      `tests/test_validate_row_unit.py:113`.
    - A two-argument builder receiving the row: record `row["a"]` in
      `tests/test_validate_unit.py:151`.
    - `warn_shadowed_rules` with `continue` changed to `break`: add a test whose first
      code has no `match: all` rule.

**The rest, to add to `future-work.md` as F.46 onward:**
- A raising context builder aborts `validate` (`engine.py:247`). This is the high
  finding, and needs the owner's decision: record it as errored, or document that a
  builder must not raise.
- The "downstream" root-cause wording (`concepts.md:49`, `interfaces.md:273`,
  `engine.py:178`), and `root_cause_rows` counting errored rows.
- `regen_docs.py` duplicating `doc-examples`.
- Four error messages the tests don't pin word for word.
- Two stale comments in `registry.py` (lines 24-26 and 269-271).
- A defaulted second check parameter being handed the context.
- YAML boolean messages: `name: off` reads as `False`.
- Five false docstrings.
- Wide-character column alignment.
- The mypy rule that case-local `.py` basenames must be unique across `tests/`.
- `doc-counts` uncommitted in skills.
- The misdescriptions in the uncommitted catalog cases: `tests/examples/README.md:15`,
  and "two of them" in `check_order_total.py:3` and its README.

**Open question for the owner — ask before committing.** The uncommitted catalog work
belongs to another session. Items 4 and 11 change files it also touched:
`docs/testing.md` counts, and the excusing case's output. There are two options:
- Commit that work first as its own commit, then this work on top.
- Stage only this session's changes, hunk by hunk, with `git apply --cached`.

Interactive staging is not available here. The pre-commit hook tests the working tree,
not the index.

## Not addressed — the real to-do list

Carried from the previous handoff:

- **The flaky scaling test**: `test_building_a_report_scales_with_the_failures_not_the_rows`
  (`tests/test_scaling.py:120-147`). It failed 2 of 7 runs under load on 2026-09-25, and
  passed once this session (2026-09-27, load ~0.6). Not investigated.
- **`paths.resolve_input_file`** has no underscore, and `paths` is still exempted in
  `INTERNAL_MODULES`. Not checked this session; recorded 2026-09-26.

New this session:

- **A `creadme` audit of `docs/`**: `f068452` rewrote about 1,100 lines, and the doc
  tests don't check prose claims.
- **A property test for the rule parser over generated YAML text**. `tests/test_fuzz.py:93`
  dumps structures, so it can never produce a duplicate key, an unquoted boolean or an
  unknown criterion key.
- **Python 3.10 with pandas 2.1**, the declared floors, has never been run here: there is
  no such interpreter. `Outcome` formatting already differs between 3.10 and 3.11+. Ask
  before installing anything.
- **The native `/code-review` pass** was not run in any of the three reviews.

Settled by standing preference, not open:
- Work stays on `simplify` and is not merged. The memory note's `claude` branch is 91
  commits behind and an ancestor of `simplify`; the project's own rule wins.
- Breaking the CLI or API is fine: no shims, and jobchain changes in the same step.
- No CI, and no changelog. The license is the owner's.
- American English everywhere.
- Held findings go to `future-work.md`, and are surveyed in full before being built.
- Every exported name needs an honest example.

## Tentative, not verified — carried

- **`registry._CHECKS.sort()`** leaves the cached order contradicting the graph.
  Reasoned, not reproduced. Carried from 2026-09-24; not checked this session.
- **A bundle that catches its own member's exception and carries on** was never tried.
  After `2304057`, a retry in-process would hit "Duplicate check code". Carried from
  2026-09-22; not checked.
- **Inline rules in a setup file remain a defensible design** (rejected 2026-09-24).
  Not revisited.

## Considered and deliberately not done

Everything in `docs/future-work.md` under "Considered and deliberately not done" still
stands, including B, C, J, the atomic per-call load, `render(title=)`, `add_columns`
restoring hidden report columns, and plain outcome strings (all 2026-09-25/26).

Checked this session and judged deliberate or documented, so not raised as findings:
- The report's key column is headed `row` (`reporting.md:49`).
- Exit 0 with failures or errors (`cli.md:267`).
- An errored line carries the check's message (`reporting.md:54`).
- A check returning a non-`Verdict` raises unconditionally, even under `"record"`
  (`interfaces.md:252`, `architecture.md:231`).
- `main.py` reads `NA`, `null`, `None` and the like as missing (`cli.md:48-51`).
- `yaml.YAMLError` propagates unwrapped (`interfaces.md:201`).
- The summary's tie order, and `disabled` outranking `skipped`.

## Decisions worth knowing before changing things

Carried from 2026-09-25 and 26, still true at `dd2b631`:
- Titles live in `attrs["title"]`.
- `_DEFAULT_COLUMNS` is the one place to set which columns show.
- `Outcome` is `(str, Enum)`, so text needs `.value`.
- A failed `load_checks` is not rolled back.
- `clear_registry` never evicts `__main__`.
- Messages are pinned in `tests/test_error_messages_unit.py`, but not all of them word
  for word (report 2).
- `__all__` must equal `PUBLIC_NAMES`.
- jobchain's `_ENGINE_NAMES` lists what jobchain needs.

New:

- **`clear_registry` evicts whatever module a registered callable reports.** That is
  documented as the price in `architecture.md:186-200`, but for a partial it is
  `functools` (report 2).
- **Without a builder, every row of every call shares one `RowContext`** (F.6, chosen
  for type consistency). Report 3 shows why that is unsafe once checks cache values on
  it.

## Measurements

- Mutation: 1,369 mutants, 95.7%, 250s wall clock; the same as 2026-09-26 (2026-09-27).
- Long suite: 94.7s at load ~0.6 (2026-09-27).
- `doc-examples` on `docs/`: 3s for 6 blocks, each in its own interpreter (2026-09-27).
- jobchain check tests against this `src`: 52s (2026-09-27).
- Size: `pyloc` on `src/jobcheck/*.py` gives 1,084 executable lines in 10 files
  (2026-09-27).

## Environment and housekeeping

- Use `PYTHON=~/.conda/envs/pytesting/bin/python` for everything except the pre-commit
  hook, which runs the fast suite under anaconda `python3` 3.14. Never install anything
  without asking.
- Generated and gitignored: `.build/`, `.agent/reviews/`, `mutants/` (present now),
  `.mutmut-cache`.
- The sibling worktree `~/work/ai/jobcheck-main/` is on branch `main`.
- Hand probes from this session are in the session scratchpad, outside the repo, and
  will not survive it. What they showed is written into report 3.

## Things that will bite

Every trap in the previous handoff still applies:
- mutmut needs pandas preloaded, and a stale `mutants/` lies.
- The long suite refuses to run without hypothesis.
- Regenerating is not fixing: read the diff.
- Never run two timing suites at once. Use `bgrun`.
- Every python block in `docs/` runs.
- Use `git add -A ':!.agent/HANDOFF.md'`.
- A scripted rename reaches strings.
- mypy rejects two files with the same name.
- An API change needs jobchain changed in the same step.
- The documented suite sizes move with nearly every commit.
- The docs checkers read a backticked `ALL_CAPS` word as a check code.
- The mutation mode ignores mutmut's exit status.
- `setdefault` evaluates its default argument every call.
- Run `regen_catalog.py` after any output change.
- `perf` records a renamed key as a new baseline.
- `subst` applies all edits or none.

New:

- **`git add -A` now sweeps in another session's work.** Stage by path.
- **Case-local `.py` files are checked by mypy as top-level modules.** A second
  `check_job_paths.py` anywhere under `tests/` fails the fast suite with
  `Duplicate module named ...` (reproduced 2026-09-27).
- **The catalog's `rglob("cmd")` makes any file named `cmd` under `tests/examples/` a
  case.**
- **PyYAML reads unquoted `on`, `off`, `yes` and `no` as booleans.** A probe rule named
  `off` failed with "every rule needs a non-empty string 'name'".
- **`regen_docs.py nosuchname` exits 0 having done nothing.** A typo'd filter looks
  like success.
