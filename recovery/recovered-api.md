# Recovered interface: `jobcheck`

## `__init__.cpython-312.pyc` (source was 2,750 bytes)

> Row-validation framework.
> 
> Importing this package registers **no** checks. An entry point names the files
> its checks live in::
> 
>     from jobcheck import load_checks, print_report, validate
> 
>     load_checks(["checks/age.py", "checks/email.py"])
>     run = validate(df)
>     print_report(run.report(key_column="id"))


## `__init__.cpython-314.pyc` (source was 2,750 bytes)

> Row-validation framework.
> 
> Importing this package registers **no** checks. An entry point names the files
> its checks live in::
> 
>     from jobcheck import load_checks, print_report, validate
> 
>     load_checks(["checks/age.py", "checks/email.py"])
>     run = validate(df)
>     print_report(run.report(key_column="id"))


## `context.cpython-312.pyc` (source was 1,382 bytes)

> Per-row metadata that deliberately does not live in the DataFrame.
> 
> Real pipelines carry per-row state that is not tabular data: feature flags,
> computed filesystem paths, pipeline bookkeeping. Putting that into extra
> DataFrame columns causes dtype churn (object columns holding dicts), bloats
> exports, and mixes computation context into a data table. It is kept in a
> separate object instead, handed to every check that asks for one.
> 
> :class:`RowContext` is deliberately empty: subclass it with the fields your
> pipeline carries, build one per row, and pass the builder to ``validate``::
> 
>     @dataclass
>     class MyContext(RowContext):
>         input_path: str
> 
>     validate(df, context_builder=lambda row: MyContext(input_path=...))

- `RowContext()`
  - RowContext
- `build_context(row)`
  - The default per-row context: empty, and the same from every entry point.

## `context.cpython-314.pyc` (source was 1,382 bytes)

> Per-row metadata that deliberately does not live in the DataFrame.
> 
> Real pipelines carry per-row state that is not tabular data: feature flags,
> computed filesystem paths, pipeline bookkeeping. Putting that into extra
> DataFrame columns causes dtype churn (object columns holding dicts), bloats
> exports, and mixes computation context into a data table. It is kept in a
> separate object instead, handed to every check that asks for one.
> 
> :class:`RowContext` is deliberately empty: subclass it with the fields your
> pipeline carries, build one per row, and pass the builder to ``validate``::
> 
>     @dataclass
>     class MyContext(RowContext):
>         input_path: str
> 
>     validate(df, context_builder=lambda row: MyContext(input_path=...))

- `RowContext()`
  - RowContext
- `__annotate__(format)`
- `build_context(row)`
  - The default per-row context: empty, and the same from every entry point.

## `engine.cpython-312.pyc` (source was 12,198 bytes)

> Running the checks: over one row, and over a frame.
> 
> Three levels, each named for what it holds:
> 
> - :class:`ValidationRun` -- a whole frame: its traces and the rules used.
> - :class:`RowTrace` -- one row: every record, in evaluation order.
> - ``CheckRecord`` -- one check on one row. Defined in
>   :mod:`jobcheck.results`, next to what a check returns.
> 
> :func:`explain_row` is the single implementation of the per-row algorithm;
> everything else here is built on it.

- `_enabled_state(row, overrides)`
  - Each code's on/off state for this row, with the reason for it.
- `explain_row(row, ctx, overrides)`
  - Run the checks against one row and report what *every* check did.
- `validate_row(row, ctx, overrides)`
  - Run every enabled check against one row and return the failures.
- `root_cause(records)`
  - The code of the most fundamental failure in a row's records.
- `RowTrace()`
  - RowTrace
  - `failures(self)`
    - The failing records, in evaluation order.
  - `root_cause(self)`
    - The shallowest failure's code, or ``None`` for a row that passed.
  - `passed(self)`
    - Whether nothing failed on this row.
- `ValidationRun()`
  - ValidationRun
  - `__len__(self)`
    - The number of rows validated.
  - `__iter__(self)`
    - Iterate the traces, in frame order.
  - `_records(self)`
    - The raw records, one list per row, for the reporting functions.
  - `failures(self)`
    - How many records failed. A check that raised counts as an error, not this.
  - `errors(self)`
    - How many checks raised.
  - `failed_rows(self)`
    - Traces for the rows that failed something.
  - `root_causes(self)`
    - Each row's root cause, in frame order; ``None`` where it passed.
  - `report(self, key_column, data_columns, include_skipped, include_passed)`
    - The long-format failure table. See :func:`jobcheck.report.build_report`.
  - `summary(self)`
    - Per-check counts, worst first. See :func:`jobcheck.report.summarise_outcomes`.
  - `explain(self, position)`
    - One row's trace, by position in the frame.
- `iter_traces(df, overrides, context_builder)`
  - Yield one :class:`RowTrace` at a time, holding no more than one at once.
- `validate(df, overrides, context_builder)`
  - Run every check against every row of *df*.

## `engine.cpython-314.pyc` (source was 12,198 bytes)

> Running the checks: over one row, and over a frame.
> 
> Three levels, each named for what it holds:
> 
> - :class:`ValidationRun` -- a whole frame: its traces and the rules used.
> - :class:`RowTrace` -- one row: every record, in evaluation order.
> - ``CheckRecord`` -- one check on one row. Defined in
>   :mod:`jobcheck.results`, next to what a check returns.
> 
> :func:`explain_row` is the single implementation of the per-row algorithm;
> everything else here is built on it.

- `__annotate__(format)`
- `_enabled_state(row, overrides)`
  - Each code's on/off state for this row, with the reason for it.
- `__annotate__(format)`
- `explain_row(row, ctx, overrides)`
  - Run the checks against one row and report what *every* check did.
- `__annotate__(format)`
- `validate_row(row, ctx, overrides)`
  - Run every enabled check against one row and return the failures.
- `__annotate__(format)`
- `root_cause(records)`
  - The code of the most fundamental failure in a row's records.
- `RowTrace()`
  - RowTrace
  - `__annotate__(format)`
  - `failures(self)`
    - The failing records, in evaluation order.
  - `__annotate__(format)`
  - `root_cause(self)`
    - The shallowest failure's code, or ``None`` for a row that passed.
  - `__annotate__(format)`
  - `passed(self)`
    - Whether nothing failed on this row.
- `ValidationRun()`
  - ValidationRun
  - `__annotate__(format)`
  - `__len__(self)`
    - The number of rows validated.
  - `__annotate__(format)`
  - `__iter__(self)`
    - Iterate the traces, in frame order.
  - `__annotate__(format)`
  - `_records(self)`
    - The raw records, one list per row, for the reporting functions.
  - `__annotate__(format)`
  - `failures(self)`
    - How many records failed. A check that raised counts as an error, not this.
  - `__annotate__(format)`
  - `errors(self)`
    - How many checks raised.
  - `__annotate__(format)`
  - `failed_rows(self)`
    - Traces for the rows that failed something.
  - `__annotate__(format)`
  - `root_causes(self)`
    - Each row's root cause, in frame order; ``None`` where it passed.
  - `__annotate__(format)`
  - `report(self, key_column, data_columns, include_skipped, include_passed)`
    - The long-format failure table. See :func:`jobcheck.report.build_report`.
  - `__annotate__(format)`
  - `summary(self)`
    - Per-check counts, worst first. See :func:`jobcheck.report.summarise_outcomes`.
  - `__annotate__(format)`
  - `explain(self, position)`
    - One row's trace, by position in the frame.
- `__annotate__(format)`
- `iter_traces(df, overrides, context_builder)`
  - Yield one :class:`RowTrace` at a time, holding no more than one at once.
- `__annotate__(format)`
- `validate(df, overrides, context_builder)`
  - Run every check against every row of *df*.

## `lint.cpython-312.pyc` (source was 14,326 bytes)

> Checks on rule files that the loader deliberately does not make.
> 
> The loader raises: a malformed rule stops the run, because a file that cannot be
> read correctly must not be half-applied. This module warns: a rule that parses
> perfectly but can never fire, or fires everywhere, or was superseded three files
> ago, is a human mistake rather than a broken file. Those are judgement calls, so
> they are reported and left to a person.
> 
> The split matters. If the loader started rejecting suspicious-but-legal rules, a
> pipeline would break on a file that had been fine for a year; if the linter
> raised, it could not report more than one problem at a time. Each does one job.
> 
> Findings come back as data rather than printed lines, so a CI step can gate on
> severity and a person can read the same list through :func:`print_findings`.

- `Finding()`
  - Finding
  - `render(self)`
    - One line, for a console or a log.
- `_criteria_key(rule)`
  - A comparable identity for a rule's match, for spotting duplicates.
- `_covers(later, earlier)`
  - Whether *later* fires on every row *earlier* does.
- `_lint_expiry(rule, today)`
  - A rule that was meant to be temporary and was not.
- `_lint_patterns(rule)`
  - Patterns that do not do what the person writing them expected.
- `_lint_params(rule, declared)`
  - A ``set`` rule that sets a parameter to the value it already has.
- `_lint_effect(rule, defaults)`
  - Rules that ask for the state a code already has.
- `_lint_shadowing(overrides)`
  - Rules a later rule always overrules.
- `_lint_conflicts(overrides)`
  - Codes more than one rule touches with differing actions.
- `_lint_dead_codes(overrides, defaults)`
  - Tests that are off by default and that no rule ever turns on.
- `_lint_against_data(rule, df)`
  - What a rule actually does to a real frame.
- `lint_rules(overrides, defaults, df, today, declared)`
  - Every suspicious thing about *overrides*, worst first.
- `findings_table(findings)`
  - The findings as a frame, for rendering or for further filtering.
- `print_findings(findings, debug)`
  - Print the findings as a table and return the frame behind it.
- `worst_severity(findings)`
  - The most severe severity present, or ``None`` for an empty list.
- `_lint_unused_params(overrides, declared)`
  - Parameters declared in Python that no rule file ever changes.

## `lint.cpython-314.pyc` (source was 14,326 bytes)

> Checks on rule files that the loader deliberately does not make.
> 
> The loader raises: a malformed rule stops the run, because a file that cannot be
> read correctly must not be half-applied. This module warns: a rule that parses
> perfectly but can never fire, or fires everywhere, or was superseded three files
> ago, is a human mistake rather than a broken file. Those are judgement calls, so
> they are reported and left to a person.
> 
> The split matters. If the loader started rejecting suspicious-but-legal rules, a
> pipeline would break on a file that had been fine for a year; if the linter
> raised, it could not report more than one problem at a time. Each does one job.
> 
> Findings come back as data rather than printed lines, so a CI step can gate on
> severity and a person can read the same list through :func:`print_findings`.

- `Finding()`
  - Finding
  - `__annotate__(format)`
  - `render(self)`
    - One line, for a console or a log.
- `__annotate__(format)`
- `_criteria_key(rule)`
  - A comparable identity for a rule's match, for spotting duplicates.
- `__annotate__(format)`
- `_covers(later, earlier)`
  - Whether *later* fires on every row *earlier* does.
- `__annotate__(format)`
- `_lint_expiry(rule, today)`
  - A rule that was meant to be temporary and was not.
- `__annotate__(format)`
- `_lint_patterns(rule)`
  - Patterns that do not do what the person writing them expected.
- `__annotate__(format)`
- `_lint_params(rule, declared)`
  - A ``set`` rule that sets a parameter to the value it already has.
- `__annotate__(format)`
- `_lint_effect(rule, defaults)`
  - Rules that ask for the state a code already has.
- `__annotate__(format)`
- `_lint_shadowing(overrides)`
  - Rules a later rule always overrules.
- `__annotate__(format)`
- `_lint_conflicts(overrides)`
  - Codes more than one rule touches with differing actions.
- `__annotate__(format)`
- `_lint_dead_codes(overrides, defaults)`
  - Tests that are off by default and that no rule ever turns on.
- `__annotate__(format)`
- `_lint_against_data(rule, df)`
  - What a rule actually does to a real frame.
- `__annotate__(format)`
- `lint_rules(overrides, defaults, df, today, declared)`
  - Every suspicious thing about *overrides*, worst first.
- `__annotate__(format)`
- `findings_table(findings)`
  - The findings as a frame, for rendering or for further filtering.
- `__annotate__(format)`
- `print_findings(findings, debug)`
  - Print the findings as a table and return the frame behind it.
- `__annotate__(format)`
- `worst_severity(findings)`
  - The most severe severity present, or ``None`` for an empty list.
- `__annotate__(format)`
- `_lint_unused_params(overrides, declared)`
  - Parameters declared in Python that no rule file ever changes.

## `parallel.cpython-312.pyc` (source was 15,072 bytes)

> Running a frame's rows across several workers.
> 
> Validation is row-at-a-time Python, and the checks usually cost more than the
> engine does, so the work is exactly the kind several cores can share. What makes
> it awkward is that a worker cannot simply be handed the registry:
> 
> - The callables the engine stores are closures built at registration, and a
>   closure cannot be pickled. A worker process has to *rebuild* the registry
>   rather than receive it, which is why :func:`validate_parallel` takes the
>   package and suites to load rather than inferring them.
> - Parameters are declared in Python, so a worker has to be told what was
>   declared before it loads the suites, or the messages that quote one will not
>   validate.
> 
> Threads are not offered, and the measurement is the reason. They avoid both
> problems above, since they share the interpreter's memory -- but on 4,000 rows
> of the example suite a thread pool took 17.7s against 6.6s sequential, nearly
> three times slower, because the checks are pure Python and spend their time
> contending for the GIL. A mode that loses by that much on the default
> interpreter is a trap, not an option. On a free-threaded build the answer would
> differ; anyone adding it back should measure there first.
> 
> Processes on the same frame took 3.4s against 6.6s, and produced identical
> records.

- `worker_count(workers)`
  - How many workers to use, defaulting to the machine's usable cores.
- `split_frame(df, chunks)`
  - Split *df* into at most *chunks* contiguous pieces, in order.
- `_prepare_worker(package, suites, params)`
  - Rebuild the registry inside a worker process, once.
- `_validate_chunk(chunk, package, suites, params, overrides, on_error)`
  - Validate one chunk. Runs in a worker; must be importable, so not a lambda.
- `_report_chunk(chunk, package, suites, params, overrides, on_error, spec)`
  - Stream one chunk into its own report builder. Runs in a worker.
- `validate_parallel(df, package, suites, overrides, on_error, workers)`
  - Validate every row across several workers, in frame order.
- `codes_a_worker_would_not_have(package, suites)`
  - Codes a worker rebuilding from *package* and *suites* would never register.
- `registry_is_reconstructible(package, suites)`
  - Whether a worker could rebuild the registry this process is holding.
- `report_parallel(df, package, suites, overrides, on_error, workers, key_column, data_columns, include_skipped, include_passed)`
  - Validate across workers *and* stream, returning the merged report builder.

## `parallel.cpython-314.pyc` (source was 15,072 bytes)

> Running a frame's rows across several workers.
> 
> Validation is row-at-a-time Python, and the checks usually cost more than the
> engine does, so the work is exactly the kind several cores can share. What makes
> it awkward is that a worker cannot simply be handed the registry:
> 
> - The callables the engine stores are closures built at registration, and a
>   closure cannot be pickled. A worker process has to *rebuild* the registry
>   rather than receive it, which is why :func:`validate_parallel` takes the
>   package and suites to load rather than inferring them.
> - Parameters are declared in Python, so a worker has to be told what was
>   declared before it loads the suites, or the messages that quote one will not
>   validate.
> 
> Threads are not offered, and the measurement is the reason. They avoid both
> problems above, since they share the interpreter's memory -- but on 4,000 rows
> of the example suite a thread pool took 17.7s against 6.6s sequential, nearly
> three times slower, because the checks are pure Python and spend their time
> contending for the GIL. A mode that loses by that much on the default
> interpreter is a trap, not an option. On a free-threaded build the answer would
> differ; anyone adding it back should measure there first.
> 
> Processes on the same frame took 3.4s against 6.6s, and produced identical
> records.

- `__annotate__(format)`
- `worker_count(workers)`
  - How many workers to use, defaulting to the machine's usable cores.
- `__annotate__(format)`
- `split_frame(df, chunks)`
  - Split *df* into at most *chunks* contiguous pieces, in order.
- `__annotate__(format)`
- `_prepare_worker(package, suites, params)`
  - Rebuild the registry inside a worker process, once.
- `__annotate__(format)`
- `_validate_chunk(chunk, package, suites, params, overrides, on_error)`
  - Validate one chunk. Runs in a worker; must be importable, so not a lambda.
- `__annotate__(format)`
- `_report_chunk(chunk, package, suites, params, overrides, on_error, spec)`
  - Stream one chunk into its own report builder. Runs in a worker.
- `__annotate__(format)`
- `validate_parallel(df, package, suites, overrides, on_error, workers)`
  - Validate every row across several workers, in frame order.
- `__annotate__(format)`
- `codes_a_worker_would_not_have(package, suites)`
  - Codes a worker rebuilding from *package* and *suites* would never register.
- `__annotate__(format)`
- `registry_is_reconstructible(package, suites)`
  - Whether a worker could rebuild the registry this process is holding.
- `__annotate__(format)`
- `report_parallel(df, package, suites, overrides, on_error, workers, key_column, data_columns, include_skipped, include_passed)`
  - Validate across workers *and* stream, returning the merged report builder.

## `params.cpython-312.pyc` (source was 7,173 bytes)

> Named values a rule file may change, declared once in Python.
> 
> A threshold that only ever appears as a literal inside a check can only be
> changed by editing Python. Parameters make it changeable from a rule file, per
> row, without letting rule files define checks or alter what one means.
> 
> They are **global**, not per check: one flat namespace every check can read. A
> limit is usually shared -- the same ``AGE_MAX`` is used by the check that
> enforces it and quoted by the one that reports it -- and per-check parameters
> would make the same value two different settings.
> 
> Declaring them in Python is what keeps a typo catchable. A rule file naming a
> parameter nothing declared is refused at load time, exactly as a rule naming an
> unknown code is. Without a declaration a misspelled parameter would sit in the
> file doing nothing, which is the failure the unknown-key rejection exists to
> prevent.
> 
> Values are permanent identifiers in the same sense test codes are: rule files
> written by non-developers refer to them by name.

- `register_params(defaults)`
  - Declare parameters and their defaults.
- `declared_params()`
  - Every declared parameter and its default (a copy).
- `clear_params()`
  - Forget every declared parameter. For tests of the framework itself.
- `TestParams()`
  - TestParams
  - `__init__(self, values, sources)`
  - `__getitem__(self, name)`
  - `__iter__(self)`
  - `__len__(self)`
  - `__repr__(self)`
  - `source(self, name)`
    - Where this value came from: ``"default"`` or ``"rule <name>"``.
- `_resolve_params(matching_rules)`
  - The parameters in force, given the rules that matched a row.
- `_render_message(message, params)`
  - Fill ``{PARAM}`` placeholders in a message with the values in force.
- `_message_placeholders(message)`
  - The ``{PARAM}`` names a message references.

## `params.cpython-314.pyc` (source was 7,173 bytes)

> Named values a rule file may change, declared once in Python.
> 
> A threshold that only ever appears as a literal inside a check can only be
> changed by editing Python. Parameters make it changeable from a rule file, per
> row, without letting rule files define checks or alter what one means.
> 
> They are **global**, not per check: one flat namespace every check can read. A
> limit is usually shared -- the same ``AGE_MAX`` is used by the check that
> enforces it and quoted by the one that reports it -- and per-check parameters
> would make the same value two different settings.
> 
> Declaring them in Python is what keeps a typo catchable. A rule file naming a
> parameter nothing declared is refused at load time, exactly as a rule naming an
> unknown code is. Without a declaration a misspelled parameter would sit in the
> file doing nothing, which is the failure the unknown-key rejection exists to
> prevent.
> 
> Values are permanent identifiers in the same sense test codes are: rule files
> written by non-developers refer to them by name.

- `__annotate__(format)`
- `register_params(defaults)`
  - Declare parameters and their defaults.
- `__annotate__(format)`
- `declared_params()`
  - Every declared parameter and its default (a copy).
- `__annotate__(format)`
- `clear_params()`
  - Forget every declared parameter. For tests of the framework itself.
- `TestParams()`
  - TestParams
  - `__annotate__(format)`
  - `__init__(self, values, sources)`
  - `__annotate__(format)`
  - `__getitem__(self, name)`
    - No parameter
  - `__annotate__(format)`
  - `__iter__(self)`
  - `__annotate__(format)`
  - `__len__(self)`
  - `__annotate__(format)`
  - `__repr__(self)`
    - TestParams(
  - `__annotate__(format)`
  - `source(self, name)`
    - Where this value came from: ``"default"`` or ``"rule <name>"``.
- `__annotate__(format)`
- `_resolve_params(matching_rules)`
  - The parameters in force, given the rules that matched a row.
- `__annotate__(format)`
- `_render_message(message, params)`
  - Fill ``{PARAM}`` placeholders in a message with the values in force.
- `__annotate__(format)`
- `_message_placeholders(message)`
  - The ``{PARAM}`` names a message references.

## `registry.cpython-312.pyc` (source was 16,799 bytes)

> What checks exist: registering them, loading them, and ordering them.
> 
> A check is a function decorated with :func:`register_check` (or with a
> :func:`check_group`, which shares defaults across a file). Registration happens
> as a side effect of importing the file, and files are named explicitly by
> :func:`load_checks` -- nothing is discovered, inferred or imported on its own.
> 
> The per-row evaluation lives in :mod:`jobcheck.engine`, the rule format in
> :mod:`jobcheck.rules`, and the value types a check returns in
> :mod:`jobcheck.results`.

- `Check()`
  - Check
- `_make_runner(fn, code)`
  - Wrap an author's function so the engine can always call ``fn(row, ctx)``.
- `_register(fn, code, message, default_enabled, depends_on)`
  - Validate one check's declaration and add it to :data:`CHECKS`.
- `_clean_depends_on(depends_on, code)`
  - Validate a ``depends_on`` argument. A bare string is refused deliberately.
- `register_check(code, message, default_enabled, depends_on)`
  - Decorator registering one validation function into :data:`CHECKS`.
  - `decorator(fn)`
- `CheckGroup()`
  - CheckGroup
  - `__init__(self, depends_on, default_enabled)`
  - `__call__(self, code, message, default_enabled, depends_on)`
    - Register one check with this group's defaults applied.
    - `decorator(fn)`
- `check_group(depends_on, default_enabled)`
  - Defaults for a file of checks: prerequisites and default on/off state.
- `load_checks(paths)`
  - Import the named check files so their checks register themselves.
- `loaded_files()`
  - The check files loaded so far, in load order.
- `clear_registry()`
  - Drop every registered check and forget which files were loaded.
- `_topological_order()`
  - Order checks so every prerequisite precedes its dependents.
  - `visit(code)`
- `validate_registry()`
  - Check every ``depends_on`` edge, then cache the evaluation order.
- `evaluation_order()`
  - The checks in the order they are run: every prerequisite before its dependents.
- `load_overrides()`
  - Load override rules from one or more YAML files.
- `registry_table()`
  - One row per registered check, in evaluation order.
- `print_registry()`
  - Print the registered checks, and return the table that was printed.

## `registry.cpython-314.pyc` (source was 16,799 bytes)

> What checks exist: registering them, loading them, and ordering them.
> 
> A check is a function decorated with :func:`register_check` (or with a
> :func:`check_group`, which shares defaults across a file). Registration happens
> as a side effect of importing the file, and files are named explicitly by
> :func:`load_checks` -- nothing is discovered, inferred or imported on its own.
> 
> The per-row evaluation lives in :mod:`jobcheck.engine`, the rule format in
> :mod:`jobcheck.rules`, and the value types a check returns in
> :mod:`jobcheck.results`.

- `Check()`
  - Check
- `__annotate__(format)`
- `_make_runner(fn, code)`
  - Wrap an author's function so the engine can always call ``fn(row, ctx)``.
- `__annotate__(format)`
- `_register(fn, code, message, default_enabled, depends_on)`
  - Validate one check's declaration and add it to :data:`CHECKS`.
- `__annotate__(format)`
- `_clean_depends_on(depends_on, code)`
  - Validate a ``depends_on`` argument. A bare string is refused deliberately.
- `__annotate__(format)`
- `register_check(code, message, default_enabled, depends_on)`
  - Decorator registering one validation function into :data:`CHECKS`.
  - `__annotate__(format)`
  - `decorator(fn)`
- `CheckGroup()`
  - CheckGroup
  - `__annotate__(format)`
  - `__init__(self, depends_on, default_enabled)`
    - check_group
  - `__annotate__(format)`
  - `__call__(self, code, message, default_enabled, depends_on)`
    - Register one check with this group's defaults applied.
    - `__annotate__(format)`
    - `decorator(fn)`
- `__annotate__(format)`
- `check_group(depends_on, default_enabled)`
  - Defaults for a file of checks: prerequisites and default on/off state.
- `__annotate__(format)`
- `load_checks(paths)`
  - Import the named check files so their checks register themselves.
- `__annotate__(format)`
- `loaded_files()`
  - The check files loaded so far, in load order.
- `__annotate__(format)`
- `clear_registry()`
  - Drop every registered check and forget which files were loaded.
- `__annotate__(format)`
- `_topological_order()`
  - Order checks so every prerequisite precedes its dependents.
  - `__annotate__(format)`
  - `visit(code)`
- `__annotate__(format)`
- `validate_registry()`
  - Check every ``depends_on`` edge, then cache the evaluation order.
- `__annotate__(format)`
- `evaluation_order()`
  - The checks in the order they are run: every prerequisite before its dependents.
- `__annotate__(format)`
- `load_overrides()`
  - Load override rules from one or more YAML files.
- `__annotate__(format)`
- `registry_table()`
  - One row per registered check, in evaluation order.
- `__annotate__(format)`
- `print_registry()`
  - Print the registered checks, and return the table that was printed.

## `registry_tables.cpython-312.pyc` (source was 7,163 bytes)

> The tables that show what is registered and what the rules would do to it.
> 
> Reading views only: nothing here decides an outcome, and nothing else in the
> package imports it. Split from :mod:`jobcheck.registry` because the
> two change for unrelated reasons -- a column added to a table has nothing to do
> with the per-row algorithm, and they were sharing one file long enough for it to
> reach twelve hundred lines.
> 
> Every function here prints *and* returns its frame: the print is what a person
> reads at a terminal, the frame is what a test or a notebook filters.
> :func:`get_registry_table` is the exception and only returns, since it is what
> the printers build on.
> 
> The registry module is imported as a module rather than by name, and read at
> call time, because it imports this one back to re-export these names -- and
> because ``TESTS`` is swapped in and out by :class:`Registry`, so the current
> list has to be read when the table is built, not when this module is imported.

- `_rules_for_code(code, overrides)`
  - Rules that reference *code*, in load order.
- `_render_match(rule)`
  - Compact one-cell rendering of a rule's match criteria.
- `get_registry_table(debug)`
  - One row per registered test.
- `print_registry(overrides, debug)`
  - Print the registry table and return the frame behind it.
- `print_registry_with_overrides(overrides, debug)`
  - Print the registry cross-referenced against the loaded override rules.
- `print_override_rules(overrides, debug)`
  - Print one row per override rule (rather than per code).
- `list_rule_codes(rule_name, overrides)`
  - Print and return the exact codes one named rule touches.

## `registry_tables.cpython-314.pyc` (source was 7,163 bytes)

> The tables that show what is registered and what the rules would do to it.
> 
> Reading views only: nothing here decides an outcome, and nothing else in the
> package imports it. Split from :mod:`jobcheck.registry` because the
> two change for unrelated reasons -- a column added to a table has nothing to do
> with the per-row algorithm, and they were sharing one file long enough for it to
> reach twelve hundred lines.
> 
> Every function here prints *and* returns its frame: the print is what a person
> reads at a terminal, the frame is what a test or a notebook filters.
> :func:`get_registry_table` is the exception and only returns, since it is what
> the printers build on.
> 
> The registry module is imported as a module rather than by name, and read at
> call time, because it imports this one back to re-export these names -- and
> because ``TESTS`` is swapped in and out by :class:`Registry`, so the current
> list has to be read when the table is built, not when this module is imported.

- `__annotate__(format)`
- `_rules_for_code(code, overrides)`
  - Rules that reference *code*, in load order.
- `__annotate__(format)`
- `_render_match(rule)`
  - Compact one-cell rendering of a rule's match criteria.
- `__annotate__(format)`
- `get_registry_table(debug)`
  - One row per registered test.
- `__annotate__(format)`
- `print_registry(overrides, debug)`
  - Print the registry table and return the frame behind it.
- `__annotate__(format)`
- `print_registry_with_overrides(overrides, debug)`
  - Print the registry cross-referenced against the loaded override rules.
- `__annotate__(format)`
- `print_override_rules(overrides, debug)`
  - Print one row per override rule (rather than per code).
- `__annotate__(format)`
- `list_rule_codes(rule_name, overrides)`
  - Print and return the exact codes one named rule touches.

## `report.cpython-312.pyc` (source was 11,994 bytes)

> Turning records into a report: the failure table, and how it is shown.
> 
> The report is **long format**: one row per failed check per data row. That is the
> diagnostic unit, it is the only shape that survives being written as CSV, and it
> sorts and filters cleanly downstream.
> 
> There is no command line: a pipeline calls these functions and decides where the
> output goes.

- `render_comments(comments)`
  - Render a check's comments as ``key=value; key=value``, sorted by key.
- `_cell_value(value)`
  - Render a value copied from the data into a report column.
- `_label_value(value)`
  - Render one key value for the report.
- `_row_labels(df, key_column)`
  - One label per row: the key column if given, else the frame's index.
- `_check_data_columns(df, data_columns)`
  - Reject anything that would make the extra columns ambiguous or empty.
- `_wanted_outcomes(include_skipped, include_passed)`
  - Which outcomes belong in the report, given the two include flags.
- `_data_column_values(df, data_columns)`
  - The data-column cells for every row, rendered, one dict per row.
- `_report_row(label, context, record, cause)`
  - One line of the report. The single definition of what a report row is.
- `build_report(run, key_column, data_columns, include_skipped, include_passed)`
  - Build the long-format report: one row per failure.
- `print_report(report, wrap)`
  - Print a report as a bordered table, or a plain line when nothing failed.
- `write_report(report, path)`
  - Write a report to *path* as CSV, creating or replacing the file.
- `row_explanation(records, exclude_passed)`
  - One row per check, in evaluation order: what it did and why.
- `print_row_explanation(records, exclude_passed)`
  - Print what every check did on one row, then the row's root cause.
- `summarise_outcomes(records_per_row)`
  - Count what happened to each check across many rows, worst first.
- `root_cause_counts(records_per_row)`
  - How many rows bottomed out at each code, worst first.
- `print_summary(records_per_row)`
  - Print the per-check summary, worst first, and the root-cause tally.

## `report.cpython-314.pyc` (source was 11,994 bytes)

> Turning records into a report: the failure table, and how it is shown.
> 
> The report is **long format**: one row per failed check per data row. That is the
> diagnostic unit, it is the only shape that survives being written as CSV, and it
> sorts and filters cleanly downstream.
> 
> There is no command line: a pipeline calls these functions and decides where the
> output goes.

- `__annotate__(format)`
- `render_comments(comments)`
  - Render a check's comments as ``key=value; key=value``, sorted by key.
- `__annotate__(format)`
- `_cell_value(value)`
  - Render a value copied from the data into a report column.
- `__annotate__(format)`
- `_label_value(value)`
  - Render one key value for the report.
- `__annotate__(format)`
- `_row_labels(df, key_column)`
  - One label per row: the key column if given, else the frame's index.
- `__annotate__(format)`
- `_check_data_columns(df, data_columns)`
  - Reject anything that would make the extra columns ambiguous or empty.
- `__annotate__(format)`
- `_wanted_outcomes(include_skipped, include_passed)`
  - Which outcomes belong in the report, given the two include flags.
- `__annotate__(format)`
- `_data_column_values(df, data_columns)`
  - The data-column cells for every row, rendered, one dict per row.
- `__annotate__(format)`
- `_report_row(label, context, record, cause)`
  - One line of the report. The single definition of what a report row is.
- `__annotate__(format)`
- `build_report(run, key_column, data_columns, include_skipped, include_passed)`
  - Build the long-format report: one row per failure.
- `__annotate__(format)`
- `print_report(report, wrap)`
  - Print a report as a bordered table, or a plain line when nothing failed.
- `__annotate__(format)`
- `write_report(report, path)`
  - Write a report to *path* as CSV, creating or replacing the file.
- `__annotate__(format)`
- `row_explanation(records, exclude_passed)`
  - One row per check, in evaluation order: what it did and why.
- `__annotate__(format)`
- `print_row_explanation(records, exclude_passed)`
  - Print what every check did on one row, then the row's root cause.
- `__annotate__(format)`
- `summarise_outcomes(records_per_row)`
  - Count what happened to each check across many rows, worst first.
- `__annotate__(format)`
- `root_cause_counts(records_per_row)`
  - How many rows bottomed out at each code, worst first.
- `__annotate__(format)`
- `print_summary(records_per_row)`
  - Print the per-check summary, worst first, and the root-cause tally.

## `results.cpython-312.pyc` (source was 5,902 bytes)

> What a check returns, and what the engine records about one check on one row.
> 
> Two value types live here:
> 
> * :class:`CheckResult` -- what a check function hands back: a status code and any
>   comments it wants carried into the report.
> * :class:`CheckRecord` -- what the engine recorded for one check on one row,
>   including the checks that never ran and why.

- `Status()`
  - Status
- `status_name(code)`
  - The name of a status value, e.g. ``INVALID``.
- `render_status(code)`
  - A status as it appears in a report: ``INVALID (3)``.
- `CheckResult()`
  - CheckResult
  - `__post_init__(self)`
  - `__bool__(self)`
  - `passed(self)`
    - Whether the check was happy with the row.
  - `failed(self)`
    - Whether the check rejected the row.
  - `status(self)`
    - The status name, e.g. ``INVALID``.
- `normalise_result(returned, code)`
  - Turn whatever a check returned into a :class:`CheckResult`.
- `CheckRecord()`
  - CheckRecord
  - `failed(self)`
    - Whether this outcome is a reportable failure, error included.
  - `status_label(self)`
    - The status as a report renders it: ``INVALID (3)``.

## `results.cpython-314.pyc` (source was 5,902 bytes)

> What a check returns, and what the engine records about one check on one row.
> 
> Two value types live here:
> 
> * :class:`CheckResult` -- what a check function hands back: a status code and any
>   comments it wants carried into the report.
> * :class:`CheckRecord` -- what the engine recorded for one check on one row,
>   including the checks that never ran and why.

- `Status()`
  - Status
- `__annotate__(format)`
- `status_name(code)`
  - The name of a status value, e.g. ``INVALID``.
- `__annotate__(format)`
- `render_status(code)`
  - A status as it appears in a report: ``INVALID (3)``.
- `CheckResult()`
  - CheckResult
  - `__annotate__(format)`
  - `__post_init__(self)`
    - CheckResult code must be an integer status, got
  - `__annotate__(format)`
  - `__bool__(self)`
  - `__annotate__(format)`
  - `passed(self)`
    - Whether the check was happy with the row.
  - `__annotate__(format)`
  - `failed(self)`
    - Whether the check rejected the row.
  - `__annotate__(format)`
  - `status(self)`
    - The status name, e.g. ``INVALID``.
- `__annotate__(format)`
- `normalise_result(returned, code)`
  - Turn whatever a check returned into a :class:`CheckResult`.
- `CheckRecord()`
  - CheckRecord
  - `__annotate__(format)`
  - `failed(self)`
    - Whether this outcome is a reportable failure, error included.
  - `__annotate__(format)`
  - `status_label(self)`
    - The status as a report renders it: ``INVALID (3)``.

## `rules.cpython-312.pyc` (source was 6,473 bytes)

> Override rules: the YAML format that switches checks on and off per row.
> 
> The file format, its parser, and the matching it drives. Nothing here knows how
> a check is registered or evaluated -- the loader is handed the set of codes that
> exist, so this module never reaches back into the registry.
> 
> A rule file is a flat list of rules. Precedence is positional: for a given row,
> the last matching rule wins.
> 
> ::
> 
>     - name: legacy feed has no email
>       action: disable          # or enable
>       codes: [EMAIL_PRESENT, EMAIL_FORMAT]
>       column: source           # omit column and pattern to match every row
>       pattern: "legacy_*"      # a glob, as in fnmatch

- `OverrideRule()`
  - OverrideRule
  - `enables(self)`
    - Whether this rule turns its codes on rather than off.
- `parse_rule(raw, source_file, known_codes)`
  - Validate and build one rule, failing loudly at load time.
- `parse_file(path, known_codes)`
  - Parse one YAML file into rules. The file is a flat top-level list.
- `load_rules(paths, known_codes)`
  - Parse several files, rejecting duplicate rule names across all of them.
- `rule_matches(rule, row)`
  - Whether *rule* applies to *row*.

## `rules.cpython-314.pyc` (source was 6,473 bytes)

> Override rules: the YAML format that switches checks on and off per row.
> 
> The file format, its parser, and the matching it drives. Nothing here knows how
> a check is registered or evaluated -- the loader is handed the set of codes that
> exist, so this module never reaches back into the registry.
> 
> A rule file is a flat list of rules. Precedence is positional: for a given row,
> the last matching rule wins.
> 
> ::
> 
>     - name: legacy feed has no email
>       action: disable          # or enable
>       codes: [EMAIL_PRESENT, EMAIL_FORMAT]
>       column: source           # omit column and pattern to match every row
>       pattern: "legacy_*"      # a glob, as in fnmatch

- `OverrideRule()`
  - OverrideRule
  - `__annotate__(format)`
  - `enables(self)`
    - Whether this rule turns its codes on rather than off.
- `__annotate__(format)`
- `parse_rule(raw, source_file, known_codes)`
  - Validate and build one rule, failing loudly at load time.
- `__annotate__(format)`
- `parse_file(path, known_codes)`
  - Parse one YAML file into rules. The file is a flat top-level list.
- `__annotate__(format)`
- `load_rules(paths, known_codes)`
  - Parse several files, rejecting duplicate rule names across all of them.
- `__annotate__(format)`
- `rule_matches(rule, row)`
  - Whether *rule* applies to *row*.

## `run.cpython-312.pyc` (source was 10,756 bytes)

> What a validation run produced, as one object rather than four loose values.
> 
> Running the tests over a frame yields a record per test per row. Everything
> downstream -- the failure table, the summary, a single row's explanation --
> needs those records *and* the frame they came from, because a report that
> identifies rows by frame index is unreadable the moment the frame has been
> filtered.
> 
> Keeping them together is what :class:`ValidationRun` is for. The alternative,
> passing a list of lists alongside the frame it belongs to into every reporting
> function, made the caller responsible for keeping two things in step and gave
> the length check nothing better to do than notice when they had drifted apart.
> 
> Three levels, each named for what it holds:
> 
> - :class:`ValidationRun` -- the whole frame: its traces, the rules used, timings.
> - :class:`RowTrace` -- one row: every record, in evaluation order.
> - ``TestRecord`` -- one test on one row. Defined in
>   :mod:`jobcheck.results`, next to what a test returns.

- `RunStats()`
  - RunStats
  - `rows_per_second(self)`
    - Throughput, or infinity for a run too fast to time.
- `RowTrace()`
  - RowTrace
  - `failures(self)`
    - The failing records, in evaluation order: the first is the root cause.
  - `root_cause(self)`
    - The shallowest failure's code, or ``None`` for a row that passed.
  - `passed(self)`
    - Whether nothing failed on this row.
- `ValidationRun()`
  - ValidationRun
  - `from_records(cls, df, records, overrides, stats)`
    - Build a run from records collected elsewhere, such as by workers.
  - `__len__(self)`
    - The number of rows validated.
  - `__iter__(self)`
    - Iterate the traces, in frame order.
  - `records(self)`
    - The raw records, one list per row, for a caller that wants them.
  - `failed_rows(self)`
    - Traces for the rows that failed something.
  - `root_causes(self)`
    - Each row's root cause, in frame order; ``None`` where it passed.
  - `report(self, key_column, data_columns, include_skipped, include_passed)`
    - The long-format failure table. See :func:`report.build_report`.
  - `summary(self)`
    - Per-test counts, worst first. See :func:`report.summarise_outcomes`.
  - `explain(self, position)`
    - One row's trace, by position in the frame.
- `iter_traces(df, overrides, context_builder, on_error, progress, progress_every)`
  - Yield one :class:`RowTrace` at a time, holding no more than one at once.
- `validate(df, overrides, context_builder, on_error, progress, progress_every)`
  - Run every test against every row of *df*.

## `run.cpython-314.pyc` (source was 10,756 bytes)

> What a validation run produced, as one object rather than four loose values.
> 
> Running the tests over a frame yields a record per test per row. Everything
> downstream -- the failure table, the summary, a single row's explanation --
> needs those records *and* the frame they came from, because a report that
> identifies rows by frame index is unreadable the moment the frame has been
> filtered.
> 
> Keeping them together is what :class:`ValidationRun` is for. The alternative,
> passing a list of lists alongside the frame it belongs to into every reporting
> function, made the caller responsible for keeping two things in step and gave
> the length check nothing better to do than notice when they had drifted apart.
> 
> Three levels, each named for what it holds:
> 
> - :class:`ValidationRun` -- the whole frame: its traces, the rules used, timings.
> - :class:`RowTrace` -- one row: every record, in evaluation order.
> - ``TestRecord`` -- one test on one row. Defined in
>   :mod:`jobcheck.results`, next to what a test returns.

- `RunStats()`
  - RunStats
  - `__annotate__(format)`
  - `rows_per_second(self)`
    - Throughput, or infinity for a run too fast to time.
- `RowTrace()`
  - RowTrace
  - `__annotate__(format)`
  - `failures(self)`
    - The failing records, in evaluation order: the first is the root cause.
  - `__annotate__(format)`
  - `root_cause(self)`
    - The shallowest failure's code, or ``None`` for a row that passed.
  - `__annotate__(format)`
  - `passed(self)`
    - Whether nothing failed on this row.
- `ValidationRun()`
  - ValidationRun
  - `__annotate__(format)`
  - `from_records(cls, df, records, overrides, stats)`
    - Build a run from records collected elsewhere, such as by workers.
  - `__annotate__(format)`
  - `__len__(self)`
    - The number of rows validated.
  - `__annotate__(format)`
  - `__iter__(self)`
    - Iterate the traces, in frame order.
  - `__annotate__(format)`
  - `records(self)`
    - The raw records, one list per row, for a caller that wants them.
  - `__annotate__(format)`
  - `failed_rows(self)`
    - Traces for the rows that failed something.
  - `__annotate__(format)`
  - `root_causes(self)`
    - Each row's root cause, in frame order; ``None`` where it passed.
  - `__annotate__(format)`
  - `report(self, key_column, data_columns, include_skipped, include_passed)`
    - The long-format failure table. See :func:`report.build_report`.
  - `__annotate__(format)`
  - `summary(self)`
    - Per-test counts, worst first. See :func:`report.summarise_outcomes`.
  - `__annotate__(format)`
  - `explain(self, position)`
    - One row's trace, by position in the frame.
- `__annotate__(format)`
- `iter_traces(df, overrides, context_builder, on_error, progress, progress_every)`
  - Yield one :class:`RowTrace` at a time, holding no more than one at once.
- `__annotate__(format)`
- `validate(df, overrides, context_builder, on_error, progress, progress_every)`
  - Run every test against every row of *df*.

## `tables.cpython-312.pyc` (source was 2,624 bytes)

> Plain-text table rendering, shared by the registry view and the report.
> 
> ``DataFrame.to_string()`` is cramped and unbordered for auditing, and a table
> library would be a runtime dependency for output formatting alone, so this small
> renderer lives here instead.

- `is_null(value)`
  - Whether a single cell is null.
- `format_table(df, wrap_columns)`
  - Render a DataFrame as a bordered plain-text table using only the stdlib.

## `tables.cpython-314.pyc` (source was 2,624 bytes)

> Plain-text table rendering, shared by the registry view and the report.
> 
> ``DataFrame.to_string()`` is cramped and unbordered for auditing, and a table
> library would be a runtime dependency for output formatting alone, so this small
> renderer lives here instead.

- `__annotate__(format)`
- `is_null(value)`
  - Whether a single cell is null.
- `__annotate__(format)`
- `format_table(df, wrap_columns)`
  - Render a DataFrame as a bordered plain-text table using only the stdlib.

