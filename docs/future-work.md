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



























**F.17 — no search path for check and rule files.** `base_dir` (2026-09-22) anchors a
relative path to one directory the caller names. What it does not serve is the
deployment case: check files installed in a shared location, named bare by a run
configuration that does not know where they were installed. That wants a list of
directories tried in order -- an environment variable, or an argument -- and first match
wins. Not built, because it is discovery, which this library refuses everywhere else: two
files of one name in two entries means the wrong checks run and nothing says so, and an
environment variable makes a run irreproducible from its command line. Estimated ~45
source and ~130 test lines. Decide it deliberately if the deployment case turns up; do
not add it as a convenience.

The ten items below came out of the two reviews of 2026-09-23, were sniff-tested against
the code, and were held rather than fixed because each changes behavior, an API, or needs
a design call the owner has not made. The reviews' own fixes to the same commit are in the
git log; these are what was deliberately left. Each says what would be gained, what would
be lost, the size, and the recommendation, so none has to be re-derived.

**F.19 — `restore` puts back the registry but not the module cache.** `restore` calls
`clear_registry` first, which pops every recorded module out of `sys.modules`, then
re-declares those same names from the snapshot without re-importing anything. Probed
2026-09-23: after a load of `examples/checks/check_age.py`, a `snapshot`, a
`clear_registry` and a `restore`, the registry holds all five age checks and the module
set names `jobcheck_check_file_check_age_0`, while `sys.modules` holds nothing at all. The
checks still run, because the runners are closures over the author's functions. Gain:
`restore` would match its docstring, "Put back a registry `snapshot` took". Loss if left:
anything that resolves a check function's module after a restore gets a `KeyError` or the
wrong answer — `pickle` for a worker pool, `inspect.getmodule`, and the `dataclasses`
annotation resolution `architecture.md` already documents as a trap for `clear_registry`;
`fresh_registry` runs this pattern around most of the suite, so the state is common.
Loss if fixed by behavior: `restore` would have to either keep the modules alive across
the clear (a second eviction rule to explain) or re-import the files (which re-runs
arbitrary user code inside what is documented as a pure state swap, and would double-
register). Doc-only: 3 lines. Behavior: ~15 source lines and a new rule about what
`restore` may execute. Priority: medium. Blast radius: `restore` is public and used by
every test that takes `fresh_registry`. Recommendation: document it — say the module cache
is not restored and point at the `clear_registry` note in `architecture.md`. Re-importing
inside `restore` is the wrong shape; keeping modules alive is worth considering only if
someone actually pickles a check.

**F.20 — `examples/bundle_main.py` has no argument parsing.** It reads `sys.argv[1:]` and
takes element zero as a bundle path, so `python3 examples/bundle_main.py --help` exits 1
with `ValueError: No check file at '--help'`, and a second path argument is dropped with
no message and exit 0. `docs/cli.md` documents `-h`, `--help` for `examples/main.py` two
sections above, so the convention is taught and then broken by the sibling. Gain: `--help`,
a usage line, and an error for too many arguments, all from four lines of `argparse`; the
silent drop stops. Loss: `docs/cli.md` currently says "No flags; one optional argument",
which would have to change, and the failures catalog would want a case for the
too-many-arguments error — both small, but they are why this is not a one-line edit. There
is also a deliberate reason for the current shape: the file is a *minimal* second entry
point, and `argparse` is the thing `examples/main.py` already demonstrates. ~10 source
lines, 1 doc section, 1 or 2 catalog cases. Priority: medium — it is the first thing a
junior types at an unfamiliar command. Blast radius: one example entry point, one doc
section, the catalog. Recommendation: do it. A shipped entry point that answers `--help`
with a traceback teaches the wrong thing about a library whose error messages are
otherwise this careful.

**F.21 — the `sys.path` bootstrap is written eight times, three ways.** `tests/conftest.py`,
`tests/test_docs_unit.py`, `tests/test_concurrency.py`, `examples/main.py`,
`examples/bundle_main.py`, `scripts/regen_catalog.py`, `scripts/regen_golden.py`,
`scripts/profile_examples.py` and `scripts/new_catalog_case.py` each compute the clone root
and put some subset of `src`, `examples`, `tests` and the root itself on the path. The root
is `PROJECT_ROOT` in some and `ROOT` in others, `os.path` in some and `pathlib` in others,
and no two insert the same set. Gain: one place to change when the layout moves, and one
name for one concept, which is the rule `contributing.md` states. Loss: the two files under
`examples/` must keep their own copy whatever happens — they are what an adopter copies, and
a demo that imports a private test helper to find its own package is worse than a repeated
three lines. So the de-duplication can only ever cover six of the eight, which weakens it:
a reader still meets two spellings, and now also has to know which files are allowed to use
the helper. ~25 source lines removed, ~15 added, 6 files touched. Priority: low — it has
never caused a failure. Blast radius: import bootstrapping for the whole suite and every
script; a mistake here is a collection error, loud and immediate. Recommendation: do the
smaller half instead — make the six agree on the name `ROOT` and on `pathlib`, and leave
them separate. The shared helper buys less than it costs once the two entry points are
carved out.

**F.22 — two private-by-name helpers in `tables.py` are package-internal API.** The cell
formatter and the extra-columns validator carry a leading underscore and are imported by
`rules.py`, `report.py` and `registry_tables.py`; `format_table` and `is_null`, in the same
file and used the same way, carry none and are exported from `__init__.py`. A reader cannot
derive the rule, and the underscore is the only signal a junior has for "do not call this
from elsewhere". Gain: the convention becomes legible — either the underscore means
"not public API" and is documented as such, or the two helpers are named like the rest of
the file. Loss if renamed: they would look exported without being in `__all__`, which is a
different confusion, and `test_api_contract.py` checks that the public surface is complete
and sorted — a public-looking name that is deliberately absent from `__all__` is a new
exception to explain there. 5 lines if documented; ~12 lines across 4 files if renamed.
Priority: low. Blast radius: three modules and their unit tests; no behavior. Recommendation:
document rather than rename. One sentence in `tables.py`'s module docstring saying an
underscore there means "internal to the package, not to this file" costs nothing and does
not disturb the export contract.

**F.23 — the test suite's module aliases.** `tests/conftest.py` imports the package's
modules as `eng`, `reg` and `res`, and roughly twenty test modules use them. The package
itself spells everything out, and `contributing.md` names the junior reader as the bar.
Gain: one vocabulary across source and tests. Loss: the rename touches every test file that
uses them, which is a large diff with no behavior change — it makes `git log -S` and
`git blame` on the suite worse for a year to buy a spelling. 3 lines in `conftest.py`,
~200 touched lines across ~20 files. Priority: low. Blast radius: tests only. Recommendation:
do not do it on its own. If the suite is ever split or reorganized, spell them out in the
files that move, and let the rest converge.

**F.24 — the enabled-state lookup carries a fallback nothing explains.** `engine.py`'s
per-row loop reads each check's state with a dict `get` and a default, but the dict is
built from the same registry list the loop walks, in the same call, so the default cannot
fire unless the cached evaluation order is stale with respect to the registry — the exact
state the cache invalidation exists to prevent. A `get` default is not a branch, so the
100% branch figure does not cover it, and no test reaches it. Gain: either the reader
learns in one line what the fallback guards, or the guard goes and a stale cache raises
where it happens instead of silently running a check under its declared default. Loss if
the default is dropped: a stale cache becomes a `KeyError` from inside the row loop rather
than a quietly wrong-but-plausible run. That is the right trade for a library that refuses
to guess elsewhere — but it converts a silent state into a crash, which is a behavior change
and needs the owner's word. 1 line either way; ~15 test lines if the raise is asserted.
Priority: low. Blast radius: the per-row loop, which is every validation. Recommendation:
drop the default and index directly, with a test that a stale cache raises. The silent path
is the one this project would not accept anywhere else.

**F.25 — `print_report` returns nothing while its four siblings return their frame.**
`registry_tables.py`'s module docstring states the convention — every function returns the
DataFrame it prints, so a caller can take the data without the output — and
`print_registry`, `print_override_rules`, `print_summary` and `print_row_explanation` all
follow it. `print_report` returns `None`, and `report.py`'s module docstring does not
mention the convention, so a reader meets the rule only by opening the other file. Gain:
one rule, stated in both files, and a caller that prints and keeps the frame without
building it twice. Loss: it is a public API change. Additive — nothing can depend on
`None` — but `interfaces.md` documents the return, `test_api_contract.py` checks
signatures, and the golden and catalog outputs would need re-reading to confirm nothing
prints twice. ~4 source lines, 2 doc lines, ~10 test lines. Priority: low. Blast radius:
one exported function's signature and its documentation. Recommendation: do it with the
next API change rather than alone, and state the convention in `report.py`'s docstring at
the same time.

**F.26 — the catalog's stable-root fallback swallows more than its comment admits.**
`tests/catalog.py` creates a fixed-length symlink to the clone so the recorded column
widths do not depend on where the repository sits, and falls back to the real root inside
an `except OSError` marked `# pragma: no cover - no symlinks on this filesystem`. That
handler also catches the `FileExistsError` two runs in one clone produce by racing between
the unlink and the symlink call: the fallback then returns the real root, the rendered
paths change width, and the byte-for-byte cases fail with a padding diff the comment blames
on the filesystem, while the pragma tells coverage never to look. Gain: a concurrent run
stops producing a failure that reads as somebody else's fault. Loss: the fix is either a
narrower `except` plus a re-read of the link, or creating the link under a unique name and
`os.replace`-ing it, which is atomic — the second is right but adds a temporary name to a
directory shared by every clone of every user, which is what the current zero-padded name
scheme was carefully built to avoid. ~12 lines in one file. Priority: low — the handoff
already says not to run two timing suites at once, and the catalog is not a timing suite
but shares the constraint. Blast radius: the 64 catalog cases, and only when two runs of
one clone overlap. Recommendation: do the atomic-replace version, and narrow the comment to
say what it is excusing. The pragma should move to whatever is genuinely unreachable.

**F.27 — no gate on line width.** `contributing.md` states "Lines stay under 100
characters. Nothing enforces it -- there is no linter here -- but the package sits under
it". On 2026-09-23 it did not: two lines were 101 and 103 characters. They were wrapped, and
nothing stops the next two. Gain: the one style rule with no enforcement gets one, in the
file that already enforces the other layout rules. Loss: a width check has to decide what it
covers — the package only, or the tests and scripts too, where several long lines are
deliberate table rows and error-message literals — and a gate that has to carry exceptions
is worth less than the rule. ~20 test lines. Priority: low. Blast radius: the fast suite; a
false positive blocks a commit. Recommendation: add it for `src/` and `examples/` only,
where the rule is actually claimed, and leave `tests/` and `scripts/` out rather than
writing an exception list.

## Considered and deliberately not done

**Carrying the in-progress load stack through `snapshot` and `restore`** (F.18, decided
2026-09-23). The registry's frame stack -- the check files whose import is in progress,
each with the checks it registered -- is the one piece of registry-module state the
snapshot dict does not copy, and `clear_registry` does not clear it either. Carrying it
was rejected: `restore` would then reinstate a *mid-load* registry, a state the rest of
the module assumes it never sees. The stack is read by `register_check` and by the
per-file rollback, so a frame put back from a load that has since finished would take the
blame for the next file's checks, and that file's rollback would drop checks belonging to
somebody else -- a worse failure than the one being fixed, and one that needs a decision
nobody has had to make about what a restore *means* during a load. The docstrings on
`snapshot`, `restore`, `clear_registry` and `RegistryState` now say the supported case
instead: a registry between loads, never during one, and a check file that snapshots while
a bundle above it is still importing is unsupported. The rest of F.18 -- the load-sequence
counter, which is registry state with no mid-load meaning -- was built in the same change.

**Anchoring relative paths on the caller's script directory, automatically** (considered
2026-09-22, when `base_dir` was built). Frame inspection -- `sys._getframe(1)` --
reads the directory of whoever *called* the loader, which is not whoever wrote the paths:
jobchain calls `load_checks` from `jobchain/checks.py`, so every relative path in a user's
run configuration would have anchored to jobchain's own library directory. It also has no
answer under `-c`, a REPL, `exec` or a frozen application. `base_dir` says the same thing
at the call site, where a reader can see it.

**Anchoring on a discovered project root** (`.git`, `pyproject.toml`), same session. The
marker does not exist in the deployment case -- an installed tool run over a data
directory has neither -- so the rule would silently fall back to the working directory and
behave differently in production than on the machine it was written on.

**Accepting importable module names, `load_checks(["mypkg.checks.age"])`**, same session.
It is the literal reading of "use the Python path" and it collides with `clear_registry`,
which drops every module that registered a check out of `sys.modules`: doing that to a
real package module leaves other holders of it stale and re-imports it as a second,
distinct module -- a new way to get the silently empty registry the eviction exists to
prevent.

**A whole-frame `validate` that streams by default.** Rejected: the two ways to spend
memory are genuinely different jobs. `validate` keeps every outcome because the report,
the summary and the explanation all need them; `validate_row` keeps one row's worth for a
frame that will not fit. A single call that guessed would make the cheap case expensive or
the expensive case impossible.

**Test names left in the `test` vocabulary (was F.16).** Fixed 2026-09-22. 53 test
function names (F.16 counted 55; the suite has moved) plus five helpers and constants
said `test` where they meant a registered check: the check-file template constant in
`test_concurrency.py`, `test_faults.py` and `test_load_files_unit.py`, the helper that
writes one, and the inner function of `conftest.make_check`. Renamed segment by segment,
keeping every `test_`
prefix pytest collects on and every `test` that means a pytest test — the `Tests that
want a single label per row` in `conftest.first_cause` is one of those and stayed. No
document named any of them, so nothing outside `tests/` moved. 18 files, 85 lines, no
behavior change.

**Best-of-N for the three single-measurement scaling ratios (was F.15).** Half taken
2026-09-22: all three now warm up each side with the `fastest` helper at `repeats=1`, and
best-of-five
is rejected. Why they had not flaked, which F.15 did not record: each measures the cheaper
side first, so an unwarmed run inflates the denominator and pushes the ratio down, toward
passing rather than toward a spurious failure. The warm-up removes that bias for about six
seconds of long-suite time. Best-of-five costs about twenty more (the rows ratio alone is
17s a side at best-of-five) and buys accuracy -- rows ratio 4.05-4.22 against 4.04-4.28
warmed and 3.66-4.56 unwarmed -- that is only worth paying for if the bounds are tightened
from 8, and this file's own docstring argues against tightening them on a shared machine.
F.15's cost estimate of one to two minutes predates the date-parsing fix of the same day,
which made every validation 7.6x cheaper.

**Duplicate recorded output going unnoticed (was F.14).** Fixed 2026-09-22, as a test
rather than as a check in `scripts/new_catalog_case.py`: the generator is the narrow
door, and a hand-made directory or a regeneration after a behavior change goes round it.
`test_no_two_cases_record_the_same_output` compares every case's recorded stdout, stderr
and exit code across both trees. Two pairs were identical when it was written:
`overrides/internal-test-accounts-exempted` ran `--rules examples/rules/error_overrides.yaml`,
which is exactly what `--rules` defaults to, so it printed what `data/validate-a-csv-file`
prints — the command guard could never have caught that, since the commands differ. It
now runs the email-only rule file, so the exemption is the only rule in force and the
output differs from both neighbors. The second pair, `data/a-file-with-nothing-wrong` and
`data/clean-file-as-csv`, is allowed by name in the test with its reason: an empty report
is prose in both formats (the F.4 decision), so no command can separate them, and both
are worth keeping.

**Cutting or truncating the `large-export` catalog cases (was F.13).** Rejected
2026-09-22. The premise does not hold: measured that day the catalog is 1.18 MB and the
seven cases over `customers_large.csv` are 328 KB of it, 28% — not 1.1 MB of 1.6. Beyond
that, volume is the only thing those cases demonstrate (every other case runs 24 or 49
rows), and two of them are `complex/`, a level with exactly 10 cases against a floor of 10
in `test_the_catalog_has_enough_of_each_level`, so dropping either fails that test.
Truncating the recorded output was rejected for a different reason: a catalog case pins
every byte the entry point prints, and a case that stops comparing part of its output
stops being evidence about that part.

**Example READMEs omitting the exit code (was F.12).** Fixed 2026-09-22. Thirty of the
42 `tests/examples/` READMEs did not name one; the twelve that did used `; exit 0` at the
end of the `Expected:` block, and the twenty `tests/failures/` READMEs all name theirs
because there the code is the point. All 42 now say `exit 0`, and
`test_every_case_documents_itself` asserts that every case's `Expected:` block names the
code in its `exit_code` file, so the drift this item recorded cannot come back. (F.12
counted 33 of 42 with nine naming it; two more had been reworded the same day for F.4 and
F.11.)

**The internal-test exemption case showing nothing (was F.11).** Fixed 2026-09-22. Row
1018's address in `scripts/make_example_data.py` is now `load-test@@internal.test`: two
`@` signs, so `EMAIL_MISSING_AT` fails on it, and the address still ends `@internal.test`,
so the shipped rule exempts it. Three catalog outputs moved — the runs where that rule is
not in force (`data/no-rules-at-all`, `data/legacy-rows-get-a-stricter-check`,
`overrides/a-rule-on-a-column-the-data-lacks`), each gaining exactly the one failure line;
the thirteen runs that do apply the rule are unchanged, which is the demonstration. The
two READMEs now name each other as the diff to read. The case was identical to
`data/validate-a-csv-file` for a second reason F.11 did not record: `--rules` defaults to
that same rule file, so the two commands were the same invocation. Changing the domain to
one the check rejects, as F.11 proposed, would not have worked -- the domain regex accepts
`internal.test`, and a subdomain address stops matching the rule's `@internal\.test$`.

**Dropping the registering module `clear_registry` evicts (was F.10).** Rejected
2026-09-22; the behavior is pinned instead, by
`test_a_module_that_registered_by_plain_import_is_evicted_too`, and the trap is written
down in [architecture.md](architecture.md). `load_checks` records the modules it imports
itself, so the line in `register_check` covers only the other routes in — a check file
importing a shared module of its own, which Python would keep cached and which would
register nothing on the next load, leaving a silently empty registry. That is the worse
failure of the two: the trap it costs is loud. The trap's exact rule, which had been
recorded as "a `@dataclass` under `fresh_registry` fails": after eviction
`sys.modules[name]` is `None`, and a dataclass whose annotations must be resolved
(`ClassVar`, `InitVar`, `get_type_hints`) raises `AttributeError: 'NoneType' object has
no attribute '__dict__'` from `dataclasses`. A dataclass with none of those is fine,
which is why it looked intermittent.

**Refusing patterns that backtrack catastrophically (was F.9).** Rejected 2026-09-22;
[configuration.md](configuration.md) states the cost and the non-goal instead, with the
measured curve for `(a+)+$` (20 characters 0.16s, 24 2.5s, 26 11s, 28 42s -- doubling per
character, per row). A load-time refusal cannot be drawn accurately: rejecting "a
quantifier inside a quantified group" also rejects `^(\d+,)+$`, an ordinary
comma-separated-list pattern, while `(a|a)+$` still gets through, so the owner loses
working configuration with no way to override and the catastrophic case survives anyway.
Bounding it at match time needs a timeout `re` does not have -- the third-party `regex`
module has one, and the library takes no runtime dependencies.

**The deep-chain error reporting width as depth (was F.8).** Fixed 2026-09-22. The
message said `deepest declared depends_on: N`, which is `max(len(check.depends_on))` --
the widest fan-in of one check. Its own test proves how useless that is: a 2,000-link
chain reported `1`. It now names the constraint the walk actually hit, Python's recursion
limit (about 900 links at the default 1,000), and labels the fan-in `widest`. The chain's
real length is not reported: measuring it means a second traversal that must itself be
cycle-safe, since `_topological_order` finds cycles and orders in one pass and has not
finished when this fires. Rewriting that walk iteratively -- no recursion limit, and a
cycle longer than the limit reported as a cycle rather than as depth -- was rejected for
now: it changes the ordering every validation run goes through, to remove an error no
real suite reaches (the example suite's deepest layer is 2), and costs the readable
recursive version.

**A cell's own line breaks corrupting the bordered table (was F.7).** Fixed 2026-09-22.
`_cell_lines` returned `str(value)` unchanged for a column with no wrap width, so a row
key or an `extra_columns` value holding a newline emitted its own line break and slid
every column after it — a quoted multi-line CSV field is the ordinary way one arrives,
and `read_csv` accepts those. It now splits on `\r\n`, `\r`, `\n` and `\f` and expands
tabs (`len()` counts one character where a terminal draws eight), in the wrapped branch
as well as the unwrapped one, so the two agree on what a line is; a wrapped column used
to collapse a newline to a space. Deliberately not `str.splitlines()`: it also splits on
`\x0b`, `\x1c` and ` `, which draw as nothing, and a cell going tall for an
invisible character is its own bug. CSV output was never affected — pandas quotes.

**Checks seeing two context types, one per entry point (was F.6).** Fixed 2026-09-22.
`validate` handed every row an empty `RowContext`; `explain_row` and `validate_row`
handed `None`, so the same check saw two types depending on which call ran it, and
`writing-checks.md` worked around it by passing `context=RowContext()` by hand. The
normalization now lives in `explain_row` — the single implementation of the per-row
algorithm — so it covers `validate_row`, a `context_builder` that returns `None`, and
`validate` at once, from one module-level empty context rather than one per row. The
boundary types stay `RowContext | None`: a caller may still pass `None`, it is what a
check receives that is guaranteed. A check written `if context is None:` to skip
cross-row logic on the per-row path loses that signal; nothing shipped did it, and under
`validate` it never worked anyway.

**A rule pattern matching a whole number pandas holds as float (was F.5).** Fixed
2026-09-21. `cell_text` now renders a cell through the same `_format_cell` the report
uses (moved to `tables.py`), so `^41$` matches `41.0` — which is what an integer column
with one blank becomes on `read_csv`, and what `iterrows` makes of every column when the
frame is all numeric (the second is the rarer of the two; any string column stops it).
The report had printed `41` all along, so the rule format caught up with what the user
sees. A pattern written against the float text (`^41\.0$`) no longer matches; nothing
shipped did that. Checks still receive the float: the engine's row type is unchanged.
Pinned through `validate` on both frame shapes, since a hand-built `Series` goes through
neither.

**Printing a CSV header from `print_report` on an empty report (was F.4).** Rejected
2026-09-21; the two catalog READMEs that promised the header were corrected instead
(`tests/examples/data/clean-file-as-csv`, `complex/clean-file-every-rule-csv`). The
argument for the header was that a piped CSV should always be a valid file, and it does
not hold: the CLI prints the registry above the report and the summary below it, so its
stdout is never a CSV file, empty or not, and `write_report` — the call that does produce
a file — already writes the header alone (`render_report` never short-circuits;
`print_report` is the console path). Printing the header only in CSV mode would have
left the two console formats disagreeing on an empty report, cost a downstream `grep
"No failures."` its match, and moved two catalog cases and the suite counts for it.

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
