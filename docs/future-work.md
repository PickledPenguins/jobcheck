# Future work

Back to the [README](../README.md).

Known gaps, work that is planned, and — the part that earns this document its place —
what was **considered and deliberately not done**, with the reason. Without the last
section every review re-proposes the same rejected idea and every session re-derives the
same answer.

Open findings live in `reviews/` when a review has run; what a session was in the middle
of lives in `HANDOFF.md`. This file is for questions that are closed.

## Known gaps

**F.1 — `lint`, `parallel` and `params` exist only as bytecode.** Three modules were lost
when the repository was re-initialised on 2026-09-09 and survive only in
`recovery/bytecode/`. `recovery/README.md` records what each did and the reason to
rebuild it; none is rebuilt because nothing calls them today. `lint` is the one with
obvious value — warnings about rule files that parse but can never fire, fire everywhere,
or were superseded.

**F.2 — Eleven test modules from the same era are also unrebuilt.**
`recovery/recovered-tests-api.md` lists what each asserted, by name and docstring. The
current suite covers most of the same surface; `test_error_messages` and `test_rules_unit`
are the two whose subjects are now covered from a different angle rather than directly.

**F.3 — Dates dominate the profile.** `explain_row` is about 85% of a validation run, and
inside it the example suites' `dates_present` and `dates_in_order` are roughly 40% of the
total, because both call `pandas.to_datetime` per row. That is example code rather than
library code, so it costs an adopter nothing — but it is what a reader of
`./run-tests.sh profile` will see first, and it is worth knowing it is not the engine.

## Considered and deliberately not done

**A whole-frame `validate` that streams by default.** Rejected: the two ways to spend
memory are genuinely different jobs. `validate` keeps every outcome because the report,
the summary and the explanation all need them; `iter_traces` keeps one row's worth for a
frame that will not fit. A single call that guessed would make the cheap case expensive or
the expensive case impossible.

**A `load_checks` alias for `load_test_files`.** Rejected 2026-09-10. The vocabulary here
is "test"; an alias in the old vocabulary would outlive its reason, and the one caller
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
threshold produces a flaky test and a number nobody trusts; the timing gate is the
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
