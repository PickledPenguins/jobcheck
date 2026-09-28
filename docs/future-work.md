# Future work

Back to the [README](../README.md).

Known gaps, work that is planned, and — the part that earns this document its place —
what was **considered and deliberately not done**, with the reason. Without the last
section every review re-proposes the same rejected idea and every session re-derives the
same answer.

Open findings live in `.agent/reviews/` when a review has run; what a session was in the
middle of lives in `.agent/HANDOFF.md`. This file is for questions that are closed.

## Known gaps

Every item raised by the reviews of 2026-09-15, 2026-09-21, 2026-09-23, 2026-09-24 and
2026-09-25 has been worked through: what was built is in the git log, and what was
decided against is in the section below, with the reason. An entry there is closed, not
pending.

F.46 was decided on 2026-09-28 and moved to the section below.

The three reviews of 2026-09-27 are worked through in part. Every silent finding —
anything that goes wrong with no sign a user could see — was built the same day:
duplicate YAML keys and unknown `match` keys refused, the shared empty context made to
refuse attributes, `warn_blocking_rules`, `rules` read once as a list, incomplete outcome
lists refused by the summary, a `functools.partial` no longer evicting `functools`,
`load_checks` serialized, terminal control characters shown as escapes, `regen_docs.py`
refusing a name that matches nothing, five untested contracts and four unpinned messages
closed, and the false docstrings, comments and catalog descriptions corrected. What was
left is open below, from F.49. Each is either loud already, or needs the owner's decision.
F.46 and F.47 were decided on 2026-09-28 and are in the section below. F.48 was built the
same day: a second positional parameter with a default other than `None` is refused at
registration, for a check and for a context builder alike, naming `functools.partial` and
a keyword-only parameter as the two ways to write it.

**YAML's booleans in rule files** (F.49, low). PyYAML reads unquoted `on`, `off`, `yes`
and `no`, in any case, as booleans: `name: off` fails as "every rule needs a non-empty
string 'name'", giving no position and no hint; `codes: [ON]` fails without showing the
`True`; `pattern: NO` (Norway) shows the `False` but not why. Loud, and confusing to the
non-developers who write these files. The fix: name the entry's position and the value
read, and where a bool arrived in place of a string, add "quote it: YAML reads unquoted
yes/no/on/off as true/false". The strict reader in `paths._read_yaml` is where it would
live. Keys are half covered since 2026-09-28: an unknown key is listed as Python writes
it, so `on:` shows as an unquoted `True` beside quoted names; nothing says why yet.

**Wide characters misalign the bordered table** (F.50, low). Columns are padded by
`len()`, so `名前名前` (length 4, eight columns on screen) pushes every column after it.
Visible. Padding by display width (`unicodedata.east_asian_width`) is a few lines, but
changes every width calculation in `_format_table`.

**The CSV printed to a terminal keeps control characters** (F.51, low). The bordered form
now shows them as escapes; `render(fmt="csv")` keeps the data as it is, since a CSV file
is data for another program. `examples/main.py --report csv` prints that CSV to stdout,
so on a terminal an escape sequence in a cell still acts. A design question rather than a
defect: an entry point could escape when stdout is a tty, or the library could offer it.

**Equal-length failures-only lists still pass the summary's check** (F.52, low).
`summarize_outcomes` and `build_report(include=...)` refuse lists that differ in length,
which is what `validate_row`'s failures-only lists do on any ordinary frame. They cannot
catch a single row, or a frame where every row fails the same number of checks. A
complete check would need `validate_row` to mark its lists, or a comparison against the
registry, which hand-built outcome lists (the tests have many) do not match.

**`clear_registry` still evicts a third-party callable object's module** (F.53, low). The
standard library and a partial's `functools` are now exempt, but a callable object of a
class from an installed package (`register_check(...)(SomeValidator(5))`) records that
package's module, and evicting it leaves earlier importers holding a second copy. The
module to evict is really the one whose execution called `register_check`, which the
decorator cannot see for an object; a plain function is the only shape where the two
agree. Options: skip modules under `site-packages`, or record nothing for a callable
object and document that such a check must be registered in a file `load_checks` loads.

**`scripts/regen_docs.py` duplicates skills `bin/doc-examples`** (F.54, from the
2026-09-27 commit review). doc-examples was committed 29 seconds after it, to replace
it, and gives the same verdict on `docs/` in 3 seconds. Keeping both leaves two fence
parsers that must agree (`tests/doc_files.py` matches a fence anywhere and allows no
info string; doc-examples anchors at line start and allows one) and breaks the rule that
a tool lives in skills. Either delete the script and its test and point
`test_docs_blocks_unit.py`, `doc_files.py`, `contributing.md`, `testing.md`,
`architecture.md` and `.claude/CLAUDE.md` at doc-examples, or record here why the
published repository keeps its own copy.

**Case-local `.py` basenames must be unique across `tests/`** (F.55, low). The catalog's
case directories are not packages, so mypy checks each case-local file as a top-level
module named after its basename; a second `check_job_paths.py` in another case fails the
fast suite with `Duplicate module named ...`. Loud. Either say so in
`tests/examples/README.md` or `exclude` the case directories from mypy.

**The scaling test is flaky under load** (F.56).
`test_building_a_report_scales_with_the_failures_not_the_rows` failed 2 of 7 runs under
load on 2026-09-25 and has passed since. Not investigated.

**`paths.resolve_input_file` has no underscore** (F.57, low). `paths` is exempted in
the internal-modules list of `tests/test_api_contract.py` rather than having its public-looking
name made private. Not checked since 2026-09-26.

**A `creadme` audit of `docs/`** (F.58). `f068452` rewrote about 1,100 lines, and the doc
tests check names, blocks and counts, not prose claims — which is how the "downstream"
root-cause line got in.

**A property test for the rule parser over generated YAML text** (F.59).
`tests/test_fuzz.py` generates structures and dumps them with `yaml.safe_dump`, which
never writes a repeated key, an unquoted boolean or an unknown criterion key: text is the
only input that holds them.

**The declared floors, Python 3.10 and pandas 2.1, have never been run** (F.60). No such
interpreter exists here, and installing one needs the owner's permission. One difference
is already known: formatting an `Outcome` member (see its docstring).

**The native `/code-review` pass** (F.61) was not run in any of the 2026-09-27 reviews.

**Two tentative traps, reasoned but never reproduced** (F.62). `registry._CHECKS.sort()`
would leave the cached evaluation order contradicting the graph (noted 2026-09-24). A
bundle that catches its own member's exception and loads it again in the same process
would hit "Duplicate check code" (noted 2026-09-22).

**`explain_row` versus `row_explanation`: two confusing names, and two meanings of
`detail`** (F.63, raised by the owner on 2026-09-28, to come back to). `explain_row`
returns the outcomes for one row; `row_explanation` turns outcomes into a table. The
names are close enough that it is hard to remember which does which. The `detail`
column also means two things. In the report it is only why a check gave no verdict,
with `message` and `comments` in their own columns. In the row explanation it is the
first non-empty of detail, rendered comments, message, then `-`
(`src/jobcheck/report.py:205`). There is a related trap: calling `explain_row(row)`
without the `context` and `rules` that `validate` was given re-runs the checks with an
empty `RowContext`, so a check that reads context raises. The explanation then shows
`errored` where the report shows a verdict. Explaining from `validate`'s own result,
`row_explanation(outcomes[i])`, avoids it. Not yet surveyed.

**A column widened by one long word should wrap its other cells at that width** (F.64,
raised by the owner on 2026-09-28). `render` wraps each free-text column to a fixed
width from `_WRAP_WIDTHS` (`src/jobcheck/tables.py:187`) and never breaks inside a
word (`break_long_words=False`, `tables.py:105`). A single long unbroken string, such
as a path or an identifier, therefore overflows the limit. The column is then as wide
as that string (`tables.py:145-152`), but every other cell in the column is still
wrapped at the smaller configured width. The result is a wide column whose other cells
are split over more lines than necessary. Proposed: wrap each column at the larger of
its configured width and its longest unbreakable word, so every cell uses the width
the column already takes. The wrap would then need two passes, one to measure the
longest word per column and one to wrap. Not yet surveyed.

**A check that raises should report its exception type and message** (F.65, raised by
the owner on 2026-09-28). With `on_error="record"`, the owner found the exception
effectively hidden unless the run is repeated with `on_error="raise"`, and wants the
exception type and message in `detail` or `comments`, whichever fits. What the code
does today: the engine already writes `f"{type(exc).__name__}: {exc}"` into the
outcome's `detail` (`src/jobcheck/engine.py:138`), and the report and the row
explanation both show it in their `detail` columns. The owner's own case showed
`detail='AttributeError: ...'` on the outcome. So the survey must first find out why it
read as hidden. Candidates: the `detail` column is not where a reader looks, next to
an empty `comments` column; `str(exc)` can be terse or empty, leaving only the type;
and there is no location, so nothing says which line of which check raised. Possible
additions: the file and line of the innermost frame in the check (from
`exc.__traceback__`), or the full traceback kept on the outcome for `render` to show on
request. Not yet surveyed.

**A unique line counter in the output tables** (F.66, raised by the owner on 2026-09-28).
The owner wants a counter that uniquely identifies each line of a table. It is global:
it counts the lines of the whole table rather than restarting for each data row. It is
added beside the existing `row` column, which it does not replace. `row` is the
`key_column` value or the frame's index (`src/jobcheck/report.py:67`). In the long-format
report it repeats on every failure of a data row, and a key column may itself repeat or
be missing (`<no key>`), so no column today names one line uniquely. The survey must
settle which tables carry the counter (the report only, or every table `render` prints),
whether it starts at 0 or 1, whether it counts before or after `include` filtering (a
failures-only report and an `include="all"` report would number the same failure
differently), its column name and position, and how it interacts with `add_columns`
name collisions and the CSV output. Not yet surveyed.

**Record the rule that enabled a check** (F.67, raised on 2026-09-28 while answering the
owner's request for a table of every check a rule decided). The engine records a rule
only when it disables a check: the outcome's `detail` reads `disabled by rule 'name'`
(`src/jobcheck/engine.py:111`). `_resolve_enabled_state` computes the same reason for a
rule that enables a check, but the loop at `engine.py:104` drops it, so a rule-enabled
check's PASSED, FAILED or SKIPPED outcome has no trace of the rule. Today the only way
to find one is indirect: an off-by-default code (`registry_table()`'s `default == 'OFF'`)
whose outcome is not `disabled`. That loses the rule's name, and it cannot see an enable
rule on a check that is on by default (one re-enabled after an earlier rule disabled it).
A related gap: `prerequisite disabled: X` does not say whether X was disabled by a rule
or by default.

- Gained: the table of rule-decided checks becomes one filter, names the rule, and
  catches enables of default-on checks.
- Lost, if written into `detail`: its documented meaning, "empty for a check that passed
  or failed" (`docs/reporting.md:53`, the `CheckOutcome` docstring); any caller that
  treats `detail == ""` as "ran normally"; and a failures report would show `detail` on
  every rule-enabled line, so the column would sometimes explain the outcome and
  sometimes explain why the check ran at all.
- Alternative: a separate `rule` field on `CheckOutcome` and a report column. That keeps
  `detail` to one meaning, but changes the report's columns and more of the docs.
- Size: about 10 source lines in `engine.py` for the `detail` form, or about 25 across
  `results.py`, `engine.py` and `report.py` for the field; docs in `reporting.md` and
  `interfaces.md`; about 3 tests.
- Blast radius: `build_report`, `row_explanation`, the CSV columns, and the shown output
  of the doc examples, which the doc-example test would catch.
- Priority: medium. Nothing fails, but "ran because of a rule" is only approximate.
- Recommended: the separate `rule` field. Not yet decided.

**Consider removing or simplifying `render`** (F.68, raised by the owner on 2026-09-28).
`render(table, fmt)` (`src/jobcheck/tables.py:231`) is a thin layer over pandas: it
chooses no columns and reformats no values, since `build_report` and the other table
builders have already done both. What it adds:

- `fmt="table"`: the `== Title ==` heading from `attrs["title"]`, `|` borders, wrapping
  of free-text columns at the per-name `_WRAP_WIDTHS` (`tables.py:185`), tall cells for
  embedded line breaks, expanded tabs, terminal control characters shown as escapes
  (`_visible`), blanks for nulls, `(empty)`, and cells read by position. pandas has no
  equivalent; `to_string()` is the nearest and does none of the safety or wrapping.
- `fmt="csv"`: `to_csv(index=False)` plus the spreadsheet formula guard
  (`_escape_for_spreadsheet`, `tables.py:201`). The guard is the only thing a caller
  loses by calling `to_csv` directly.

Shapes to survey: drop `fmt="csv"` and export the formula guard for callers who write
CSV themselves (a caller who forgets it gets a file that can execute in a spreadsheet);
split `render` into two named functions, one per format, so the `fmt` string and its
`ValueError` go; or leave it as the single entry point. Removing the bordered form
outright would take the only terminal-safe view the package has. Callers: 11 in
`examples/` (`main.py`, `run_from_config.py`, `bundle_main.py`), at least 10 test
modules, and the README plus six documents. `render` is 10 executable lines;
`tables.py` as a whole is 93. Related: F.64 (wrap width) changes the same code. Not yet
surveyed.

On 2026-09-25 the last eight were closed. Built: F.29 (the run file, as a third
demonstration entry point), F.31 (`format_table` renders by position), F.32 (a context
builder's required keyword-only parameter is refused at setup), F.33 (two exports with
no caller made private, and the export list written down), F.36 (`list_rule_codes`
replaced by a `codes` column) and F.37 (an example for every exported name). Declined:
F.34 (merging the column validators) and F.35 (moving the setup schema out of the
registry).

## Considered and deliberately not done

**Errored checks as root causes, and renaming the root-cause columns** (F.47, from the
2026-09-27 reviews; decided by the owner 2026-09-28). `root_causes` picked the shallowest
of every failure, errored ones included, so on the broken-check catalog case's row S4 a
check that raised on layer 0 took the flag from a genuine delivered-before-shipped failure
on layer 2, and the broken check read `failed 1, root_cause_rows 4` (now 2). Counting
real failures only was prototyped and rejected: row S3, whose only problem is the broken
check, then had no flagged line at all, so a filter on `is_root_cause` hid it. Built
instead: data failures come first, and an errored check counts only on a row with no
`failed` one (`test_a_broken_check_never_takes_the_flag_from_a_data_failure`,
`test_a_row_whose_only_problem_is_a_broken_check_is_still_flagged`). Renaming
`is_root_cause`, `root_cause_rows` and `root_causes` to something that claims no cause
(`is_shallowest`, `shallowest_rows`) was declined: the docs now define the term as "the
shallowest failing layer, read first", and the rename would touch about 48 fixtures, 10
test modules, 7 documents and jobchain for a heading. Reopen if the column is misread in
practice.

**Recording a raising context builder as `errored`** (F.46, high, from the 2026-09-27
diff review; decided by the owner 2026-09-28: document instead). `validate` calls the
builder outside the `try` that turns a check's exception into `errored`, so a builder
raising on one row -- `args.base / row["run_dir"]` on a blank cell -- ends the whole call
and names no row. Four options were prototyped on the job-manifest case with a blank
`run_dir`: every check on the row recorded `errored` (the run survives, but checks that
never read the context lose their verdict there, and every layer-0 check gains a
`root_cause_rows` count); a stand-in context that raises when read (most information,
but a check testing `isinstance(context, TheirContext)` passes silently); raising with
the row named (the run is still lost, and the exception type changes); and documenting
that a builder must not raise, with the defensive pattern. The last was chosen: the
builder is the caller's code, and written to map a blank cell to `None` behind a
presence check it gives the best report of the four -- one `MISSING` failure, no
`errored` lines. `writing-checks.md` and `interfaces.md` state the contract,
`test_a_builder_that_raises_propagates_unchanged_under_record` pins it, and the
job-manifest catalog case shows the pattern (rows J7 and J8). Reopen if builders written
by people other than the pipeline's own authors become common, where the trap would bite
someone who never read the contract.

**Building rules in Python** (F.38, raised by the `src/` review of 2026-09-25, declined by the
owner the same day). `Rule` is exported, but a hand-built one needs the private
`_MatchCriterion` and a precompiled regex, and is not validated -- six test modules import
the private class to build rules. The proposal was a `Rule` that takes the YAML's own
`match` shape and validates itself, so `validate(df, rules=[Rule(...)])` works without a
file. Declined: rules are configured in YAML files and nowhere else. `Rule` stays a type the
loader returns rather than one callers construct.

**Replacing the context builder with one shared `context=` object** (F.39, raised by the `src/`
review of 2026-09-25, rejected by the owner the same day). The proposal replaced
`context_builder`, `context_args` and `RowContext` with `validate(df, context=obj)`, the
same object for every row, on the evidence that jobchain passes a constant. Rejected: the
builder is the design, not a leftover. What a pipeline needs is a set of **row-scoped
constants** -- paths, files, values derived from each other -- defined in one place, built
once per row, and shared by every check on that row. That needs an object built from the
row, which the builder does and a single shared object cannot. `RowContext` stays as the
interface such an object subclasses.

**Handing checks one Python type per column whatever the frame holds** (F.40, raised by the
`src/` review of 2026-09-25, rejected by the owner the same day). `validate` iterates with
`iterrows`, so an all-numeric frame upcasts an int column to float (`7` arrives as `7.0`)
while a frame with any text column does not. The proposal was `df.astype(object)` in
`validate`: +14% on an all-numeric 4,000-row frame, no change on `customers.csv`. Rejected in
favor of consistency the caller controls: a check should expect the same thing whatever the
column types, and the owner's preference is text -- a frame read with `dtype=str` hands
every check strings, the same on every row and every frame. The library does not convert.

**Rolling a failed load back, per file or per call** (F.41, raised by the `src/` review of
2026-09-25; the per-file rollback removed the same day). `load_checks` used to drop the
checks a failing file had registered, tracking each in-progress file's checks on a stack
so a failing bundle kept its completed members'. The review proposed making the whole call
atomic instead, which would also have closed the F.30 trap. Both were answered by the use:
a load failure ends the script, and the author reruns it. The one caller that loads twice
in a process, jobchain, calls `clear_registry()` before every load, so it never saw the
rollback either -- only the test suite did. The rollback, its `except BaseException`
block and the per-file check lists went; the error still propagates unchanged. What was
lost: a caller that catches the error and loads the corrected file in the same process now
gets "Duplicate check code" unless it calls `clear_registry()` first.

**Documenting an exported name in prose instead of showing it in use** (F.37, decided
2026-09-25). F.37 was raised against five names no document mentioned. The owner's rule
asks for an *example*, so the bar was raised to a runnable use -- `examples/`, an executed
block in `docs/`, or jobchain -- and thirteen names failed it. Twelve now have one in
`docs/reporting.md` or `docs/writing-checks.md`, grouped by use rather than one block per
name: the frames behind the `print_*` functions, the outcome constants, the registry and
rules frames, the renderer's pieces, the spreadsheet guard, and `validate_registry` for
checks defined in-process. `resolve_enabled_state` had no honest one -- `explain_row`
answers the same question and more -- so it is `engine._resolve_enabled_state` now, and a
caller wanting a row's on/off states without running the checks has no public spelling.

**Splitting `list_rule_codes` into `get_rule_codes` and `print_rule_codes`** (F.36,
decided 2026-09-25). The function was the one reader in `registry_tables.py` that
printed, returned and raised under a third prefix. The entry recommended the split; it
would have grown the surface by one name while `get_rule_codes` stayed a lookup by name
over `Rule.codes`, a public field. Instead the function is gone and `get_rules_table`
offers `codes` as an optional column, which is the module's own rule -- every question
about the configuration becomes another column. What that gives up: lookup by name, with
its `No rule named 'x'. Loaded rules: ...` error for a misspelling, and the one-line
`name (action) -> A, B` print. A `title: bool` flag was also declined: on this function it
would have suppressed its only line, a different meaning under the same name.

**Moving the setup-file schema out of `registry.py`** (F.35, decided 2026-09-25).
The setup-key tuple, `_setup_paths` and `load_setup` are about sixty lines of YAML schema
validation in the module about the set of checks. `load_setup` has to stay, since it calls
both loaders, so a move splits the function from its rejections; into `rules.py` it blurs
a module guarded as "a file about a file format", and as its own module it is forty lines
in a package already accumulating small ones. The move was deferred until F.29 settled
whether the schema would grow; F.29 landed in `examples/run_from_config.py` with a format
of its own, and the setup file is still two keys. The registry docstring now says why
`load_setup` lives there. Revisit if the setup file gains a key.

**Merging `_reject_unknown_columns` and `_keep_columns`** (F.34, decided 2026-09-25).
Both refuse a column name that is not on offer or is asked for twice (`tables.py:57`,
`tables.py:76`), and both say so in one sentence shape. A full merge needs five arguments
-- requested, allowed, subject, argument name, empty-list text -- at seven call sites, and
either validates *and* filters in one function or keeps a wrapper per caller. Extracting
only the three-line `unusable` computation shares one edit of the three a rule change
needs, since both messages restate the rule in words. Every shared behavior is pinned word
for word in at least two test files, so a change to one copy alone fails the suite.
Revisit when a third column argument appears.

**Keeping `MatchCriterion` public for annotations** (F.33, decided 2026-09-25). The entry
recommended keeping it, as a type a caller may annotate a function over `rule.criteria`
against. The owner's standing rule decided it: no example needs the name -- reading a
criterion's `column`, `pattern` or `regex` works by inference -- so it is
`rules._MatchCriterion` now, and `Rule.criteria` is typed by an internal class. What that
costs: a caller who annotates must import a private name. `normalize_verdict`, whose
claimed use was a wrapper around checks that nobody has written, went private with it.
The derived export test stays, because it catches a public function left out of
`__all__`; beside it, `__all__` must now equal a list written in the test.

**One shared helper for the `(row)` or `(row, second)` rule** (F.32, decided 2026-09-25).
`registry._make_runner` and `engine._context_caller` apply the same arity rule to a check
and to a context builder. They had drifted -- only the check path refused a required
keyword-only parameter -- and that was fixed; each docstring now names the other and says
the two change together. Sharing the code was declined: `registry.py` cannot import
`engine.py`, the reverse import deepens a coupling that is one private name today, and a new
module would hold about six lines, since each caller keeps its own messages. Two
twelve-line bodies that read straight through are cheaper. Revisit when a third caller of
the rule appears, or the rule gains a third shape.

**Refusing a duplicate-labeled frame in `format_table`** (F.31, decided 2026-09-25).
`explain_row`, `_row_labels` and `build_report` refuse duplicate column labels, because
they hand a cell to a check or use it as a row key and a Series there is wrong. The
renderer only has to draw what it is given, so it now reads cells by position and draws a
duplicated label correctly instead of raising. What that gives up: one package-wide rule
about duplicate labels, and a signal to a caller whose `concat` duplicated a column by
mistake. A guard would have rejected input that renders, with no migration path.

**The run file in `main.py`, in the library, or as jobchain's format** (F.29, decided
2026-09-25). One YAML file naming the setup, the data and the tables to print was built as
`examples/run_from_config.py`, a third entry point that takes the file as its only
argument. Three placements were declined. **A mode on `main.py`** would give every run two
spellings, flag and file, and a precedence rule whose other reading is a trap; the
`docs/cli.md` flag gate would need a schema twin. **A loader in `src/jobcheck/`** would put a
command-line concept and a second configuration format into a library that has neither,
and every printing function's signature change would become a schema change there. **A
production runner** already exists: jobchain's run configuration names checks and rules
(`jobchain/config.py:251-257`), and report and column keys belong there if a pipeline
needs them -- one format, in the project whose job it is. The entry point's run-file
format reuses the printing functions' own argument names so it documents itself, and
reuses `load_setup` for the checks and rules, so it adds no schema of its own for either.

**Rolling the loaded-file list back when the dependency validation fails** (F.30's other
half, decided 2026-09-24). `load_checks` records each file as its import finishes and
validates the graph once, after the last one, so a dangling `depends_on` leaves the file
recorded, the broken check registered, and the next call skipping the path -- correcting
the typo in that same file changes nothing until `clear_registry()`. Reproduced. What was
built is the sentence saying so, in the error itself; what was declined is moving
`_LOADED_FILES.append` below the graph validation.

Three reasons. **It would make one dangling prerequisite discard every file of the call**,
where a file that raised during import then discarded only its own -- two
rollback granularities for two failure kinds, in a package whose loading rule is stated as
"per file, not per call, at every depth". **Or it would leave the recorded list and the
registry disagreeing**, which is exactly the state F.24's guards existed to catch. **And
the loaded-file list would stop being a record of what was read**: today it lists the
files that imported successfully after a failed load, which is the honest answer to "what
did you read", and a caller logging it would start seeing an empty list for a load that
genuinely read five files.

The message is the cheaper fix and the honest one: the wedge is a consequence of two rules
that are each right, so the thing to fix was that nothing told the user how to get out of
it. Revisit only if somebody hits it with the message in place.

**Keeping the registry list public, or making it a tuple** (F.28, decided 2026-09-24).
`CHECKS` was exported and mutable, and nothing that mutated it directly dropped the cached
evaluation order -- which is how F.24 was reachable: `CHECKS.pop()` left the order naming a
check the registry no longer had. It is `registry._CHECKS` now, internal, and the read path
is `get_registry_table`.

Measured before deciding: the exported name had **no caller outside the test suite** -- zero
in `examples/`, zero in jobchain, zero in the documents' code blocks, two in `tests/` against
55 that reached the module attribute instead. `interfaces.md` stated the contract as "read it
freely; mutate it only through the decorators and `clear_registry`", a rule with nothing
enforcing it. Every legitimate read was already served: `get_registry_table` gives code,
layer, default, message and `depends_on` as a frame, and `loaded_check_files` the files
behind them.

The two fixes on record were both worse. A **tuple** would make `clear_registry` and
`register_check` rebind a module global, which `from .registry import CHECKS` in `engine.py`
and `registry_tables.py` would never see -- and any external `from jobcheck import CHECKS`
would silently keep the old list. A **copy-returning `checks` function** would be a new
export needing its own use case when `get_registry_table` is already it. Private costs
neither. A caller who reaches in anyway gets a bare `KeyError` from the row loop rather than
a plausible wrong report; the F.24 guards that turned it into a worded `ValueError` were
removed on 2026-09-25 (review of `src/`): about 40 lines, two of them in the hot loop, spent
on misuse of a private name, and they missed `_CHECKS.sort()` regardless.

What went with it: a caller wanting the `Check` objects themselves rather than the table --
the runner function, and `source_file` except as an optional column. Nothing here or in
jobchain wanted `fn`, and handing out the runner invites calling it outside the engine, which
bypasses rules, dependencies and error recording.

**A search path for check and rule files** (F.17, decided 2026-09-23). `base_dir`
anchors a relative path to one directory the caller names. What it does not serve is the
deployment case: check files installed in a shared location, named bare by a run
configuration that does not know where they went. A list of directories tried in order,
first match wins, was the obvious answer and is refused. **A bundle is the answer
instead**: the installed location ships one check file that names its own members, the
run configuration names that file, and where the members live is the bundle's business
rather than a search order's. One path still means one file, which a search path gives
up -- two files of one name in two entries means the wrong checks run and nothing says
so, and an environment variable makes a run irreproducible from its command line. It
would also cost the sentence every failure prints, "load_checks() names files explicitly;
nothing is discovered", which is pinned in eleven places and is the invariant the whole
loader is built on.

**An `Outcome` enum in place of five outcome strings** (F.42, raised by the `src/` review of
2026-09-25, built the same day). `PASSED`, `FAILED`, `DISABLED`, `SKIPPED` and `ERRORED`
were plain strings, so a misspelled comparison was silently false. `Outcome` is a
`(str, Enum)`: one export instead of five, `== "failed"` still holds, a misspelled member
is an `AttributeError`, and `CheckOutcome` refuses a string that is not an outcome. Chosen
over plain strings with no constants, which saves one more name and loses the typo check.
Lost: formatting a member prints `Outcome.FAILED`, so hand-written text needs `.value`
(the tables write `.value` themselves; `StrEnum` would avoid it but needs Python 3.11).
Jobchain's two `engine.ERRORED` uses changed with it.

**Five exported names made private** (F.43, raised by the `src/` review of 2026-09-25, done
the same day, per the example rule of F.37). `Check` (no public function hands one
out since F.28), `render_status` (duplicated by `CheckOutcome.status_label`),
the report-column tuple (what a report shows is `_DEFAULT_COLUMNS` now), `loaded_check_files`
and `validate_registry` (both run or recorded by `load_checks` itself). 36 exports
become 31. Lost: formatting a bare status number outside an outcome; a public list of
the report's hidden columns; logging which files a run loaded, including a bundle that
registers nothing (`registry_table(add_columns=["source_file"])` shows the files that
registered checks); and an explicit graph check before data for checks registered
outside `load_checks` (`registry_table()` runs it). `bundle_main.py` prints the
registry with `source_file` instead of its "Loaded" list.

**`drop_columns` replaced by one dict of default columns** (F.44, raised by the `src/`
review of 2026-09-25, built the same day). `build_report`, `registry_table` and
`rules_table` each took `drop_columns`, validated against per-table base and optional
column lists in two modules. Now `_DEFAULT_COLUMNS` in `tables.py`, keyed by title, sets
what every table shows -- the owner wanted the defaults editable in one place in the
library rather than set by an entry point -- and a one-off removal is pandas'
`table.drop(columns=...)`, which keeps the title. Lost: the friendly "cannot be used ...
one of:" message for a bad drop name (pandas raises `KeyError`); restoring a hidden
*report* column per call (edit the dict); and `add_columns` on the summary and row
explanation, which never had it. The run file keeps its `drop_columns` option, applied by
`examples/run_from_config.py` itself.

**One `render` in place of the printing functions** (F.45, raised by the `src/` review of
2026-09-25, built the same day). Twelve names showed or saved results --
`print_report`, `render_report`, `write_report`, `print_registry`, `print_rules`,
`print_row_explanation`, `print_summary`, `format_table`, `escape_for_spreadsheet`,
`root_cause_counts`, `get_registry_table`, `get_rules_table` -- under three rules about
what each returned. Now every view is a DataFrame carrying `attrs["title"]`
(`build_report`, `registry_table`, `rules_table`, `row_explanation`,
`summarize_outcomes`), and `render(table, fmt)` draws any of them under a `== Title ==`
bar or as escaped CSV. The owner chose a title the table carries over a `title=`
argument, since naming the table at every call is cumbersome. Lost: the facts in the
old headings (line and row counts, key column, include level, rule count); "No
failures." and the other empty-table sentences, now the title over `(empty)`; the
"root cause:" line under an explanation (call `root_causes`); the root-cause tally
under the summary, now its `root_cause_rows` column; `write_report`'s one-call file
write; and the heading on a table merged or concatenated with an untitled frame, since
pandas drops `attrs` there. `attrs` is experimental in pandas; the fallback is a
missing bar, never an error.

**Making `print_report` return its frame** (F.25, decided 2026-09-24; moot since
2026-09-25, when the printing functions were replaced by `render`). Four `print_*`
functions return the DataFrame they print and `print_report` returns `None`, which read as
an inconsistency. It is not one: the other four *build* their frame -- `print_registry` from
the registry, `print_rules` from a rule list, `print_row_explanation` and
`print_summary` from outcomes -- so returning it saves the caller building it twice.
`print_report` is handed the finished report as its first argument, and returning it would
hand back what the caller passed in. Its real siblings are the other two functions with that
argument, and both agree with it: `write_report` returns `None`, `render_report` returns its
text.

So the change was rejected. It adds a public return value with no use case a user outside
the package has -- the test any export has to pass here -- and it makes the convention worse,
because afterwards `print_report` and `write_report` take the same argument and return
different things, and the rule becomes "whatever starts with print_" rather than "whoever
built the frame". Two of the entry's supporting claims did not hold either:
`test_api_contract.py` pins defaults, not returns, and `interfaces.md` documents no return
for `print_report`. What was real was that the convention lived in one module's docstring
and was narrower than the truth; both docstrings now state it in full.

**Spelling out the test suite's module aliases** (F.23, decided 2026-09-23). The suite
writes `reg`, `rep` and `res` where the package spells `registry`, `report` and `results`
out, and `contributing.md` names the junior reader as the bar. Rejected on size against
gain: measured 2026-09-23, that is 405 use sites across about 26 files -- `reg` 277 in 24
files, `rep` 93 in 6, `res` 33 in 5 -- a diff with no behavior change that makes
`git blame` and `git log -S` on the suite worse for a year to buy a spelling. The entry's
own figure, "~200 touched lines across ~20 files", was half the real one, and it missed
`rep` entirely: `conftest.py` does not define that alias, the six test modules each import
`report as rep` themselves. That is also why `conftest.py` is not the lever it looks like --
most of the 24 files re-import `registry as reg` locally, so changing conftest alone changes
nothing.

What was taken is in the git log: `eng` was defined in `conftest.py` and used twice, both
inside `conftest.py`, while three test modules already spelled `engine` out. Dropping it
cost three lines in one file and left the suite with one spelling of `engine` instead of
two. If the suite is ever split or reorganized, spell the rest out in the files that move
and let the others converge.

**Renaming `tables.py`'s two cross-module helpers to look public** (F.22, decided
2026-09-23). `_format_cell` and `_reject_unknown_columns` carry a leading underscore and are
imported by `report.py`, `rules.py` and `registry_tables.py`, while `is_null` and
`format_table` sit in the same file without one and are exported. Dropping the underscore
was rejected: `tests/test_api_contract.py` fails on a public callable that is not in
`__all__`, so the rename forces both into the public surface, and `_reject_unknown_columns`
exists to reject a bad `add_columns=` argument -- there is no use for it outside the three
tables that take one, which makes it exactly the kind of export that has to be removed
again later. Keeping a public-looking name deliberately out of `__all__` is worse still: a
second rule to learn, and an exception to explain in the contract test. What was wrong was
that the convention was nowhere written; it now is, in `tables.py`'s docstring and in
`contributing.md`'s style list. An underscore marks a name outside the *public surface*,
not one that stays in its file -- `_cell_lines`, `_padded_line` and `_LINE_BREAKS` happen to
be both.

**One shared `sys.path` bootstrap helper** (F.21, decided 2026-09-23). Seven files compute
the clone root and prepend some subset of `src`, `examples`, `tests` and the root to
`sys.path`: `tests/conftest.py`, the two entry points under `examples/`, and four scripts
under `scripts/`. Five distinct insert sets, two spellings of the root (`PROJECT_ROOT`,
`ROOT`) and two libraries (`os.path`, `pathlib`). A shared helper was rejected. The two
files under `examples/` have to keep their own copy whatever happens -- they are what an
adopter copies, and a demo importing a private test helper to find its own package is worse
than three repeated lines -- so the helper could never cover more than five of the seven,
after which a reader meets two spellings *and* a rule about which files may use the helper.
It has no honest home either: not `src/`, which must not carry a bootstrap for the
repository that develops it; not `tests/`, which the scripts would then import from; and a
new root-level module for it works against the rule that the project root stays readable.
The insert sets differ for real reasons (`new_catalog_case.py` needs only `tests`,
`regen_golden.py` needs the root because it imports a root-level module), so a helper
taking "which of the four" has moved the decision rather than removed it -- and each file
inserts at position 0, so a helper with a fixed order silently changes which module wins
for at least one caller.

Renaming `PROJECT_ROOT` to `ROOT` for consistency was rejected with it: eight sites across
four files to turn two correct spellings into one, and `PROJECT_ROOT` is the clearer of the
two. The entry's citation of a "one name for one concept" rule in `contributing.md` was
checked and no such rule is there. Its counts were wrong as well -- "eight times" counted
`tests/test_docs_unit.py`, which computes a root and inserts nothing, and
`tests/test_concurrency.py`, which imports the root from `conftest` and writes an insert
into *generated subprocess source*. What was taken instead is in the git log: `pythonpath`
in `pyproject.toml` replaced `conftest.py`'s three inserts, which was the one place a
declaration could do the job.

**Rebuilding `lint`, `parallel` or `params` (was F.1).** Declined 2026-09-24, and the
bytecode they existed as is deleted. Three modules were lost when the repository was
re-initialized on 2026-09-09 and survived only as `.pyc`, which keeps names, parameters,
annotations and docstrings but never the statements -- so rebuilding any of them always
meant writing the bodies again from the recovered interface. Nothing calls them, and each
carries a reason beyond the port: `lint` would be a second, softer rule-validation path
beside the loader, written against a rule schema that has since changed from
`column`/`pattern` with `fnmatchcase` to a `match` list of regex criteria; `parallel` needs
every check file to be importable and side-effect-free in a fresh interpreter, a new
contract on user files, and its recorded 3.4s-against-6.6s win predates validation getting
7.6x cheaper; `params` changes the on-disk rule format, which is a design decision rather
than a rebuild. `lint` was the one with obvious value -- warnings about rule files that
parse but can never fire, fire everywhere, or were superseded. The one part of that with a
decidable answer was built separately on 2026-09-24 as `rules.warn_shadowed_rules`: a rule
a later `match: all` rule overrules for every row, which is dead for that code however the
data looks. What stays unbuilt is the undecidable rest, where two conditional rules may or
may not overlap -- that needs the patterns compared rather than read.

The bytecode was committed to this branch and then deleted in the next commit, so it is
recoverable from history rather than carried: `git restore --source=3fce4b4 -- recovery`
brings the whole directory back, and `git show 3fce4b4:recovery/README.md` is its entry
point. It is also still on `origin/main`, where it has lived since 2026-09-09.
`scripts/read_bytecode_api.py` regenerates the package's interface file straight from
that commit, without restoring anything, or from a restored directory named as its argument.

**Registry snapshot and restore as library API** (F.18 and F.19, decided 2026-09-23).
`snapshot` and `restore` copied the registry's module globals and put them back. Both were
public, exported and documented beside `load_checks`, and nothing outside the test suite
ever called them: measured across both suites, 525 restores, of which exactly one put back
a non-empty registry -- a test of `restore` itself. Every production shape is served by
something else. A long-lived process clears and loads a different set between runs; two
sets of check files active in one process is what `architecture.md` already refuses, entry
points being separate processes; a failed load rolls back per file on its own, so a
snapshot is not the transaction it looks like; and swapping the registry per request under
threads is a race, not isolation. The rule the removal follows: an installed package
carries what a user could call, not what a test needs. The capability is real for a
*test* -- an inner scope that loads check files and must hand back exactly what it found,
which `clear_registry` cannot do because it hands back nothing -- so it moved to
`tests/registry_state.py` as `SavedRegistry`.

That closes both entries that were open against it. F.18 asked whether the in-progress
load stack should be carried: it is not, and the reason survives the move -- the stack
belongs to the `load_checks` call that is running, so a frame put back from a load that
has since finished would take the blame for the next file's checks, and that file's
rollback would drop checks belonging to somebody else. F.19 asked whether putting a
registry back should restore `sys.modules` too: it does not, because re-importing inside a
state swap would re-run a user's check file and double-register. The two consequences F.19
listed do not reproduce either -- `pickle` fails on a check's runner before any restore,
the runner being a closure, and `inspect.getmodule` answers `jobcheck.registry` either
way.

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
`rules/internal-test-accounts-exempted` ran `--rules examples/rules/error_rules.yaml`,
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
`rules/a-rule-on-a-column-the-data-lacks`), each gaining exactly the one failure line;
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
which is why it looked intermittent. Narrowed 2026-09-27: a `functools.partial` reported
`functools` as its module and evicted it; the wrapped function's module is now recorded,
and no standard-library module is ever evicted (F.53 is what is left).

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
key or an `add_columns` value holding a newline emitted its own line break and slid
every column after it — a quoted multi-line CSV field is the ordinary way one arrives,
and `read_csv` accepts those. It now splits on `\r\n`, `\r`, `\n` and `\f` and expands
tabs (`len()` counts one character where a terminal draws eight), in the wrapped branch
as well as the unwrapped one, so the two agree on what a line is; a wrapped column used
to collapse a newline to a space. Deliberately not `str.splitlines()`: it also splits on
`\x0b`, `\x1c` and ` `, which draw as nothing, and a cell going tall for an
invisible character is its own bug. CSV output was never affected — pandas quotes.
Extended 2026-09-27: "draws as nothing" was not true of ESC, which starts sequences a
terminal acts on. Every C0 and C1 control but the handled breaks and tab, DEL, and the
bidirectional overrides are now shown as their escapes (`\x1b`).

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
`validate` it never worked anyway. Amended 2026-09-27: the one shared object was mutable,
so a check caching a value on it handed the first row's value to every later row and
call. `RowContext` now has an empty `__slots__`, so the base instance refuses a new
attribute (recorded as `errored`) while subclasses keep their `__dict__`.

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
rule patterns (`2024-01-01 00:00:00` where the file said `2024-01-01`) and what the
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
the first `test_rules_unit` by what was then `test_overrides_unit` and is now
`test_rules_unit` again, with its nine glob-matching tests obsolete
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
option measured (107 columns) and matches what `print_rules` does with
`codes_hit_count`: the names are the reason the column exists. `print_rules` and
`list_rule_codes` already carry the detail for a reader who wants it by rule rather than
by code.

**Shortening the demo rule names.** Not done. Two are 48 characters
(`disable_age_integer_check_from_another_directory`), which is what makes the table as
wide as it is, but they are self-documenting in a directory whose whole job is to show a
reader what a rule file looks like. This is data in `examples/rules/`, not a library
limit — worth remembering before concluding the table cannot be narrower.
