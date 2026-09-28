# Handoff

Written 2026-09-28. Branch `simplify`, commit `64f7e25`, 114 commits ahead of `main`.
The tree is clean. Start at `README.md` and the documents its index links;
`.claude/CLAUDE.md` holds the project's history. The open work is `docs/future-work.md`,
"Known gaps", F.46 to F.62. The three review reports it came from are still in
`.agent/reviews/` (gitignored): `2026-09-27T14-13-04`, `14-40-45` and `15-11-05`, all
`claude-opus-5-5`. Every finding in them is now either fixed (`a4582e1`) or an F entry.
Deleting them is `caddressreview`'s call, and nobody has made it.

## State

Observed this session with `~/.conda/envs/pytesting/bin/python` (Python 3.12.14,
pandas 3.0.5, PyYAML 6.0.3, mutmut 3.5.0). `src/` is the same from the jobchain run
onward. Only tests and docs changed after that.

| Gate | Result | Observed |
|---|---|---|
| `./tests/run-tests.sh fast` | 862 passed, mypy clean (87 files), 22.6s | 2026-09-28, the tree committed as `a4582e1`; also the pre-commit hook (anaconda `python3`) on `a4582e1` and `64f7e25` |
| `./tests/run-tests.sh long` | PASS; 273 collected, per `doc-counts` | 2026-09-27/28, before the last survivor tests (which are fast-marked) |
| `./tests/run-tests.sh cov` | 858 passed, 100% lines and branches (1,165 statements, 418 branches) | 2026-09-28, before the 4 last survivor tests |
| `./tests/run-tests.sh perf` | PASS | 2026-09-28, final `src/` |
| `./tests/run-tests.sh memory` | PASS | 2026-09-28, final `src/` |
| `./tests/run-tests.sh mutation` | 1,525 mutants, 1,473 killed, 52 survived, 96.6% vs the 94% floor, PASS, about 302s | 2026-09-28, final `src/` and tests |
| `doc-counts --write` | 9 numbers, in step | 2026-09-28 |
| `doc-examples` on `docs/*.md` | 6 blocks, 0 different | 2026-09-28 |
| jobchain `tests/test_checks_unit.py tests/examples` against this `src` | 136 passed, 67s | 2026-09-28, jobchain `simplify` |

Survivors by module (2026-09-28): `engine` 13, `tables` 10, `paths` 9, `report` 9,
`registry` 9, `registry_tables` 2. The survivors in the new code were read. The rest are
equivalents: `deep=None`, codec letter case, a -2 sentinel, `utf-8` on a UTF-8 box, and
`break` after an unhashable key. `docs/testing.md` records them.

`doc-errors src` (2026-09-28): 35 of 60 messages are quoted in no document. That gap
predates this session and no test gates it. The one new message it flagged is now quoted
in `reporting.md`.

```sh
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh fast    # the commit gate
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh long
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh cov
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh perf
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh memory
PYTHON=~/.conda/envs/pytesting/bin/python ./tests/run-tests.sh mutation   # ~5 min
~/work/ai/skills/bin/mutmut-survivors --python ~/.conda/envs/pytesting/bin/python \
    --preload pandas [--diffs] [-m jobcheck.engine]
~/work/ai/skills/bin/doc-counts --python ~/.conda/envs/pytesting/bin/python [--write]
~/work/ai/skills/bin/doc-examples --python ~/.conda/envs/pytesting/bin/python \
    --setup tests/doc_files.py:documented_world --path src --path examples --path tests docs/*.md
~/work/ai/skills/bin/doc-errors src
~/.conda/envs/pytesting/bin/python scripts/regen_catalog.py [case-substring]
cd ~/work/ai/jobchain && JOBCHECK=~/work/ai/jobcheck/src \
    ~/.conda/envs/pytesting/bin/python -m pytest tests/test_checks_unit.py tests/examples -q
```

## What this session changed

- **`82d1a97`**: commits the 2026-09-26 session's catalog work as that session left it.
  That is four `tests/examples/complex/` cases, the counts, the `[tool.doc-counts]`
  block and `.agent/example-pain-points.md`. Someone other than session ai-41 had
  staged it at 23:27 on 2026-09-27; ai-41 said it never touched jobcheck.
- **`d281e76`**: commits the 2026-09-27 review handoff unchanged.
- **`a4582e1`**: fixes every silent finding. The owner's definition: "silent is any issue
  that the user would not be able to see".
  - Duplicate YAML keys are refused, through the strict `paths._read_yaml` that both
    loaders share. The run-file example has its own copy.
  - A `match` criterion with any key besides `column` and `pattern` is refused.
  - `RowContext.__slots__ = ()`.
  - New export `warn_blocking_rules`, printed by `main.py --rules-table` and by the run
    file.
  - `rules` is made a list once, in `validate`, `registry_table` and the rule warnings.
  - `summarize_outcomes`, and `build_report` with any `include` except `"failures"`,
    refuse outcome lists of unequal length.
  - A partial is unwrapped before its module is recorded for eviction, and
    standard-library modules are never evicted.
  - `_LOAD_LOCK` is an `RLock` held around `load_checks` and `clear_registry`.
  - `tables._visible` shows C0/C1 controls, DEL and bidi overrides as escapes, in cells
    and in headings. CSV output is unchanged.
  - `regen_docs.py` exits 2 when a name matches nothing.
  - Tests for the five untested contracts and the four partly pinned messages.
  - False wording corrected: "downstream", `root_cause_rows` counting errored rows, five
    docstrings, two comments, and the catalog descriptions.
  - The excusing case's expected output now includes the new warning.
- **`64f7e25`**: adds `docs/future-work.md` F.46 to F.62, everything not silent. F.6,
  F.7 and F.10 are amended to say what changed.

## In flight — where the session stopped

Nothing is half-done. The owner's next instruction: **"then work on future work
items"**. Under the standing preference (global `CLAUDE.md`), that means survey F.46 to
F.62 in detail and plan with the owner. Build nothing until told. The survey covers
seven points per item: the issue with file:line, the gain, the loss, SLOC and files,
priority, blast radius, and a recommendation.

Tentative, this session's reading and unconfirmed by the owner:
- F.46 is decided (document; see future-work.md). The survey of F.47 to F.62 was given
  to the owner on 2026-09-28, and F.47 is next.
- F.52 and F.53 are the two partial fixes. Each has a stronger version with a cost:
  - F.52: a marker on `validate_row`'s lists, or a comparison against the registry.
    Either would break the hand-built outcome lists in the tests.
  - F.53: skip `site-packages` modules, or record nothing for a callable object.
- Borderline classification. These were treated as not silent, because the user sees
  something, even if confusing. The owner may classify them otherwise:
  - F.51 (CSV control characters on a terminal)
  - F.52 (the equal-length gap)
  - F.53 (third-party eviction)

## Not addressed — the real to-do list

All of it is in `docs/future-work.md` "Known gaps", with the evidence:
- F.46: closed 2026-09-28. The owner chose to document the contract rather than record
  the row as errored; see "Considered and deliberately not done" in future-work.md.
- F.47: `is_root_cause`/`root_cause_rows` naming; whether errored rows count.
- F.48: a defaulted second check parameter receives the context.
- F.49: YAML booleans (`name: off`, `codes: [ON]`, `pattern: NO`) give messages with no
  hint.
- F.50: wide characters misalign the bordered table.
- F.51: CSV printed to a terminal keeps control characters.
- F.52: equal-length failures-only lists still pass the summary.
- F.53: `clear_registry` evicts a third-party callable object's module.
- F.54: `scripts/regen_docs.py` duplicates skills `bin/doc-examples`.
- F.55: case-local `.py` basenames must be unique across `tests/` (mypy).
- F.56: the flaky scaling test,
  `test_building_a_report_scales_with_the_failures_not_the_rows`. Carried from
  2026-09-25. It passed in this session's long run, and was not investigated.
- F.57: `paths.resolve_input_file` has no underscore. Carried from 2026-09-26; not
  checked this session.
- F.58: a `creadme` audit of `docs/`. More prose changed this session, so it matters more
  now.
- F.59: a property test for the rule parser over generated YAML text. It would also cover
  the new duplicate-key and criterion-key refusals.
- F.60: Python 3.10 with pandas 2.1 never run. Ask before installing.
  `email.utils.parseaddr`, used in `test_a_standard_library_callable_is_never_evicted`,
  may have a different signature on 3.10. Unverified.
- F.61: the native `/code-review` pass was never run.
- F.62: two tentative traps (`_CHECKS.sort()`, a bundle retrying its own member).

Settled by standing preference, not open:
- Work stays on `simplify` and is not merged. The memory note's `claude` branch is
  behind, and is an ancestor of `simplify`; the project's own rule wins.
- Breaking the CLI or API is fine: no shims, and jobchain changes in the same step.
- No CI, and no changelog. The license is the owner's.
- American English everywhere.
- Future work is surveyed and planned with the owner, then built only on "build/do/cut".
- Every exported name needs an honest example.

## Considered and deliberately not done

- Everything under "Considered and deliberately not done" in `docs/future-work.md` still
  stands.
- **Inline rules in a setup file** remain a defensible design; rejected 2026-09-24, not
  revisited.
- **Deleting `regen_docs.py`** was not done with the silent fixes. It is duplication, not
  a silent defect, so it is F.54.
- **Escaping control characters in CSV** was not done: a CSV file is data for another
  program (F.51).
- **Refusing all-failure lists in the summary** was not done: all checks failing on
  every row is legitimate, and refusing it would be a false error (F.52).
- Judged deliberate or documented on 2026-09-27, still standing:
  - The report's key column is headed `row` (`reporting.md`).
  - Exit 0 with failures or errors (`cli.md`).
  - An errored line carries the check's message.
  - A non-`Verdict` return raises even under `"record"`.
  - `main.py` reads `NA`/`null`/`None` as missing.
  - `yaml.YAMLError` propagates unwrapped.
  - The summary's tie order, and `disabled` outranking `skipped`.
- **`doc-counts` untracked in skills** (a 2026-09-27 finding) is closed: it is committed
  as skills `39c31af` (observed 2026-09-27).

## Decisions worth knowing before changing things

Carried from 2026-09-25/26, still true at `64f7e25`:
- Titles live in `attrs["title"]`.
- `_DEFAULT_COLUMNS` is the one place to set which columns show.
- `Outcome` is `(str, Enum)`, so text needs `.value`.
- A failed `load_checks` is not rolled back.
- `clear_registry` never evicts `__main__`.
- `__all__` must equal `PUBLIC_NAMES` (`tests/test_api_contract.py`).
- jobchain's `_ENGINE_NAMES` lists what jobchain needs.

New, 2026-09-28:
- **The base `RowContext` refuses attributes.** Without a builder every row shares one
  instance, so caching per row needs a builder that returns a fresh subclass instance.
- **`warn_blocking_rules` stays quiet about a dependent that the same rule lists.**
  Listing a dependent is how a rule author says the silence is meant; the shipped
  `error_rules.yaml` relies on this. A code below another code in the same rule is not
  reported twice. Dependents that are off by default are still named.
- **`build_report(include="failures")` accepts `validate_row` lists on purpose.** It
  reads only failures. Only the other levels, and the summary, refuse unequal lengths.
- **Eviction records `_module_to_evict(fn)`, but the error-message label still uses the
  raw `fn.__module__`.** This keeps the "registering __main__.x" wording.
- **`_LOAD_LOCK` is reentrant** because a bundle calls `load_checks` from inside one. A
  check file that starts a thread which calls `load_checks`, and then joins it, would
  deadlock. That was judged not worth guarding.

## Measurements, so they are not re-derived

- Mutation: 1,525 mutants, 96.6%, about 302s wall clock (2026-09-28). At 2026-09-27 it
  was 1,369 mutants, 95.7%, 250s.
- Fast suite: 862 tests in 22.6s (2026-09-28).
- jobchain check tests against this `src`: 67s (2026-09-28). The same tests took 52s on
  2026-09-27, both with another session's suite running beside them.
- The new load-race test waits 0.3s by design (long-marked, `tests/test_concurrency.py`).

## Environment and housekeeping

- Use `PYTHON=~/.conda/envs/pytesting/bin/python` for everything except the pre-commit
  hook. The hook runs the fast suite under anaconda `python3`. Never install anything
  without asking.
- Generated and gitignored: `.build/`, `.agent/reviews/`, `mutants/` (present now, from
  the 2026-09-28 run), `.mutmut-cache`.
- The sibling worktree `~/work/ai/jobcheck-main/` is on branch `main`.
- Other sessions work in `~/work/ai` at the same time (ai-41 was on xtm). This repo's
  index changed under this session once; check `git status` before staging.

## Things that will bite

Carried, all still true:
- mutmut needs pandas preloaded, and a stale `mutants/` lies.
- The long suite refuses to run without hypothesis.
- Regenerating is not fixing: read the diff.
- Never run two timing suites at once. Use `bgrun`.
- Every python block in `docs/` runs.
- A scripted rename reaches strings.
- mypy rejects two files with the same name, and treats case-local `.py` files in
  `tests/examples/` as top-level modules.
- An API change needs jobchain changed in the same step.
- The documented suite sizes move with nearly every commit. Run `doc-counts --write`.
- The mutation mode ignores mutmut's exit status.
- `setdefault` evaluates its default argument every call.
- Run `regen_catalog.py` after any output change.
- `perf` records a renamed key as a new baseline.
- `subst` applies all edits or none.
- The catalog's `rglob("cmd")` makes any file named `cmd` under `tests/examples/` a
  case.
- PyYAML reads unquoted `on`/`off`/`yes`/`no` as booleans.

New, 2026-09-28:
- **The docs checkers read every backticked `ALL_CAPS` word as a check code, and every
  backticked `name(` as a call.** This includes `docs/future-work.md`: `INTERNAL_MODULES`,
  `RUN_DIR_PRESENT` and `build(row, ...)` each failed the fast suite. Write such names
  without backticks.
- **`subst` counts a literal `\x85` in a file as a line break**, so a sized `region N`
  block miscounts. `tables.py` held one in a comment until this session. Use an unsized
  region.
- **The fast suite passes before a doc edit and fails after it.** `cov` caught
  future-work lines that the fast run before them never saw. Re-run after the last doc
  edit, not before.
- **The server-side permission check for Bash sometimes returns no verdict.** Read-only
  work through Read still works; retry Bash later.
