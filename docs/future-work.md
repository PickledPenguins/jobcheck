# Future work

Back to the [README](../README.md).

Known gaps, work that is planned, and — the part that earns this document its place —
what was **considered and deliberately not done**, with the reason. Without the last
section every review re-proposes the same rejected idea and every session re-derives the
same answer.

Open findings live in `.agent/reviews/` when a review has run; what a session was in the
middle of lives in `.agent/HANDOFF.md`. This file is for questions that are closed.

## Known gaps

**F.1 — `lint`, `parallel` and `params` exist only as bytecode.** Three modules were lost
when the repository was re-initialized on 2026-09-09. Their `.pyc` files, and the
interface read out of them, are on `main`: `git show origin/main:recovery/README.md`
records what each did and the reason to rebuild it, and
`git restore --source=origin/main -- recovery` brings the whole directory back. None is
rebuilt because nothing calls them today. `lint` is the one with obvious value — warnings
about rule files that parse but can never fire, fire everywhere, or were superseded.





The items below were raised by the 2026-09-15 and 2026-09-21 reviews, each sniff-tested
against the code and, where a behavior is involved, reproduced. The owner chose on
2026-09-21 to record them here rather than build any of them yet. Each says what the fix
would be, so a later session can take one without re-deriving it.

**F.4 — `print_report(fmt="csv")` on an empty report prints `No failures.`, not a CSV
header.** `src/jobcheck/report.py:219`. Two catalog READMEs
(`tests/examples/data/clean-file-as-csv`, `complex/clean-file-every-rule-csv`) promise the
header and their recorded output shows the prose. Fix: print the header line alone in CSV
mode, so a piped CSV is always a valid file; regenerate the two cases and read the diff.
The alternative is to correct the two READMEs.

**F.5 — A rule pattern never matches an integer column once the frame has a float
column.** `src/jobcheck/rules.py:213`. Reproduced on pandas 3.0.5: `iterrows` upcasts the
row to float when any column is float (an integer column with one blank is enough), so
`cell_text` sees `101.0` and `^102$` fails silently. An all-integer frame is unaffected.
Fix: render whole floats without the `.0` in `cell_text` (sharing `report._format_cell`
through `tables.py`), document it in [configuration.md](configuration.md), and add the
regression test through `validate` on a numeric frame — the existing matching test builds
its `Series` by hand, which is why this escaped.

**F.6 — `validate` hands checks `RowContext()`; `validate_row` and `explain_row` hand
`None`.** `src/jobcheck/engine.py:113`. Reproduced: the same check sees `RowContext` from
`validate` and `NoneType` from the per-row calls. Both sides are pinned
(`test_ctx_defaults_to_none`, `test_validate_without_a_builder_hands_every_row_a_bare_context`).
Fix: substitute `RowContext()` for `None` in `explain_row`, flip the one test, and note it
in [interfaces.md](interfaces.md).

**F.7 — A newline inside an unwrapped cell breaks the bordered table.**
`src/jobcheck/tables.py:47`. `_cell_lines` returns `str(value)` unchanged for a column
with no wrap width, so a row key or an `extra_columns` value holding `\n` prints as a
broken row. Wrapped columns are immune because `textwrap` collapses whitespace; CSV is
immune because pandas quotes. Fix: split on newlines in `_cell_lines` so the value
renders as a tall cell, as a wrapped one does.

**F.8 — The deep-chain error reports width, not depth.** `src/jobcheck/registry.py:352`.
`deepest declared depends_on: N` is `max(len(check.depends_on))`, the widest fan-in, not
the longest chain. Fix: report the deepest layer, or reword to `widest`; one exact-text
test in `tests/test_error_messages_unit.py` moves with it.

**F.9 — Regex matching has no bound.** `src/jobcheck/rules.py:226`. A rule pattern with a
nested quantifier (`(a+)+$`) on a 30-character cell runs for minutes inside `rule_matches`
with nothing to stop it and no message naming the rule; `tests/test_safety.py` pins that a
23-character value returns in under five seconds, and says so. Rule files are the owner's
configuration, so the exposure is a hung run, not an attack. Two shapes: a load-time
refusal in `parse_match` of patterns with a nested quantifier, naming the rule (about 15
lines, one rejection case in `tests/test_overrides_unit.py`, one case in
`tests/failures/`), or a stated non-goal in [configuration.md](configuration.md) with the
30-character figure beside it.

**F.10 — `register_check` records the registering module for `clear_registry` to evict.**
`src/jobcheck/registry.py:167`. Every module that registers a check by plain import is
popped from `sys.modules` on `clear_registry`, which is why a `@dataclass` defined inside
a test function under `fresh_registry` fails (the test module itself is evicted). No test
pins the behavior; a mutant that records `None` instead survives. Fix: either pin it with
a test that imports a module by hand, registers, clears and asserts the eviction — which
makes the trap a decision — or drop the line and evict only what `load_checks` imported,
which removes the trap and is a behavior change for an adopter who relies on a re-import
re-registering.

**F.11 — The internal-test exemption case shows nothing.**
`tests/examples/overrides/internal-test-accounts-exempted` is byte-identical to
`data/validate-a-csv-file` because `qa@internal.test` passes both email checks on its
own. Fix: in `scripts/make_example_data.py`, give one internal row a domain the check
rejects, regenerate the data, the catalog and the golden files, and read the diff —
roughly twenty expected outputs move.

**F.12 — 33 of 42 example READMEs omit the exit code from `Expected:`.** The other nine
state it. Fix: add the line to the 33, in the wording the nine use.

**F.13 — Seven `large-export` catalog cases are 1.1 MB of the catalog's 1.6.**
`tests/examples/data/large-export-*` and `complex/large-export-*` over the 2,000-row file.
Options: keep two and drop five, or truncate the recorded output. Volume is the point of
those cases, which is the argument for leaving them.

**F.14 — `scripts/new_catalog_case.py` refuses a duplicate command but not a duplicate
output.** Two cases with different commands and byte-identical recorded output are one
case filed twice; one such pair got in that way. Fix: compare the recorded stdout against
every existing case before accepting.

**F.15 — Three timing ratios in `tests/test_scaling.py` use a single measurement.**
`tests/test_scaling.py:67`; the file's own `fastest` helper exists for the one that compares
two small measurements. Fix: best-of-N for the other three, at a cost of one to two
minutes on the long suite. They have not flaked; the ratios have room.

**F.16 — 55 test names and several helpers still say `test` where the vocabulary is
`check`.** Suite-wide, since the 2026-09-10 rename. A mechanical rename in one commit;
no behavior changes.

## Considered and deliberately not done

**A whole-frame `validate` that streams by default.** Rejected: the two ways to spend
memory are genuinely different jobs. `validate` keeps every outcome because the report,
the summary and the explanation all need them; `validate_row` keeps one row's worth for a
frame that will not fit. A single call that guessed would make the cheap case expensive or
the expensive case impossible.

**Parsing dates in the engine or the loader instead of in the check (was F.3).** Closed
2026-09-21. The example date checks called the scalar `pandas.to_datetime` per cell, which
on pandas 3.0.5 costs 455 µs against 1.5 µs for `pandas.Timestamp` on the same string;
measured over 4,000 rows, `validate` took 9.65s against 1.28s with identical outcomes, so
date parsing was 87% of every run and the perf gate could barely see the engine. Fixed in
the example by swapping the call. Converting date columns up front was rejected: the
engine has no column types, and a `datetime64` column changes what `cell_text` hands
override patterns (`2024-01-01 00:00:00` where the file said `2024-01-01`) and what the
report prints, so a rule that matched the input text silently stops matching. A check
converts the cell it reads; at 1.5 µs a cell there is nothing left to save.

**Rebuilding the eleven test modules that exist only as bytecode (was F.2).** Closed
2026-09-21. `recovery/recovered-tests-api.md` on `main` lists every test by name and
docstring (`git show origin/main:recovery/recovered-tests-api.md`). Six of the eleven
test code this branch does not have: `test_lint_unit` (76 tests), `test_parallel_unit`
(45), `test_parallel_integration` (7) and `test_params_unit` (26) cover the three modules
of F.1; `test_run_unit` (36) covers `ValidationRun`, `iter_traces` and the progress
callback, rebuilt at `c2a3851` and cut again at `fab967a`; `test_groups_unit` (20)
covers `check_group`, cut in the same pass. They come back only with the code. The other
five are superseded by name: `test_engine_unit` by `test_validate_unit` and
`test_validate_row_unit`; `test_error_messages` by `test_error_messages_unit` and
`test_report_unit` (its other fifteen tests are parallel, params and run messages);
`test_rules_unit` by `test_overrides_unit`, with its nine glob-matching tests obsolete
since `match` became regex; `test_benchmarks` by `test_perf` and `test_scaling`;
`test_examples` by `test_shipped_examples_unit`. Two individual tests have no successor:
a number is matched on how it prints (the F.5 regression test, written with F.5) and
matching is case-sensitive.

**A `load_tests` alias for `load_checks`.** Rejected 2026-09-10. The vocabulary here
is "check"; an alias in the old vocabulary would outlive its reason, and the one caller
that needed it (jobchain) was ported in the same pass.

**Inferring a report's format from the file extension.** Rejected: `--report` decides the
format for both the printed and the written report, and one flag with one meaning beats a
rule that applies only sometimes. A `.csv` file holding a rendered table is surprising, and
the CLI reference says so where it would surprise someone.

**Accepting the check-era rule format (a top-level `column`/`pattern` pair, globbed).**
Rejected: the current parser rejects those keys as typos, and ignoring them would disable
nothing while the author believed a code was switched off. Silence is the worse failure;
rule files get rewritten instead.

**Lowering the coverage floor when it was failing.** Rejected in the sibling project for
the same reason it would be rejected here: a floor that moves to meet the suite measures
nothing. The floor is 95% and the suite runs at 100%.

**Making the perf thresholds absolute numbers.** Rejected: a ceiling written on one
machine is either so loose it catches nothing or so tight it fails on a slower one.
`tests/test_perf.py` compares against a baseline recorded on the machine that runs it,
with the tolerance derived from that machine's own measured spread.

**Gating on the profile.** Rejected: a profile is a description. Turning one into a
threshold produces a flaky check and a number nobody trusts; the timing gate is the
assertion, and the profile says where the time went once it fires.

**Chasing the remaining mutation survivors to 100%.** Rejected with the evidence in
[testing.md](testing.md#mutation-testing): 21 of them are default-argument mutations
mutmut's own trampoline cannot execute, several are equivalent on this platform, and the
rest are print-function wording that the example catalog and the golden files pin byte for
byte — while mutmut cannot run either, because both shell out.

**Deduplicating the example catalog.** Rejected: two cases reaching the same code path
from different angles are two references, and the catalog is read by people looking for
something close to their own case. It is judged on variety, not on coverage.

**A CI workflow.** Not wanted. The pre-commit hook and the release gates in
[testing.md](testing.md#gates) are what run the suites; an absent workflow is not
outstanding work.

**Narrowing the registry table by breaking long words.** Rejected: the demo registry table
with `could_be_overridden_by` asked for is 150 columns, and the binding constraint is a
single 48-character rule name, not the wrap width. Breaking words at the wrap width takes
it to 138, and a `wrap_width` default applied to every column saves nothing at all (both
measured on 2026-09-11). A code or rule name split across two lines cannot be copied out
of the output, which is what `format_table`'s `break_long_words=False` is protecting; a
table 150 columns wide is read by scrolling, a mangled identifier is not read at all.
Renaming `default_state` to `default` was taken — it was 13 columns of heading for three
characters of data.

**Replacing `could_be_overridden_by` with a count.** Rejected, though it is the narrowest
option measured (107 columns) and matches what `print_override_rules` does with
`codes_hit_count`: the names are the reason the column exists. `print_override_rules` and
`list_rule_codes` already carry the detail for a reader who wants it by rule rather than
by code.

**Shortening the demo rule names.** Not done. Two are 48 characters
(`disable_age_integer_check_from_another_directory`), which is what makes the table as
wide as it is, but they are self-documenting in a directory whose whole job is to show a
reader what a rule file looks like. This is data in `examples/rules/`, not a library
limit — worth remembering before concluding the table cannot be narrower.
