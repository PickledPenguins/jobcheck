# Recovered interface: `tests`

## `catalog.cpython-312.pyc` (source was 3,047 bytes)

> Shared machinery for the example and failure catalogs.
> 
> A case is a directory holding:
> 
>     cmd                   the command, run from the project root
>     README.md             what it demonstrates
>     expected_stdout.txt   examples: stdout, compared byte for byte
>     expected_stderr.txt   failures: the final traceback line, compared exactly
>     exit_code             the expected exit status
> 
> Failure cases compare only the last line of stderr -- the exception type and
> message the user actually reads. The frames above it name absolute paths and
> line numbers that change with any edit, so they are normalised away.
> 
> One more normalisation applies to both kinds: the absolute project root is
> replaced by ``<project>``, so ``source_file`` columns in ``-vv`` output do not
> pin the catalog to one machine.

- `CaseResult()`
  - CaseResult
- `case_dirs(kind)`
  - Every case directory under tests/<kind>, sorted for a stable test order.
- `run_case(case)`
  - Run one case's command from the project root.
- `normalise(text)`
  - Replace the absolute project root, which differs on every machine.
- `stderr_tail(text)`
  - The last non-blank line of stderr: the message a user actually reads.
- `run_all_cases(cases, workers)`
  - Run every case, several at a time, keyed by case directory.

## `conftest.cpython-312-pytest-9.1.1.pyc` (source was 2,569 bytes)

> Shared fixtures.
> 
> The registry is module-level state, so every test starts from an empty one and
> leaves one behind: a test that registered checks must not decide what the next
> test sees.

- `_empty_registry()`
  - Empty the registry before and after every test.
- `simple_checks()`
  - Three checks in one chain: present -> numeric -> in range.
  - `present(row)`
  - `numeric(row)`
  - `in_range(row)`
- `frame()`
  - Four rows: one clean, one out of range, one malformed, one missing.
- `write_check_file(directory, name, body)`
  - Write a check file and return its path, for tests of loading.
- `write_rules(directory, name, body)`
  - Write a rule file and return its path.

## `golden_fixture.cpython-312.pyc` (source was 4,982 bytes)

> The fixed inputs behind the golden output files.
> 
> One frame, one rule file, one set of suites, chosen to exercise every column and
> every outcome the report can show: a clean row, a value failure, a cascade from a
> missing field, a rule-disabled test, and a row whose key is missing. Nothing here
> varies between machines or runs -- no clock, no paths, no ordering that depends
> on the filesystem -- which is what lets the output be compared byte for byte.
> 
> Imported by both ``tests/test_golden_output.py`` and ``scripts/regen_golden.py``,
> so the test and the regeneration can never disagree about the input.

- `frame()`
  - The rows every golden file is produced from.
- `render_all()`
  - Every golden view, keyed by filename, produced through the public API.
  - `captured(render)`
    - Whatever a print function put on stdout.
- `read_golden(name)`
- `write_golden(name, text)`

## `test_api_contract.cpython-312-pytest-9.1.1.pyc` (source was 7,807 bytes)

> Interface tests: the public surface other code depends on.
> 
> These are the checks that fail when an export is forgotten, a default changes, or
> a permanent identifier moves -- the kind of break that is invisible until someone
> else's import fails.

- `test_every_exported_name_exists()`
- `test_all_is_sorted_and_free_of_duplicates()`
- `test_every_tool_the_suite_relies_on_is_declared()`
  - Regression: hypothesis sat in an optional extra CI never installed, so
- `test_the_package_states_a_version()`
  - Anyone depending on this needs to be able to say which behaviour they have.
- `test_the_rule_parser_does_not_import_the_registry()`
  - The seam that keeps rules.py a file about a file format: the registry hands
- `test_every_public_function_is_exported()`
  - Regression: root_cause_counts was documented but never re-exported, so
- `test_status_values_are_permanent()`
  - Reports and saved data refer to these numbers; they never move.
- `test_outcome_names_are_permanent()`
- `test_report_columns_are_stable()`
  - Anything reading the CSV depends on these names and this order.
- `test_registry_table_columns_are_stable(example_suites)`
- `defaults(fn)`
- `test_public_defaults(fn, expected)`
- `test_load_suites_requires_the_package_to_load_from()`
  - This package ships no tests, so a default would name the wrong tree.
- `test_validate_row_returns_outcomes_not_a_separate_result_type(fresh_registry)`
- `test_root_cause_accepts_either_functions_output(fresh_registry)`
- `test_pass_is_a_shared_singleton()`
- `_row()`

## `test_benchmarks.cpython-312-pytest-9.1.1.pyc` (source was 6,356 bytes)

> The benchmark harness runs and reports what it claims to.
> 
> These are not benchmarks. They are the guard that stops ``scripts/benchmark.py``
> rotting between the rare occasions somebody runs it for real: every scenario is
> exercised at a size small enough to be part of a test suite, and the numbers are
> checked for internal consistency rather than against a threshold.
> 
> A timing threshold in a test suite fails on a busy machine and teaches people to
> ignore the suite, so there is deliberately none here.

- `test_build_frame_cycles_templates_and_numbers_rows()`
  - The synthetic frame has the requested size, unique ids, every template.
- `test_build_frame_of_one_row_is_the_first_template()`
  - The smallest frame the CLI allows still builds.
- `test_write_rule_file_produces_loadable_rules(tmp_path, example_suites)`
  - Generated rules parse through the real loader, not a private shortcut.
- `test_generated_rules_do_not_change_which_tests_run(tmp_path, example_suites)`
  - The rules scenario must measure matching cost, not fewer tests running.
- `test_run_benchmarks_measures_every_scenario(example_suites)`
  - Every scenario reports a positive, self-consistent measurement.
- `test_render_lines_up_with_its_header()`
  - The table renders one line per measurement under a header of equal width.
- `test_main_writes_json_that_round_trips(tmp_path, capsys, example_suites)`
  - ``--json`` records the run's shape alongside its numbers.
- `test_sizes_below_one_are_rejected(flag)`
  - A zero or negative size would divide by zero or measure nothing.
- `test_the_harness_runs_without_the_suites_fixture(fresh_registry)`
  - It has to work as a script, not only under a fixture that helps it.

## `test_context_unit.cpython-312-pytest-9.1.1.pyc` (source was 2,119 bytes)

> The per-row context base class and its default builder.

- `TestBuildContext()`
  - TestBuildContext
  - `test_the_default_builder_returns_an_empty_context(self)`
  - `test_a_context_can_be_subclassed_with_fields(self)`
    - `Mine()`
      - TestBuildContext.test_a_context_can_be_subclassed_with_fields.<locals>.Mine
- `TestContextReachesAChecks()`
  - TestContextReachesAChecks
  - `test_a_two_argument_check_receives_the_built_context(self)`
    - `Mine()`
      - TestContextReachesAChecks.test_a_two_argument_check_receives_the_built_context.<locals>.Mine
    - `c(row, ctx)`
  - `test_a_one_argument_check_never_sees_the_context(self)`
    - `c(row)`
  - `test_the_default_builder_is_used_when_none_is_given(self)`
    - `c(row, ctx)`

## `test_e2e_catalogs.cpython-312-pytest-9.1.1.pyc` (source was 2,097 bytes)

> End-to-end: run every catalog case through the real entry point.
> 
> These double as the project's worked examples and troubleshooting reference, so
> a behaviour change fails here before it reaches a user.

- `case_results()`
  - Every case run once, concurrently, for the whole session.
- `case_id(case)`
- `test_example_case_matches_its_expected_output(case, case_results)`
- `test_failure_case_matches_its_expected_message(case, case_results)`
- `test_every_case_documents_itself(case)`

## `test_engine_unit.cpython-312-pytest-9.1.1.pyc` (source was 12,818 bytes)

> Running the checks: one row, and a whole frame.

- `outcomes(records)`
- `disable(codes, column, pattern, name)`
- `enable(codes, column, pattern, name)`
- `TestExplainRow()`
  - TestExplainRow
  - `test_records_every_check_in_evaluation_order(self, simple_checks)`
  - `test_a_failure_carries_the_message_status_and_comments(self, simple_checks)`
  - `test_a_passing_check_carries_no_message(self, simple_checks)`
  - `test_a_blocked_check_is_skipped_naming_its_prerequisite(self, simple_checks)`
  - `test_a_skip_names_every_blocking_prerequisite(self)`
    - `a(row)`
    - `b(row)`
    - `c(row)`
  - `test_the_layer_of_each_check_is_recorded(self, simple_checks)`
  - `test_a_check_that_raises_is_recorded_not_propagated(self)`
    - `boom(row)`
  - `test_the_error_record_carries_the_traceback(self)`
    - `boom(row)`
  - `test_an_errored_check_blocks_its_dependents(self)`
    - `boom(row)`
    - `after(row)`
  - `test_a_check_returning_something_unusable_still_raises(self)`
    - `bad(row)`
  - `test_rejects_a_row_with_duplicate_column_labels(self, simple_checks)`
  - `test_a_check_off_by_default_is_recorded_as_disabled(self)`
    - `off(row)`
  - `test_a_disabled_check_blocks_its_dependents(self)`
    - `off(row)`
    - `after(row)`
  - `test_does_not_mutate_the_row(self, simple_checks)`
- `TestOverridesPerRow()`
  - TestOverridesPerRow
  - `test_a_matching_rule_disables_a_check_and_names_itself(self, simple_checks)`
  - `test_a_rule_that_does_not_match_leaves_the_check_on(self, simple_checks)`
  - `test_a_rule_matching_every_row_applies_without_a_column(self, simple_checks)`
  - `test_a_rule_can_enable_a_check_that_is_off_by_default(self)`
    - `off(row)`
  - `test_the_last_matching_rule_wins(self, simple_checks)`
  - `test_a_rule_naming_an_unregistered_code_is_ignored(self, simple_checks)`
- `TestValidateRow()`
  - TestValidateRow
  - `test_returns_only_the_failures(self, simple_checks)`
  - `test_a_clean_row_has_no_failures(self, simple_checks)`
  - `test_skipped_and_disabled_checks_are_absent(self, simple_checks)`
  - `test_an_errored_check_is_reported_as_a_failure(self)`
    - `boom(row)`
- `TestRootCause()`
  - TestRootCause
  - `test_none_for_a_row_that_passed(self, simple_checks)`
  - `test_the_shallowest_failure_wins(self, simple_checks)`
  - `test_the_shallower_of_two_untouching_chains_wins(self)`
    - `base(row)`
    - `deep(row)`
    - `shallow(row)`
  - `test_accepts_the_output_of_validate_row(self, simple_checks)`
- `TestRowTrace()`
  - TestRowTrace
  - `test_reports_its_failures_in_evaluation_order(self, simple_checks, frame)`
  - `test_passed_is_true_only_when_nothing_failed(self, simple_checks, frame)`
  - `test_carries_the_rows_position(self, simple_checks, frame)`
  - `test_root_cause_of_one_row(self, simple_checks, frame)`
- `TestValidate()`
  - TestValidate
  - `test_one_trace_per_row(self, simple_checks, frame)`
  - `test_counts_failures_and_errors_separately(self, simple_checks, frame)`
    - `boom(row)`
  - `test_keeps_the_frame_and_the_rules_it_was_given(self, simple_checks, frame)`
  - `test_failed_rows_are_the_traces_that_failed(self, simple_checks, frame)`
  - `test_root_causes_are_one_per_row_in_frame_order(self, simple_checks, frame)`
  - `test_explain_returns_one_rows_trace(self, simple_checks, frame)`
  - `test_explain_rejects_a_position_outside_the_frame(self, simple_checks, frame)`
  - `test_explain_rejects_a_negative_position(self, simple_checks, frame)`
  - `test_an_empty_frame_produces_no_traces(self, simple_checks)`
  - `test_the_context_builder_is_called_once_per_row(self, simple_checks, frame)`
  - `test_a_context_builder_returning_none_is_allowed(self, simple_checks, frame)`
- `TestIterTraces()`
  - TestIterTraces
  - `test_yields_one_trace_at_a_time(self, simple_checks, frame)`
  - `test_it_is_a_generator_so_a_caller_can_stop_early(self, simple_checks, frame)`
  - `test_the_rules_reach_every_row(self, simple_checks, frame)`
- `TestValidationRunConstruction()`
  - TestValidationRunConstruction
  - `test_can_be_built_from_traces_directly(self, simple_checks, frame)`
  - `test_iterating_a_run_yields_its_traces(self, simple_checks, frame)`
  - `test_a_trace_defaults_to_no_records(self)`

## `test_error_messages.cpython-312-pytest-9.1.1.pyc` (source was 10,991 bytes)

> The exact text of the errors a person is most likely to hit.
> 
> Every other suite asserts a *phrase* from a message, which is the right thing
> when the point is which error fired. It leaves the rest of the sentence
> unpinned, though: a message is assembled from several string literals, and a
> test matching one of them says nothing about the others. Mutation testing found
> this directly -- rewriting the middle of a three-line explanation changed
> nothing any test could see.
> 
> These messages are the product. A rule file is edited by people who do not read
> Python, and the message is the whole of what they get back, so it is worth
> pinning whole rather than by keyword.
> 
> Kept in one file so the wording can be reviewed in one place, and so a
> deliberate rewording is one obvious diff rather than a hunt through six suites.

- `write(tmp_path, text)`
- `message_of(excinfo)`
  - The exception's text, with the temporary path made comparable.
- `test_fail_fast_with_workers(example_suites)`
- `test_a_registry_that_cannot_be_rebuilt(fresh_registry)`
- `test_too_few_workers(workers)`
- `test_too_few_chunks()`
- `test_an_unknown_parameter_in_a_rule_file(fresh_registry, tmp_path)`
- `test_a_parameter_of_the_wrong_type(fresh_registry, tmp_path)`
- `test_a_set_rule_carrying_codes(fresh_registry, tmp_path)`
- `test_params_on_a_rule_that_is_not_a_set(fresh_registry, tmp_path)`
- `test_a_set_rule_with_no_parameters(fresh_registry, tmp_path)`
- `test_an_undeclared_placeholder_in_a_message(fresh_registry)`
  - `check(row)`
- `test_a_parameter_name_that_is_not_upper_case(fresh_registry)`
- `test_a_parameter_default_a_rule_file_could_not_carry(fresh_registry)`
- `test_redeclaring_a_parameter_differently(fresh_registry)`
- `test_register_params_given_something_that_is_not_a_mapping(fresh_registry)`
- `test_reading_a_parameter_that_was_never_declared()`
- `test_explaining_a_row_outside_the_frame(fresh_registry)`
- `test_a_progress_interval_below_one(fresh_registry)`
- `test_a_data_column_colliding_with_a_report_column(fresh_registry)`
  - The fix is a rename, and the message shows the exact call that does it.
- `test_a_data_column_that_is_not_in_the_frame(fresh_registry)`
  - The message lists the columns there are, which is what the fix needs.
- `test_a_key_column_that_is_not_in_the_frame(fresh_registry)`

## `test_examples.cpython-312-pytest-9.1.1.pyc` (source was 3,175 bytes)

> The example catalog: every case run through the real entry point.
> 
> Each directory under ``tests/examples/<level>/`` is one case: a ``cmd`` to run,
> the ``expected_stdout.txt`` it must print, an ``exit_code``, and a ``README.md``
> saying what it demonstrates. They run as a subprocess, so the entry point, the
> argument parser and the printing are all under test rather than mocked.
> 
> Two things are normalised before comparing, and nothing else: the repository's
> own absolute path becomes ``<repo>``, and the terminal width is pinned to 80 so
> argparse wraps its help the same way everywhere.

- `case_id(case)`
- `test_example_case(case, tmp_path)`
  - The case's command prints exactly what its expected output says.
- `test_every_case_documents_itself(case)`
  - A case with no README is a fixture, not an example.
- `test_the_catalog_covers_all_three_levels()`
  - Counts, so a level cannot quietly empty out.
- `test_a_complex_case_says_why_the_combination_is_the_point()`
  - The interaction is what a complex case is for, so it has to be written down.

## `test_fuzz.cpython-312-pytest-9.1.1.pyc` (source was 6,600 bytes)

> Generated input, seeded so a failure reproduces.
> 
> Every example in the other suites was written by whoever wrote the code, which is
> the weakness of examples. These feed the two parsers and the renderer input
> nobody chose by hand, and assert the shape of the answer rather than its content:
> either it works, or it fails the way the library says it fails, and never with an
> unexpected exception type.
> 
> Seeded from a constant, so a failing case is reproducible; the seed appears in
> the assertion message.

- `random_scalar(rng)`
- `random_name(rng)`
- `random_rule(rng)`
  - A rule-shaped mapping, valid about as often as not.
- `test_the_rule_parser_either_loads_or_raises_valueerror(fresh_registry, tmp_path)`
- `random_frame(rng)`
- `test_the_engine_holds_its_invariants_on_generated_frames(example_suites)`
  - The three properties the whole design rests on, over input nobody chose:
- `test_rendering_survives_whatever_a_test_puts_in_its_comments(example_suites)`
  - Comments carry data, and data is hostile: the renderer must not raise, and

## `test_golden_output.cpython-312-pytest-9.1.1.pyc` (source was 3,778 bytes)

> Golden files: the exact text the library produces, compared byte for byte.
> 
> The catalog already pins what `examples/main.py` prints, but that output carries the
> registry tables and the demo preamble around it, so a change to the report shows
> up as a diff in a 9 KB file. These are tight: one view per file, produced through
> the public API from the fixed inputs in `tests/golden_fixture.py`, so a diff
> points straight at what moved.
> 
> Regenerate with `python3 scripts/regen_golden.py` after an intended change, then
> read the diff.

- `test_output_matches_its_golden_file(fresh_registry, name)`
- `test_every_golden_file_is_accounted_for()`
  - A golden nobody compares is a file that rots quietly. README.md is the
- `test_the_golden_report_shows_every_outcome_the_report_can_carry(fresh_registry)`
  - The fixture earns its place only if it exercises the whole shape.
- `test_the_data_columns_golden_shows_them_next_to_the_row_key()`
- `test_a_written_file_is_byte_for_byte_the_golden_csv(fresh_registry, tmp_path)`
  - Pins the file on disk, not just the string: encoding, line endings, and the
- `test_the_golden_csv_parses_back_into_the_same_frame(fresh_registry)`

## `test_groups_unit.cpython-312-pytest-9.1.1.pyc` (source was 7,464 bytes)

> Unit tests: test_group defaults and how they combine with a test's own.

- `register(group, code)`
  - `_test(row)`
- `by_code(code)`
- `test_a_group_supplies_its_prerequisites(fresh_registry)`
- `test_a_test_adds_its_own_prerequisites_to_the_group_s(fresh_registry)`
  - Union, not replacement: 'this file waits for X' cannot be undone per test.
- `test_a_prerequisite_named_twice_is_kept_once(fresh_registry)`
- `test_a_group_prerequisite_repeated_in_its_own_list_is_kept_once(fresh_registry)`
- `test_a_group_member_cannot_be_its_own_prerequisite(fresh_registry)`
  - The group's prerequisites are unconditional, so a presence test belongs in a
- `test_a_group_sets_the_default_state(fresh_registry)`
- `test_a_test_can_override_the_group_default_state(fresh_registry)`
- `test_a_group_can_name_the_suite(fresh_registry)`
- `test_a_test_can_override_the_group_suite(fresh_registry)`
- `test_without_a_declared_suite_the_module_decides(fresh_registry)`
- `test_a_group_carries_description_and_message_through(fresh_registry)`
- `test_group_members_run_like_any_other_test(fresh_registry)`
  - `_test(row)`
- `test_two_groups_in_one_file_stay_separate(fresh_registry)`
- `test_a_bad_declaration_is_rejected_at_registration(fresh_registry, code, message, expected)`
  - `check(row)`
- `test_a_non_string_prerequisite_is_rejected(fresh_registry)`
- `test_a_string_prerequisite_is_rejected_not_split_into_characters(fresh_registry)`
  - Regression: a bare string passed the element check, registering one
- `test_a_group_rejects_a_string_of_prerequisites(fresh_registry)`
- `test_a_test_needing_a_keyword_argument_is_rejected_at_registration(fresh_registry)`
  - Regression: it registered cleanly and then errored on every single row.
  - `check(row)`
- `test_a_keyword_argument_with_a_default_is_fine(fresh_registry)`
  - `check(row)`
- `test_every_declaration_field_is_validated(fresh_registry, kwargs, expected)`
  - `check(row)`

## `test_integration.cpython-312-pytest-9.1.1.pyc` (source was 9,019 bytes)

> Integration: real files on disk, a real DataFrame, both loaders end to end.

- `codes(df)`
- `validated(overrides)`
- `test_shipped_root_rule_file_drives_a_whole_frame(example_suites)`
- `test_directory_loading_produces_the_same_first_two_rules(example_suites)`
- `test_directory_loading_leaves_the_legacy_enable_in_force(example_suites)`
- `test_file_order_decides_precedence_across_directories(example_suites)`
- `test_errors_column_projects_to_text_for_export(example_suites, tmp_path)`
- `test_a_written_report_reads_back_as_a_frame(example_suites, tmp_path)`
- `test_a_table_report_renders_the_comments_a_reader_needs(example_suites)`
- `test_a_rule_file_written_at_runtime_is_picked_up(example_suites, tmp_path)`
- `test_loading_leaves_no_stray_files_behind(example_suites, tmp_path)`
- `test_a_new_suite_added_at_runtime_is_discovered(fresh_registry, tmp_path)`
  - The discovery contract: a subpackage with an __init__.py and a test_*.py.
- `test_source_file_of_a_shipped_check_exists_on_disk(example_suites)`
- `test_a_written_report_round_trips_through_a_spreadsheet_reader(example_suites, tmp_path)`
  - What a person actually does: write the CSV, open it, read the failures.
- `test_the_table_and_csv_forms_carry_the_same_failures(example_suites)`
- `test_explaining_a_row_agrees_with_the_report(example_suites)`
  - The two views are the same data: the report's first line for a row is the
- `test_a_rule_file_and_a_suite_change_the_same_report(example_suites)`
  - The two knobs a user has, exercised against one frame.

## `test_interface_cli.cpython-312-pytest-9.1.1.pyc` (source was 8,932 bytes)

> Interface tests: the CLI contract — flags, defaults, exit codes, routing.

- `isolated_registry(fresh_registry)`
  - Give every test here its own registry.
- `test_defaults_when_no_flags_are_given()`
- `test_suites_flatten_in_the_order_given(argv)`
- `test_overrides_flatten_in_the_order_given(argv)`
- `test_verbose_counts(argv, expected)`
- `test_passing_a_suite_replaces_the_default_rather_than_extending_it()`
- `test_success_exits_zero()`
- `test_failing_rows_still_exit_zero()`
  - Validation failures are data, not a process error.
- `test_the_report_names_each_row_by_its_key_column_and_root_cause()`
- `test_cascading_tests_are_absent_from_the_report()`
  - Row id=6 has no age at all: only AGE_PRESENT is reported for it.
- `test_include_skipped_shows_what_a_failure_blocked()`
- `test_the_csv_report_format_is_selectable()`
- `test_the_report_can_be_written_to_a_file(tmp_path)`
- `test_explain_prints_one_row_and_its_root_cause()`
- `test_explain_outside_the_frame_exits_two()`
- `test_summary_reports_counts_and_root_causes()`
- `test_unknown_flag_exits_two()`
- `test_flag_without_its_value_exits_two()`
- `test_unknown_suite_exits_one()`
- `test_missing_override_file_exits_one()`
- `test_results_go_to_stdout_and_nothing_to_stderr()`
- `test_errors_go_to_stderr_and_leave_stdout_clean()`
- `test_default_run_prints_the_registry_tables_and_the_failures()`
- `test_debug_one_adds_the_cross_reference_column_only()`
- `test_debug_two_adds_source_files_and_the_by_rule_table()`
- `test_suite_selection_changes_which_codes_are_registered()`
- `test_narrowing_suites_without_narrowing_rules_exits_one()`
  - The default rule file names soft_tests codes, so loading only hard_tests
- `test_main_hard_only_registers_no_email_checks()`
- `test_main_hard_only_rejects_an_unknown_flag()`
  - It takes no options, but still parses, so a mistyped flag is not ignored.
- `test_main_hard_only_has_help()`

## `test_lint_unit.cpython-312-pytest-9.1.1.pyc` (source was 37,624 bytes)

> Unit tests: every rule lint, its severity, and how findings are rendered.

- `rule(name, action, codes, criteria, match_all, source_file)`
  - Build a rule directly, so a lint can be exercised without a YAML file.
- `checks(findings)`
  - The lint names that fired, for asserting on without message text.
- `test_rule_past_its_expiry_is_an_error()`
  - A suppression that was meant to be temporary and was not.
- `test_rule_expiring_today_is_still_live()`
  - Expiry is the last day the rule applies, not the first day it does not.
- `test_rule_without_an_expiry_is_never_reported_for_one()`
  - The key is optional; absence is not a finding.
- `test_expiry_defaults_to_the_real_clock()`
  - Left unset, ``today`` is today -- the only clock read in the library.
- `test_wildcard_pattern_is_reported_as_a_hidden_match_all(pattern)`
  - A rule that matches everything should say so with ``match: all``.
- `test_unescaped_dot_in_a_literal_pattern_is_reported()`
  - ``1.5`` also matches ``1x5``: the classic non-developer regex mistake.
- `test_unanchored_literal_pattern_is_an_informational_note()`
  - ``BATCH`` matches ``PREBATCH`` too, which is worth mentioning, not warning.
- `test_anchored_pattern_is_left_alone()`
  - A pattern that already uses regex syntax is assumed to be deliberate.
- `test_a_match_all_rule_has_no_patterns_to_complain_about()`
  - ``match: all`` carries no criteria, so no pattern lint can apply.
- `test_rule_asking_for_the_default_state_changes_nothing()`
  - Disabling a code that is already off is a no-op the author meant as work.
- `test_rule_changing_at_least_one_code_is_not_redundant()`
  - Only a rule where *every* code already has the wanted state is a no-op.
- `test_code_that_is_off_and_never_enabled_is_dead()`
  - A test off by default that no rule turns on can never run.
- `test_code_enabled_by_some_rule_is_not_dead()`
  - Any enabling rule is enough, even one that matches narrowly.
- `test_rule_overruled_by_a_later_match_all_is_shadowed()`
  - Precedence is positional, so a later match-all with the opposite action wins.
- `test_identical_criteria_with_the_opposite_action_shadow()`
  - Same rows, opposite actions: the earlier rule can never take effect.
- `test_different_criteria_are_not_claimed_to_shadow()`
  - One regex being a superset of another is undecidable, so it is not guessed.
- `test_rules_sharing_no_codes_do_not_shadow()`
  - Shadowing is per code: two rules on different codes cannot conflict.
- `test_same_action_twice_is_not_shadowing()`
  - Two rules agreeing is redundancy at worst, not one silently losing.
- `test_conflicting_rules_name_the_winner()`
  - Positional precedence is invisible in the file, so the winner is spelled out.
- `test_one_rule_per_code_is_no_conflict()`
  - Nothing to disambiguate when only one rule touches a code.
- `test_criterion_on_a_missing_column_never_applies()`
  - The one rule mistake nothing else can catch: a column that is not there.
- `test_rule_matching_no_rows_is_reported()`
  - A rule whose column exists but whose pattern never hits this data.
- `test_rule_matching_every_row_suggests_match_all()`
  - Matching all of them is legal but should be said plainly.
- `test_null_values_never_match_as_the_engine_treats_them()`
  - The lint must agree with the engine, where a null never matches.
- `test_match_all_rules_are_not_counted_against_data()`
  - A match-all rule matches every row by definition; saying so is noise.
- `test_an_empty_frame_produces_no_data_findings()`
  - Nothing can be concluded about matching from a frame with no rows.
- `test_a_missing_column_suppresses_the_row_count_checks()`
  - One finding about the absent column, not three about what it cannot match.
- `test_data_checks_are_skipped_without_a_frame()`
  - The static lints run on their own; the data ones need data.
- `test_findings_are_sorted_worst_first_and_deterministically()`
  - Two runs over the same rules produce the same list, so runs can be diffed.
- `test_finding_renders_one_line_with_its_source()`
  - The single-line form a log or console wants.
- `test_finding_without_a_source_file_omits_the_parenthetical()`
  - Registry-wide findings belong to no file.
- `test_findings_table_keeps_every_column_even_when_empty()`
  - A caller filtering on a column must not have to special-case no findings.
- `test_print_findings_hides_the_source_file_until_asked(capsys)`
  - One file is the normal case, and its name in every row is noise.
- `test_print_findings_says_so_when_there_is_nothing_to_report(capsys)`
  - Silence would read as "did not run".
- `test_worst_severity_picks_the_most_severe()`
  - What a CI step gates on.
- `test_registry_wrapper_supplies_the_default_states(fresh_registry)`
  - ``reg.lint_rules`` knows the defaults; the module-level one is told them.
- `test_registry_wrapper_passes_the_frame_through(fresh_registry)`
  - The data lints are reachable from the registry-aware entry point too.
- `test_module_and_registry_entry_points_agree(fresh_registry)`
  - The wrapper adds the defaults and nothing else.
- `test_an_earlier_match_all_is_not_shadowed_by_a_narrower_later_rule()`
  - A match-all rule still applies to every row the narrower one misses.
- `test_a_set_rule_setting_a_parameter_to_its_default_changes_nothing()`
  - The parameter equivalent of a redundant enable or disable.
- `test_a_set_rule_changing_at_least_one_parameter_is_not_redundant()`
- `test_a_declared_parameter_no_rule_sets_is_reported()`
  - Worth knowing before adding another one nothing uses.
- `test_a_parameter_some_rule_sets_is_not_reported_as_unset()`
- `test_a_set_rule_is_never_reported_as_a_redundant_action()`
  - A set rule carries no codes, so the enable/disable lint must skip it.
- `test_the_redundant_message_names_the_action_it_found()`
  - "enables X, which is already on" -- both halves have to match the rule.
- `test_the_redundant_message_agrees_in_number()`
  - Two codes read "are already", one reads "is already".
- `test_an_enable_rule_that_turns_something_on_is_not_redundant()`
  - The complement of the redundant lint: it must stay quiet when it should.
- `test_the_hidden_wildcard_message_names_the_column_and_pattern()`
- `test_the_literal_dot_message_shows_the_mistake_and_the_fix()`
- `test_the_unanchored_message_shows_the_anchored_form()`
- `test_the_expiry_message_reads_the_same_with_and_without_a_ticket()`
  - The ticket is parenthetical: its absence must not leave a stray bracket.
- `test_the_data_messages_count_the_rows_they_looked_at()`
- `test_the_unknown_column_message_names_the_column()`
- `test_the_dead_code_message_names_the_code()`
- `test_the_shadowed_message_names_the_codes_and_the_later_rule()`
- `test_the_unset_param_message_quotes_the_default()`
- `test_the_redundant_param_message_names_the_parameters()`
- `test_the_conflict_message_lists_the_rules_and_names_the_winner()`
- `test_findings_table_carries_every_field_of_every_finding()`
  - The table is what a person reads, so no column may quietly go blank.
- `only(findings, check)`
  - The single finding for *check*, so an assertion cannot pass on the wrong one.
- `test_expiry_finding_names_its_rule_and_file()`
- `test_pattern_findings_name_their_rule_and_file()`
  - Both pattern lints, from one rule with one criterion each.
- `test_redundant_action_finding_names_its_rule_and_file()`
- `test_redundant_param_finding_names_its_rule_and_file()`
- `test_shadowing_finding_names_the_shadowed_rule_and_its_file()`
  - The finding is about the rule that can never fire, not the one that wins.
- `test_conflict_finding_names_the_winning_rule_and_its_file()`
  - Here the finding is about the winner, which is the rule a reader must find.
- `test_data_findings_name_their_rule_and_file()`
  - All three data lints, each from its own rule and file.
- `test_findings_about_no_particular_rule_say_so_rather_than_naming_one()`
  - A dead code and an unset parameter belong to the set of rules, not to one.
- `test_a_wildcard_criterion_does_not_hide_a_later_bad_one()`
  - The wildcard finding skips the rest of *that* criterion, not the loop.
- `test_a_rule_with_the_same_action_does_not_hide_a_later_shadowing_one()`
  - Shadowing needs the opposite action, so a same-action rule is skipped.
- `test_an_undisputed_code_does_not_hide_a_conflict_on_a_later_one()`
  - Codes are walked in sorted order, so an early quiet one must not stop it.
- `test_the_conflict_winner_is_the_last_rule_not_the_second()`
  - Precedence is positional, so with three rules the third one wins.
- `test_a_pattern_with_metacharacters_is_not_reported_as_literal()`
  - A dot inside a real regex is deliberate; only a literal-looking one is not.
- `test_a_literal_pattern_with_a_dot_is_not_also_called_unanchored()`
  - One finding per problem: the dot is the thing to fix first.
- `test_the_dot_example_replaces_only_the_first_dot()`
  - The message shows what else the pattern matches, one substitution at a time.
- `test_worst_severity_orders_by_severity_not_alphabetically()`
  - 'info' sorts before 'warning' as a string, and is the milder of the two.
- `test_print_findings_wraps_long_messages_at_sixty_columns(capsys)`
  - Wrapping is what keeps a wide message from pushing the table off-screen.

## `test_load.cpython-312-pytest-9.1.1.pyc` (source was 6,998 bytes)

> Load: behaviour at volume, with asserted ceilings rather than observations.
> 
> The ceilings are set a few times above what the suite actually takes, not ten
> times: a ceiling far enough above reality to never fire is a test that passes
> whatever happens. They were last tightened when the example date check stopped
> calling ``pd.to_datetime`` per row and the same work got four times faster.
> 
> Thresholds are deliberately loose -- they catch an order-of-magnitude
> regression (an accidental per-row topological sort, a per-row file read), not
> small variation between machines.

- `frame(rows)`
- `test_twenty_thousand_rows_validate_within_the_time_ceiling(example_suites)`
- `test_results_are_correct_at_volume_not_just_fast(example_suites)`
- `test_building_a_report_over_many_rows_stays_within_the_time_ceiling(example_suites)`
  - Collecting outcomes keeps an object per test per row, so it is the report
- `test_memory_stays_bounded_across_many_rows(example_suites)`
  - Validation holds no per-row state, so peak memory must not scale with rows.
- `test_topological_order_is_not_recomputed_per_row(fresh_registry)`
  - `counting()`
- `test_many_registered_tests_still_validate_quickly(fresh_registry)`
- `test_many_rules_resolve_within_the_ceiling(fresh_registry)`
- `test_repeated_validation_does_not_leak_registry_state(example_suites)`
- `test_report_memory_stays_bounded_for_a_large_frame(example_suites)`
  - validate keeps an object per test per row, so this is the number that
- `test_rendering_a_large_report_stays_within_the_time_ceiling(example_suites)`
- `test_summarising_a_large_frame_stays_within_the_time_ceiling(example_suites)`

## `test_overrides_unit.cpython-312-pytest-9.1.1.pyc` (source was 26,982 bytes)

> Unit tests: rule parsing, every load-time rejection, matching, precedence.

- `write(tmp_path, name, text)`
- `one_code(fresh_registry)`
- `test_rule_fields_are_parsed(one_code, tmp_path)`
- `test_match_all_sets_the_flag_and_leaves_criteria_empty(one_code, tmp_path)`
- `test_source_file_records_the_file_the_rule_came_from(one_code, tmp_path)`
- `test_missing_description_defaults_to_empty(one_code, tmp_path)`
- `test_an_unknown_key_is_rejected_rather_than_silently_ignored(one_code, tmp_path)`
  - A misspelled key in a hand-edited file is a setting that does nothing.
- `test_every_documented_key_is_accepted(one_code, tmp_path)`
- `test_empty_file_contributes_no_rules(one_code, tmp_path)`
- `test_missing_file_is_refused_like_any_other_bad_rule_file(one_code, tmp_path)`
  - A ValueError, not the raw OSError: one error policy for loading.
- `test_malformed_rule_is_rejected_at_load_time(one_code, tmp_path, body, expected)`
- `test_duplicate_rule_name_within_one_file_is_rejected(one_code, tmp_path)`
- `test_duplicate_rule_name_across_files_names_both_files(one_code, tmp_path)`
- `test_load_overrides_from_dir_loads_alphabetically(one_code, tmp_path)`
- `test_load_overrides_from_dir_honours_the_pattern(one_code, tmp_path)`
- `test_load_overrides_from_dir_of_an_empty_directory_returns_nothing(one_code, tmp_path)`
- `test_load_overrides_from_files_keeps_the_given_order_not_alphabetical(one_code, tmp_path)`
- `test_load_overrides_from_files_spans_directories(one_code, tmp_path)`
- `test_list_rule_codes_returns_the_exact_codes(one_code, tmp_path)`
- `test_list_rule_codes_prints_the_rule(one_code, tmp_path, capsys)`
- `test_list_rule_codes_unknown_name_lists_what_is_loaded(one_code, tmp_path)`
- `test_list_rule_codes_with_no_rules_loaded_says_so(one_code)`
- `rule(name, action, codes, criteria)`
  - Build a rule directly, bypassing YAML, to isolate matching behaviour.
- `test_default_state_is_used_when_no_rule_matches(fresh_registry)`
- `test_enable_rule_turns_on_an_off_by_default_code(fresh_registry)`
- `test_all_criteria_must_match(fresh_registry)`
- `test_pattern_is_a_search_not_a_full_match(fresh_registry)`
- `test_absent_column_does_not_match(fresh_registry)`
- `test_null_value_does_not_match(fresh_registry)`
- `test_non_string_values_are_matched_as_text(fresh_registry)`
- `test_last_matching_rule_wins(fresh_registry)`
- `test_a_non_matching_later_rule_does_not_override(fresh_registry)`
- `test_one_rule_switches_several_codes(fresh_registry)`
- `test_codes_that_are_not_registered_are_ignored_by_resolution(fresh_registry)`
- `test_expires_is_parsed_from_an_unquoted_yaml_date(one_code, tmp_path)`
  - YAML turns an unquoted 2026-12-31 into a date before the parser sees it.
- `test_expires_is_parsed_from_a_quoted_string(one_code, tmp_path)`
  - A person editing by hand should not have to know which form YAML produced.
- `test_expires_narrows_a_datetime_to_its_date(one_code, tmp_path)`
  - Expiry is a day, not an instant.
- `test_expires_defaults_to_none(one_code, tmp_path)`
  - The key is optional: most rules are not meant to lapse.
- `test_an_unparseable_expires_is_rejected(one_code, tmp_path, value)`
  - A date nobody can read is a date nobody can act on.
- `test_an_impossible_date_is_rejected_by_the_yaml_reader(one_code, tmp_path)`
  - A month of 13 never reaches our parser: PyYAML builds the date itself.
- `test_loading_never_reads_the_clock(one_code, tmp_path)`
  - A rule long past its expiry still loads and still applies.
- `test_ticket_is_carried_through(one_code, tmp_path)`
  - Free text saying why the rule exists, for whoever finds it later.
- `test_ticket_defaults_to_empty(one_code, tmp_path)`
- `test_a_non_string_ticket_is_rejected(one_code, tmp_path)`
  - A bare 4417 would render as a number and stop matching the tracker.
- `test_column_wise_matching_agrees_with_row_wise(one_code, column, pattern)`
  - The vectorised matcher must be the same function, not merely similar.
- `test_applicable_rules_keeps_load_order(one_code)`
  - Precedence is positional, so the per-row list must not be reordered.
- `test_applicable_rules_without_rules_is_one_empty_list_per_row(one_code)`
  - The common case allocates nothing but the empty lists.
- `test_loading_a_list_of_files_knows_which_parameters_are_declared(one_code, tmp_path)`
- `test_loading_a_directory_knows_which_parameters_are_declared(one_code, tmp_path)`
- `test_a_registry_passes_the_file_pattern_to_its_directory_loader(one_code, tmp_path)`
  - The pattern is the whole point of the argument, so a dropped one shows.
- `test_list_rule_codes_separates_several_codes_with_commas(one_code, tmp_path, capsys)`
  - One code never shows a separator, which is where the last one hid.
- `test_an_unknown_rule_name_separates_the_loaded_names_with_commas(one_code, tmp_path)`
- `test_a_rule_mask_requires_every_criterion_to_match(one_code)`
  - AND, not OR: the whole rule applies to a row or none of it does.
- `test_a_match_all_rule_masks_every_row_as_a_boolean(one_code)`
  - The mask is asked for `.sum()` and indexed row by row, so its dtype matters.
- `test_loading_rules_logs_what_it_loaded_at_debug(one_code, tmp_path, caplog)`
  - The counts are the whole content of the line, so the placeholders matter.

## `test_packaging.cpython-312-pytest-9.1.1.pyc` (source was 12,015 bytes)

> What an adopter actually gets: the library alone, with nothing of ours in it.
> 
> These are the checks that would have caught the two findings the fourth review
> turned up -- the example suites travelling inside the distribution, and the
> library being unusable from outside this repository. They install nothing: the
> package is imported from ``src/`` the way an installed copy would be, in a
> subprocess whose working directory is not this project.

- `run_isolated(code, cwd, extra_path)`
  - Run code with only the library (and anything named) importable.
- `test_the_package_ships_no_tests_of_its_own()`
  - Regression: test_row_shape.py, hard_tests/ and soft_tests/ lived in the
- `test_the_example_suites_live_outside_the_package()`
- `test_the_annotations_are_advertised()`
  - Without the marker, mypy treats an installed copy as untyped.
- `test_every_shipped_module_is_importable_on_its_own(tmp_path)`
- `test_importing_the_library_registers_nothing(tmp_path)`
- `adopter_package(tmp_path)`
  - A minimal package of someone else's tests, in their own directory.
- `test_an_adopter_gets_only_their_own_tests(tmp_path)`
  - Regression: a consumer's registry picked up ROW_ALL_NULL, our example.
- `test_an_adopter_can_produce_a_report(tmp_path)`
  - The whole journey from outside: load, validate, render, write.
- `test_a_misspelled_package_says_so_rather_than_raising_an_import_error(tmp_path)`
  - Regression: resolving the suite first meant a typo in package= surfaced as
- `test_a_null_field_is_not_truthy_for_an_adopter(tmp_path)`
  - The pandas trap the docs warn about: a missing value arrives as NaN, which
- `declared_floor()`
  - The Python version pyproject.toml promises to run on, as a tuple.
- `too_new_uses(tree, floor)`
  - Every use of a stdlib name newer than *floor*, by import or attribute.
  - `newer(version)`
- `test_nothing_uses_a_stdlib_newer_than_the_declared_floor()`
  - Regression: two tests imported tomllib, which is 3.11, while pyproject,
- `test_the_declared_floor_is_one_the_suite_has_run_on()`
  - A floor below the versions anything has executed is a promise, not a fact.
- `test_the_floor_guard_catches_a_real_violation()`
  - A guard nobody has seen fail is a guard nobody knows works.
- `test_the_floor_guard_allows_what_the_floor_covers()`
  - The other half: a name the declared floor is new enough for is not a

## `test_parallel_integration.cpython-312-pytest-9.1.1.pyc` (source was 6,673 bytes)

> Validating a frame across worker processes produces exactly what one process does.

- `frame(rows)`
  - Enough rows to be split several ways, cycling through every failure kind.
- `comparable(records)`
  - Everything about a record that must survive crossing a process boundary.
- `test_workers_produce_the_same_records_in_the_same_order(example_suites)`
  - The whole claim: parallel is the same answer, not a similar one.
- `test_comments_survive_being_pickled(example_suites)`
  - They are a mappingproxy, which does not pickle without help.
- `test_override_rules_reach_the_workers(example_suites)`
  - Rules are pickled and applied per worker, so a suppression must hold.
- `test_parameters_reach_the_workers(example_suites)`
  - A worker declares the parameters before loading, or templated messages fail.
- `test_streaming_across_workers_gives_the_same_report(example_suites)`
  - The composed path against real workers: same table, same summary, same causes.
- `test_the_merged_builder_reports_the_whole_runs_numbers(example_suites)`
  - Counts a sequential run's, and a span covering starting the workers --
- `test_a_frame_too_small_to_split_still_reports_its_numbers(example_suites)`
  - The path that never starts a worker returns the same shape of numbers.

## `test_parallel_unit.cpython-312-pytest-9.1.1.pyc` (source was 32,611 bytes)

> Unit tests: splitting a frame, worker counts, and the parallel refusals.
> 
> The end-to-end process run lives in the long suite, since starting workers is
> slow and the fast suite gates every commit.

- `test_a_frame_splits_into_contiguous_ordered_chunks()`
  - Contiguity is what lets results be concatenated without sorting.
- `test_more_chunks_than_rows_gives_one_chunk_per_row()`
- `test_an_empty_frame_splits_into_nothing()`
- `test_asking_for_no_chunks_is_refused()`
- `test_worker_count_defaults_to_the_machines_cores()`
- `test_asking_for_no_workers_is_refused()`
- `test_fail_fast_cannot_be_combined_with_parallel(example_suites)`
  - Which exception surfaced first would depend on scheduling, not the data.
- `test_a_registry_holding_ad_hoc_checks_is_refused(fresh_registry)`
  - A worker rebuilds from suite names, so a check outside a suite would vanish.
- `test_a_suite_loaded_registry_is_reconstructible(example_suites)`
- `test_a_frame_too_small_to_split_runs_here(example_suites)`
  - One chunk means no workers: starting them would cost more than the rows.
- `worker_reset()`
  - Undo the once-per-process flag the worker setup sets.
- `test_a_worker_rebuilds_the_registry_and_only_does_it_once(fresh_registry, worker_reset)`
  - Rebuilding per chunk would cost more than a chunk does.
- `test_a_worker_validates_its_chunk(fresh_registry, worker_reset)`
  - The function a worker actually runs, called here rather than over there.
- `test_a_record_survives_a_pickle_round_trip(fresh_registry)`
  - Records cross a process boundary, and comments are a mappingproxy.
- `test_a_pool_is_started_and_its_results_are_concatenated_in_order(example_suites, monkeypatch)`
  - The pool path itself, with the executor stubbed out.
  - `FakePool()`
    - test_a_pool_is_started_and_its_results_are_concatenated_in_order.<locals>.FakePool
    - `__init__(self, max_workers)`
    - `__enter__(self)`
    - `__exit__(self)`
    - `map(self, fn, chunks)`
- `test_workers_are_handed_every_argument_they_need(example_suites, monkeypatch)`
  - A worker rebuilds from these, so a dropped one means different checks.
  - `FakePool()`
    - test_workers_are_handed_every_argument_they_need.<locals>.FakePool
    - `__init__(self, max_workers)`
    - `__enter__(self)`
    - `__exit__(self)`
    - `map(self, fn, chunks, packages, suites, params, overrides, on_error)`
- `test_the_default_is_to_record_a_raising_check_not_to_raise(example_suites)`
  - The sequential fallback path, with its default arguments.
- `test_a_check_naming_a_loaded_suite_it_does_not_live_in_is_refused(example_suites)`
  - Naming a suite is not the same as being in the package a worker imports.
  - `check(row)`
- `test_a_suite_loaded_but_not_requested_is_refused(example_suites)`
  - Both suites are registered here; a worker told one of them checks less.
- `test_codes_a_worker_would_not_have_is_empty_when_they_match(example_suites)`
  - The everyday case: the suites loaded are the suites passed.
- `fake_pool_returning(records_per_row)`
  - A pool that hands back the given records for every row of every chunk.
  - `FakePool()`
    - fake_pool_returning.<locals>.FakePool
    - `__init__(self, max_workers)`
    - `__enter__(self)`
    - `__exit__(self)`
    - `map(self, fn, chunks)`
- `test_the_run_carries_the_rules_it_was_given(example_suites, monkeypatch)`
- `test_the_run_counts_failures_and_errors_separately(example_suites, monkeypatch)`
  - One of each per row, so a flipped comparison cannot look right.
- `test_the_sequential_fallback_still_applies_the_rules(example_suites)`
  - One chunk runs here rather than in a worker, and must not lose arguments.
- `test_a_worker_chunk_applies_the_rules_and_the_error_policy(example_suites, worker_reset)`
  - The function a worker actually runs, exercised in this process.
- `test_worker_count_falls_back_where_affinity_is_unavailable(monkeypatch)`
  - Not every platform has sched_getaffinity; the fallback is cpu_count.
- `test_a_reconstructible_registry_is_reported_as_one(example_suites)`
  - The positive answer, which the refusal tests cannot give.
- `test_the_refusal_lists_every_missing_code_separated_by_commas(example_suites)`
  - `first(row)`
  - `second(row)`
- `test_report_parallel_checks_its_columns_before_starting_workers(example_suites)`
  - A bad column name fails here, not in four processes at once.
- `test_report_parallel_refuses_fail_fast_like_its_sibling(example_suites)`
- `test_report_parallel_refuses_a_registry_a_worker_could_not_rebuild(example_suites)`
  - `check(row)`
- `test_report_parallel_streams_a_single_chunk_here(example_suites)`
  - One chunk means no workers, and the answer must still be the report.
- `test_report_parallel_merges_what_the_workers_built(example_suites, monkeypatch)`
  - The pool path, stubbed: each chunk's builder is folded into one report.
  - `build_for(chunk)`
  - `FakePool()`
    - test_report_parallel_merges_what_the_workers_built.<locals>.FakePool
    - `__init__(self, max_workers)`
    - `__enter__(self)`
    - `__exit__(self)`
    - `map(self, fn, chunks)`
- `test_a_worker_streams_its_chunk_into_a_builder(example_suites, worker_reset)`
  - The function a worker runs for a report, exercised in this process.
- `test_a_worker_builds_its_report_with_the_spec_it_was_given(example_suites, worker_reset)`
  - The report arguments travel to the worker or the chunk comes back keyed
- `test_a_worker_chunk_report_applies_the_rules_and_the_error_policy(example_suites, worker_reset)`
  - The streaming sibling of the same check: a dropped rule list or error
- `test_report_parallel_hands_its_workers_every_argument(example_suites, monkeypatch)`
  - The same columns validate_parallel is checked for, plus the report spec:
  - `FakePool()`
    - test_report_parallel_hands_its_workers_every_argument.<locals>.FakePool
    - `__init__(self, max_workers)`
    - `__enter__(self)`
    - `__exit__(self)`
    - `map(self, fn, chunks, packages, suites, params, overrides, on_error, spec)`
- `test_the_pool_path_times_the_whole_call_too(example_suites, monkeypatch)`
  - Not only the single-chunk path: the merged builder's span covers starting
  - `FakePool()`
    - test_the_pool_path_times_the_whole_call_too.<locals>.FakePool
    - `__init__(self, max_workers)`
    - `__enter__(self)`
    - `__exit__(self)`
    - `map(self, fn, chunks)`
- `test_report_parallel_says_why_it_refuses_fail_fast(example_suites)`
  - The whole sentence: it is what tells someone which run to make instead.
- `test_report_parallel_says_why_it_refuses_an_unrebuildable_registry(example_suites)`
  - Names the codes and what to do, rather than only that something is wrong.
  - `check(row)`
  - `check_too(row)`
- `test_the_single_chunk_report_path_never_reaches_the_workers(example_suites, monkeypatch)`
  - One chunk is validated here, so neither the pool nor the check that a
  - `refuse()`
  - `check(row)`
- `test_the_single_chunk_report_path_applies_the_rules_and_the_spec(example_suites)`
  - It runs the loop itself rather than handing it to _report_chunk, so it
- `test_the_merged_builder_is_timed_from_the_start_of_the_call(example_suites)`
  - A span, not a clock reading: the wall clock of this call, which is what
- `test_worker_count_prefers_the_affinity_mask_over_the_cpu_count(monkeypatch)`
  - A process pinned to two of eight cores gets two workers, not eight: the
- `test_a_worker_chunk_is_handed_the_error_policy(example_suites, worker_reset, monkeypatch)`
  - The policy is the worker's to apply, so it has to arrive there. Asserted
  - `fake_validate(df)`
- `test_a_worker_report_chunk_is_handed_the_error_policy(example_suites, worker_reset, monkeypatch)`
  - The streaming sibling of the same check.
  - `fake_iter_traces(df)`
- `test_an_unknown_error_policy_is_refused_on_the_single_chunk_path(example_suites, call)`
  - The path that runs the loop here rather than in a worker must pass the

## `test_params_unit.cpython-312-pytest-9.1.1.pyc` (source was 11,097 bytes)

> Unit tests: declaring parameters, setting them from rules, reading them in checks.

- `write(tmp_path, text)`
- `age_max(fresh_registry)`
  - A declared parameter and a check that reads it.
  - `too_high(row, ctx)`
- `test_declared_parameters_and_defaults_are_readable(fresh_registry)`
- `test_declaring_the_same_default_twice_is_allowed(fresh_registry)`
  - A module declaring what it uses may be imported more than once.
- `test_redeclaring_with_a_different_default_is_refused(fresh_registry)`
  - Two callers disagreeing about a default is not a question this can answer.
- `test_a_name_that_is_not_upper_case_is_refused(fresh_registry, name)`
  - Casing is what tells a parameter apart from a column in a rule file.
- `test_a_default_a_rule_file_could_never_carry_is_refused(fresh_registry, value)`
  - YAML gives numbers, strings and bools; anything else could never be set.
- `test_register_params_wants_a_mapping(fresh_registry)`
- `test_a_check_reads_the_declared_default(age_max)`
- `test_every_check_gets_the_parameters_even_without_a_context(age_max)`
  - The engine builds a context when the caller passed none.
  - `peek(row, ctx)`
- `test_a_parameter_that_was_never_declared_raises_naming_what_is(age_max)`
  - A silent None would make a typo look like a threshold of nothing.
- `test_parameters_are_read_only(age_max)`
  - A check must not be able to change what the next row sees.
- `test_a_set_rule_changes_the_value_for_matching_rows(age_max, tmp_path)`
- `test_the_message_quotes_the_limit_the_row_was_judged_against(age_max, tmp_path)`
  - A message naming 130 next to a row judged at 150 is worse than no message.
- `test_the_last_matching_set_rule_wins(age_max, tmp_path)`
  - The same positional precedence that decides enabling and disabling.
- `test_a_parameter_records_where_its_value_came_from(age_max, tmp_path)`
  - What makes a surprising threshold traceable to the file that set it.
- `test_source_of_an_unknown_parameter_raises(age_max)`
- `test_a_set_rule_naming_an_undeclared_parameter_is_refused(age_max, tmp_path)`
  - Without this a typo would sit in the file quietly doing nothing.
- `test_a_value_of_the_wrong_type_is_refused(age_max, tmp_path)`
  - A limit given as a string would compare against a number unpredictably.
- `test_a_bool_where_a_number_belongs_is_refused(age_max, tmp_path)`
  - bool is a subclass of int, so this needs its own check to be caught.
- `test_a_set_rule_without_params_is_refused(age_max, tmp_path)`
- `test_a_set_rule_carrying_codes_is_refused(age_max, tmp_path)`
  - Parameters are global, so setting one is not scoped to particular checks.
- `test_params_on_an_enable_rule_are_refused(age_max, tmp_path)`
- `test_a_message_placeholder_nothing_declared_fails_at_load(fresh_registry)`
  - Caught when the registry is validated, not on the first row that fails.
  - `check(row)`
- `test_a_message_without_placeholders_is_left_alone(fresh_registry)`
  - Nothing pays for templating unless it uses it.
  - `check(row)`
- `test_params_behave_as_a_mapping(age_max)`
  - It is handed to str.format, which needs the whole Mapping protocol.
- `test_no_declared_parameters_means_the_shared_empty_one(fresh_registry)`
  - A registry that declares none allocates nothing per row.
- `test_an_unclosed_brace_in_a_message_is_reported_as_a_bad_template(fresh_registry)`
  - A stray brace would otherwise surface as a formatting error mid-run.

## `test_pathological.cpython-312-pytest-9.1.1.pyc` (source was 12,718 bytes)

> Pathological input: malformed, hostile, empty, boundary. Cheap cases only.

- `write(tmp_path, name, text)`
- `one_code(fresh_registry)`
- `test_invalid_yaml_raises_a_yaml_error(one_code, tmp_path)`
- `test_yaml_that_is_only_a_comment_yields_no_rules(one_code, tmp_path)`
- `test_yaml_null_document_yields_no_rules(one_code, tmp_path)`
- `test_a_list_of_nulls_is_rejected_as_a_non_mapping_rule(one_code, tmp_path)`
- `test_utf8_content_survives_the_round_trip(one_code, tmp_path)`
- `test_a_pattern_matching_a_unicode_value(fresh_registry, tmp_path)`
- `test_a_thousand_rules_load_and_the_last_wins(fresh_registry, tmp_path)`
- `test_empty_row_reports_the_presence_tests_and_nothing_below_them(example_suites)`
- `test_row_with_unexpected_columns_only_reports_what_is_missing(example_suites)`
- `test_duplicate_column_labels_are_rejected_not_silently_passed(fresh_registry)`
  - A duplicate label hands the check a Series, which every value helper turns
- `test_duplicate_labels_are_rejected_before_any_check_runs(fresh_registry)`
- `test_a_very_long_string_value_is_matched_not_truncated(fresh_registry)`
- `test_a_test_that_raises_is_recorded_as_an_error_not_a_pass(fresh_registry)`
  - A broken test must never be mistaken for a happy one.
  - `check(row)`
- `test_a_raising_test_can_be_made_fatal(fresh_registry)`
  - `check(row)`
- `test_a_test_reading_a_column_that_is_absent_errors_naming_it(fresh_registry)`
  - Tests read the row themselves, so a typo surfaces as a KeyError outcome.
  - `check(row)`
- `test_a_test_returning_nothing_raises_even_when_errors_are_recorded(fresh_registry)`
  - A bad return is an authoring bug, not a data problem, so it is never recorded.
  - `check(row)`
- `test_a_deep_dependency_chain_evaluates_in_order(fresh_registry)`
- `test_a_deep_chain_skips_everything_below_a_failure(fresh_registry)`
- `test_wide_row_with_many_columns(fresh_registry)`
- `test_table_rendering_of_a_cell_containing_a_pipe(fresh_registry)`
  - The renderer does not escape, so a pipe in data is shown literally.
- `test_a_newline_in_a_message_does_not_break_the_table(fresh_registry)`
  - textwrap collapses it, so every rendered line stays the same width.
- `test_a_newline_in_a_comment_value_does_not_break_the_table(fresh_registry)`
- `test_a_very_long_comment_value_overflows_rather_than_being_mangled(fresh_registry)`
  - Wrapping never breaks inside a word, so a long identifier stays greppable
- `test_unicode_survives_both_formats(fresh_registry)`
- `test_a_non_string_comment_value_renders(fresh_registry, value)`
- `test_a_hundred_comment_keys_render_in_sorted_order(fresh_registry)`
- `test_a_key_column_value_containing_the_separator_is_left_as_it_is(fresh_registry)`
  - Composite keys join with '|', so a value containing one is ambiguous; the
- `test_a_frame_with_duplicate_column_labels_fails_on_the_first_row(fresh_registry)`
- `test_an_empty_frame_produces_an_empty_report(fresh_registry)`
- `test_a_missing_rule_file_is_reported_like_every_other_load_failure(one_code, tmp_path)`
  - A mistyped path is the likeliest mistake, and it was the one exception
- `test_a_directory_where_a_rule_file_belongs_says_so(one_code, tmp_path)`
  - The other everyday OSError: a path that exists but is not a file.
- `test_a_rule_file_nested_thousands_deep_is_refused_not_crashed(one_code, tmp_path)`
  - The parser runs out of stack before it runs out of file.

## `test_perf.cpython-312-pytest-9.1.1.pyc` (source was 5,655 bytes)

> Performance gates: the numbers that fail a build when they get much worse.
> 
> This is deliberately not `tests/test_benchmarks.py`, which checks that
> `scripts/benchmark.py` still runs, and not `scripts/benchmark.py` itself, which
> prints numbers to read and asserts nothing. What was missing was a check that
> *fails*: a check calling `pd.to_datetime` on a scalar once per row -- about
> seventeen times the cost of the whole engine -- survived many commits because
> nothing in the suite noticed a run getting slower.
> 
> Two things are gated here, each with a generous threshold:
> 
> - **Time**, by `pytest-benchmark`, comparing against the last saved run on this
>   machine and failing at +50%. Fifty per cent, not ten: a tight timing
>   assertion on a shared machine fails for reasons that have nothing to do with
>   the change, and a suite that cries wolf gets ignored. What is being caught is
>   the order-of-magnitude mistake, which is the kind that actually happens.
> - **Memory**, by `pytest-memray`, as ceilings on the report path. Peak
>   allocation is far less sensitive to a busy machine than wall clock, so those
>   ceilings sit between what was measured and what a regression would cost,
>   rather than the order of magnitude a timing threshold needs.
> 
> The two run as separate pytest invocations, because `--memray` slows the code
> it watches -- the engine scenario went from 55ms to 100ms under it -- which
> would make every timing comparison meaningless.
> 
> Neither runs in `fast` or `long`: these tests carry only the `perf` marker, so
> `-m fast` and `-m long` both exclude them. `./run-tests.sh perf` runs them, and
> it is a release gate, not a pre-commit one. See docs/testing.md.

- `frame()`
  - The synthetic frame every scenario here runs over.
- `test_engine_alone(benchmark, frame, fresh_registry)`
  - The engine's own per-row cost, with checks that compute nothing.
- `test_validate_through_the_example_suite(benchmark, frame, example_suites)`
  - The whole path a caller actually runs, checks included.
- `test_build_report_reshaping(benchmark, frame, example_suites)`
  - Turning a completed run into the failure table, which is pure reshaping.
- `test_validate_peak_memory(frame, example_suites)`
  - Holding every record for 500 rows, which is the un-streamed shape.
- `test_streaming_a_report_stays_flat(example_suites)`
  - Streaming holds memory proportional to failures, not to tests times rows.

## `test_properties.cpython-312-pytest-9.1.1.pyc` (source was 4,558 bytes)

> Property-based tests for the three invariants the whole design rests on.
> 
> `tests/test_fuzz.py` checks these too, but only against the fixed seed it uses;
> Hypothesis explores the input space on its own and shrinks a failure down to the
> smallest case that still reproduces it, which is the piece example-based fuzzing
> cannot do.
> 
> ``hypothesis`` is in the ``dev`` extra, so a normal development install runs
> these. The import guard exists for someone running the suite against a bare
> runtime install, and `tests/test_api_contract.py` asserts the dependency is
> declared, so a silent skip cannot become the permanent state without the suite
> saying so.

- `dependency_graphs(draw)`
  - A registry: each test's code, its prerequisites, and whether it passes.
- `test_a_test_never_runs_unless_every_prerequisite_passed(fresh_registry, graph)`
- `test_root_cause_is_always_the_shallowest_failure(fresh_registry, graph)`
- `test_evaluation_order_is_a_topological_order_of_the_graph(fresh_registry, graph)`

## `test_readme.cpython-312-pytest-9.1.1.pyc` (source was 11,168 bytes)

> The README, executed.
> 
> Every Python block in the README is run against the real library, and where the
> README shows the output, the block's printed output is compared to it byte for
> byte. Nothing is stubbed or patched: the only fixture is the empty registry each
> block starts from, which is what a fresh interpreter would give it.
> 
> The blocks are run in the order the README presents them, each in its own
> registry, so a snippet that would only work after some earlier snippet ran is
> caught rather than hidden.

- `blocks()`
  - Every fenced block in the README, as (language, body).
- `python_blocks()`
  - Each Python block with the output block that follows it, if any.
- `block_id(case)`
- `test_the_readme_has_python_blocks_to_check()`
  - A guard on the guard: if the README stops carrying examples, say so rather
- `is_template(source)`
  - The "writing a test" block is a template, not part of the worked session.
- `session_blocks()`
  - The blocks the README presents as one continuous session.
- `test_the_readme_session_runs_and_prints_exactly_what_it_shows(fresh_registry)`
  - The worked example, start to finish, in one namespace -- which is what a
- `test_a_later_block_only_uses_names_an_earlier_one_defined(fresh_registry)`
  - A reader pastes these in order; a block reaching for something undefined
- `test_the_writing_a_test_block_registers_a_working_test(fresh_registry)`
  - The template block is checked on its own: it produces a test that runs, not
- `test_the_example_code_does_not_collide_with_the_shipped_tests(fresh_registry)`
  - A README example that duplicated a shipped code would fail on import for
- `test_every_document_the_readme_links_to_exists(name)`
- `test_the_readme_shell_commands_name_files_that_exist()`
- `readme_text()`
- `test_the_stated_runtime_dependencies_are_the_real_ones()`
  - The README names pandas and PyYAML; requirements.txt is the contract.
- `test_the_stated_pandas_floor_is_the_one_the_code_needs()`
  - render_report calls DataFrame.map, which arrived in pandas 2.1; a lower floor
- `test_the_package_installs_the_way_the_readme_says()`
  - The README tells people to pip install it; pyproject.toml is what makes that
- `test_the_declared_version_matches_the_package()`
- `test_a_bare_bool_return_works_as_the_readme_says(fresh_registry)`
- `test_the_report_is_one_line_per_failure_as_claimed(fresh_registry)`
- `test_the_scope_limits_the_readme_states_hold(fresh_registry)`
  - "it does not fix, coerce, or drop rows" -- validation leaves the frame alone.
- `test_rule_files_can_only_switch_existing_codes(fresh_registry, tmp_path)`
  - "They cannot define new checks or change what one means".
- `test_rule_files_can_set_a_declared_parameter(fresh_registry, tmp_path)`
  - "and change declared thresholds without touching Python".
- `test_the_suites_the_readme_names_exist(fresh_registry)`

## `test_registry_unit.cpython-312-pytest-9.1.1.pyc` (source was 16,313 bytes)

> Registering checks, loading the files they live in, and ordering them.

- `write(tmp_path, filename, body)`
- `TestRegisterCheck()`
  - TestRegisterCheck
  - `test_registers_one_check_with_its_declaration(self)`
    - `c(row)`
  - `test_returns_the_function_unchanged(self)`
    - `c(row)`
  - `test_records_prerequisites_without_duplicates(self)`
    - `a(row)`
    - `b(row)`
  - `test_rejects_an_empty_code(self)`
  - `test_rejects_a_non_string_code(self)`
  - `test_rejects_an_empty_message(self)`
  - `test_rejects_a_duplicate_code_naming_the_function(self)`
    - `first(row)`
    - `second(row)`
  - `test_rejects_a_non_bool_default_enabled(self)`
  - `test_rejects_a_bare_string_of_prerequisites(self)`
  - `test_rejects_an_empty_prerequisite_code(self)`
- `TestCheckSignatures()`
  - TestCheckSignatures
  - `test_accepts_a_one_argument_check(self)`
    - `c(row)`
  - `test_accepts_a_two_argument_check_and_passes_the_context(self)`
    - `c(row, ctx)`
  - `test_accepts_an_optional_third_argument_and_leaves_it_defaulted(self)`
    - `c(row, ctx, limit)`
  - `test_rejects_a_one_argument_check_with_an_optional_second(self)`
    - `c(row, limit)`
  - `test_rejects_a_zero_argument_check(self)`
  - `test_rejects_a_three_argument_check(self)`
  - `test_rejects_a_required_keyword_only_argument(self)`
    - `c(row)`
- `TestCheckGroup()`
  - TestCheckGroup
  - `test_applies_the_groups_prerequisites_to_every_member(self)`
    - `base(row)`
    - `a(row)`
  - `test_a_members_prerequisites_add_to_the_groups(self)`
    - `base(row)`
    - `other(row)`
    - `a(row)`
  - `test_a_prerequisite_named_twice_appears_once(self)`
    - `base(row)`
    - `a(row)`
  - `test_the_group_supplies_default_enabled(self)`
    - `a(row)`
  - `test_a_member_overrides_the_groups_default_enabled(self)`
    - `a(row)`
  - `test_rejects_a_bare_string_on_the_group(self)`
  - `test_rejects_a_bare_string_on_a_member(self)`
- `TestLoadChecks()`
  - TestLoadChecks
  - `test_loads_one_file_and_registers_its_checks(self, tmp_path)`
  - `test_accepts_a_single_path_as_a_string(self, tmp_path)`
  - `test_loads_several_files_in_the_order_given(self, tmp_path)`
  - `test_a_file_listed_twice_is_loaded_once(self, tmp_path)`
  - `test_a_file_already_loaded_is_skipped(self, tmp_path)`
  - `test_a_prerequisite_may_live_in_another_file_in_the_same_call(self, tmp_path)`
  - `test_names_a_path_that_does_not_exist(self, tmp_path)`
  - `test_names_a_path_that_is_a_directory(self, tmp_path)`
  - `test_nothing_is_loaded_when_one_path_of_several_is_missing(self, tmp_path)`
  - `test_an_error_inside_a_check_file_propagates(self, tmp_path)`
  - `test_a_file_that_failed_to_load_can_be_loaded_again(self, tmp_path)`
- `TestClearRegistry()`
  - TestClearRegistry
  - `test_empties_the_registry_and_the_file_list(self, tmp_path)`
  - `test_the_same_file_can_be_loaded_again_afterwards(self, tmp_path)`
- `TestValidateRegistry()`
  - TestValidateRegistry
  - `test_orders_prerequisites_before_dependents(self)`
    - `b(row)`
    - `a(row)`
  - `test_computes_a_layer_per_check(self)`
    - `a(row)`
    - `b(row)`
    - `c(row)`
  - `test_names_a_prerequisite_that_is_not_registered(self)`
    - `b(row)`
  - `test_reports_a_dependency_cycle_as_a_path(self)`
    - `a(row)`
    - `b(row)`
  - `test_reports_a_check_that_depends_on_itself(self)`
    - `a(row)`
  - `test_an_empty_registry_validates(self)`
- `TestEvaluationOrder()`
  - TestEvaluationOrder
  - `test_computes_the_order_on_first_use(self)`
    - `a(row)`
  - `test_a_later_registration_is_included(self)`
    - `a(row)`
    - `b(row)`
- `TestLoadOverrides()`
  - TestLoadOverrides
  - `test_validates_rule_codes_against_the_registry(self, tmp_path)`
    - `a(row)`
  - `test_rejects_a_code_no_check_declares(self, tmp_path)`
  - `test_precedence_follows_the_order_given(self, tmp_path)`
    - `a(row)`
  - `test_no_paths_is_no_rules(self)`
- `TestRegistryTable()`
  - TestRegistryTable
  - `test_one_row_per_check_in_evaluation_order(self)`
    - `b(row)`
    - `a(row)`
  - `test_an_empty_registry_gives_an_empty_table(self)`
  - `test_print_registry_prints_and_returns_the_table(self, capsys)`
    - `a(row)`
- `TestCheckDataclass()`
  - TestCheckDataclass
  - `test_carries_its_declaration(self)`

## `test_report_unit.cpython-312-pytest-9.1.1.pyc` (source was 14,524 bytes)

> The failure table, the row explanation, and the summaries.

- `TestRenderComments()`
  - TestRenderComments
  - `test_renders_pairs_sorted_by_key(self)`
  - `test_no_comments_render_as_an_empty_string(self)`
- `TestBuildReport()`
  - TestBuildReport
  - `test_one_row_per_failure_with_the_documented_columns(self, simple_checks, frame)`
  - `test_a_failure_carries_its_rendered_status_and_comments(self, simple_checks, frame)`
  - `test_marks_the_root_cause_of_each_row(self, simple_checks, frame)`
  - `test_only_the_shallowest_failure_is_the_root_cause(self)`
    - `shallow(row)`
    - `also(row)`
  - `test_falls_back_to_the_frame_index_without_a_key_column(self, simple_checks, frame)`
  - `test_a_missing_key_renders_as_no_key(self, simple_checks)`
  - `test_a_whole_float_key_loses_its_decimal(self, simple_checks)`
  - `test_rejects_a_key_column_that_is_not_in_the_frame(self, simple_checks, frame)`
  - `test_an_empty_report_still_has_its_columns(self, simple_checks)`
  - `test_include_skipped_adds_blocked_and_disabled_checks(self, simple_checks, frame)`
  - `test_include_skipped_carries_the_blocking_reason_as_the_message(self, simple_checks, frame)`
  - `test_the_blocking_reason_is_not_repeated_in_comments(self, simple_checks, frame)`
  - `test_include_passed_adds_every_remaining_check(self, simple_checks, frame)`
  - `test_data_columns_are_copied_in_after_the_key(self, simple_checks, frame)`
  - `test_a_data_column_renders_a_missing_value_as_empty(self, simple_checks)`
  - `test_a_whole_float_data_column_loses_its_decimal(self, simple_checks)`
  - `test_rejects_a_data_column_that_is_not_in_the_frame(self, simple_checks, frame)`
  - `test_rejects_a_data_column_named_twice(self, simple_checks, frame)`
  - `test_rejects_a_data_column_colliding_with_a_report_column(self, simple_checks)`
  - `test_the_run_method_and_the_function_agree(self, simple_checks, frame)`
- `TestErrorsInTheReport()`
  - TestErrorsInTheReport
  - `test_an_errored_check_reports_its_one_line_summary(self, frame)`
    - `boom(row)`
- `TestPrintReport()`
  - TestPrintReport
  - `test_prints_a_bordered_table(self, simple_checks, frame, capsys)`
  - `test_says_so_when_nothing_failed(self, simple_checks, capsys)`
  - `test_wraps_the_message_column_at_the_given_width(self, capsys)`
    - `long(row)`
- `TestWriteReport()`
  - TestWriteReport
  - `test_writes_csv_with_a_header_and_no_index(self, simple_checks, frame, tmp_path)`
  - `test_replaces_an_existing_file(self, simple_checks, frame, tmp_path)`
- `TestRowExplanation()`
  - TestRowExplanation
  - `test_one_row_per_check_with_the_documented_columns(self, simple_checks)`
  - `test_a_passing_check_has_a_dash_for_detail(self, simple_checks)`
  - `test_a_failure_shows_its_comments(self, simple_checks)`
  - `test_a_failure_without_comments_shows_its_message(self, simple_checks)`
  - `test_a_skip_shows_what_blocked_it(self, simple_checks)`
  - `test_exclude_passed_drops_the_checks_that_passed(self, simple_checks)`
  - `test_exclude_passed_keeps_skipped_and_disabled(self, simple_checks)`
- `TestPrintRowExplanation()`
  - TestPrintRowExplanation
  - `test_prints_the_table_and_the_root_cause(self, simple_checks, capsys)`
  - `test_says_so_when_the_row_passed(self, simple_checks, capsys)`
  - `test_returns_the_table_it_printed(self, simple_checks)`
- `TestSummarise()`
  - TestSummarise
  - `test_counts_every_outcome_per_check(self, simple_checks, frame)`
  - `test_worst_first(self, simple_checks, frame)`
  - `test_counts_disabled_checks(self, frame)`
    - `off(row)`
  - `test_an_empty_run_gives_an_empty_table_with_columns(self)`
  - `test_the_run_method_agrees_with_the_function(self, simple_checks, frame)`
- `TestRootCauseCounts()`
  - TestRootCauseCounts
  - `test_counts_rows_per_root_cause_worst_first(self, simple_checks, frame)`
  - `test_ties_break_alphabetically(self, simple_checks)`
  - `test_a_clean_frame_has_no_root_causes(self, simple_checks)`
- `TestPrintSummary()`
  - TestPrintSummary
  - `test_prints_the_summary_and_the_root_cause_tally(self, simple_checks, frame, capsys)`
  - `test_says_so_when_no_checks_ran(self, capsys)`
  - `test_says_so_when_every_row_passed(self, simple_checks, capsys)`
  - `test_returns_the_per_check_table(self, simple_checks, frame)`

## `test_results_unit.cpython-312-pytest-9.1.1.pyc` (source was 5,172 bytes)

> What a check returns, and what the engine records.

- `TestStatusNames()`
  - TestStatusNames
  - `test_names_every_built_in_status(self)`
  - `test_renders_name_and_value_together(self)`
  - `test_refuses_a_value_that_is_not_a_status(self)`
- `TestCheckResultConstruction()`
  - TestCheckResultConstruction
  - `test_defaults_to_a_pass_with_no_comments(self)`
  - `test_pass_singleton_is_a_pass(self)`
  - `test_a_failure_is_falsy_and_names_its_status(self)`
  - `test_accepts_a_numpy_integer_status(self)`
  - `test_comments_are_copied_and_frozen(self)`
  - `test_rejects_a_bool_code(self)`
  - `test_rejects_a_string_code(self)`
  - `test_rejects_an_unregistered_status_value(self)`
  - `test_rejects_status_error_from_a_check(self)`
  - `test_rejects_comments_that_are_not_a_mapping(self)`
  - `test_rejects_a_non_string_comment_key(self)`
- `TestNormaliseResult()`
  - TestNormaliseResult
  - `test_passes_a_check_result_through_unchanged(self)`
  - `test_reads_true_as_a_pass(self)`
  - `test_reads_false_as_an_invalid_failure(self)`
  - `test_reads_a_numpy_bool_as_a_bool(self)`
  - `test_reads_a_bare_status_value(self)`
  - `test_rejects_none_naming_the_check(self)`
  - `test_rejects_a_string(self)`
- `TestCheckRecord()`
  - TestCheckRecord
  - `test_a_failed_record_is_a_failure(self)`
  - `test_an_errored_record_is_a_failure(self)`
  - `test_a_passed_record_is_not_a_failure(self)`
  - `test_status_label_renders_name_and_value(self)`
  - `test_defaults_are_a_pass_at_layer_zero_with_no_text(self)`
- `TestPandasScalarsAreAccepted()`
  - TestPandasScalarsAreAccepted
  - `test_a_comparison_against_a_pandas_value_normalises(self)`

## `test_rules_unit.cpython-312-pytest-9.1.1.pyc` (source was 7,997 bytes)

> The rule-file format: its parser, and the matching it drives.

- `rule()`
  - A minimal valid rule mapping, with fields replaced as asked.
- `TestParseRule()`
  - TestParseRule
  - `test_builds_a_rule_that_matches_every_row(self)`
  - `test_keeps_the_column_and_pattern_when_both_are_given(self)`
  - `test_enables_is_true_only_for_an_enable_rule(self)`
  - `test_rejects_a_rule_that_is_not_a_mapping(self)`
  - `test_rejects_a_missing_name(self)`
  - `test_rejects_an_empty_name(self)`
  - `test_rejects_an_unknown_key_and_lists_the_allowed_ones(self)`
  - `test_rejects_an_action_that_is_not_enable_or_disable(self)`
  - `test_rejects_missing_codes(self)`
  - `test_rejects_an_empty_codes_list(self)`
  - `test_rejects_a_bare_string_of_codes(self)`
  - `test_rejects_a_code_that_is_not_registered(self)`
  - `test_rejects_a_column_without_a_pattern(self)`
  - `test_rejects_a_pattern_without_a_column(self)`
  - `test_rejects_a_non_string_pattern(self)`
  - `test_names_the_rule_and_the_file_in_every_message(self)`
- `TestParseFile()`
  - TestParseFile
  - `test_reads_a_flat_list(self, tmp_path)`
  - `test_an_empty_file_holds_no_rules(self, tmp_path)`
  - `test_rejects_a_mapping_at_the_top_level(self, tmp_path)`
  - `test_names_a_path_that_cannot_be_read(self, tmp_path)`
- `TestLoadRules()`
  - TestLoadRules
  - `test_keeps_the_order_the_files_were_given(self, tmp_path)`
  - `test_rejects_a_duplicate_name_across_two_files(self, tmp_path)`
  - `test_rejects_a_duplicate_name_within_one_file(self, tmp_path)`
  - `test_no_files_is_no_rules(self)`
- `matcher(column, pattern)`
- `TestRuleMatches()`
  - TestRuleMatches
  - `test_a_rule_without_a_column_matches_every_row(self)`
  - `test_a_glob_matches_the_value_as_text(self)`
  - `test_a_glob_that_does_not_match_returns_false(self)`
  - `test_matching_is_case_sensitive(self)`
  - `test_a_question_mark_matches_one_character(self)`
  - `test_a_number_is_matched_on_how_it_prints(self)`
  - `test_an_absent_column_never_matches(self)`
  - `test_a_null_value_never_matches(self)`
  - `test_a_nan_value_never_matches(self)`

## `test_run_unit.cpython-312-pytest-9.1.1.pyc` (source was 15,482 bytes)

> Unit tests: the run object, its traces, its stats, and the progress callback.

- `two_layers(fresh_registry)`
  - A presence check and a range check that depends on it.
  - `age_present(row)`
  - `age_in_range(row)`
- `test_a_run_holds_one_trace_per_row_in_frame_order(two_layers)`
- `test_the_run_keeps_the_rules_it_was_given(two_layers)`
  - A report is only interpretable next to the rules that shaped it.
- `test_records_are_the_raw_lists(two_layers)`
- `test_failed_rows_are_the_ones_with_a_failure(two_layers)`
- `test_root_causes_line_up_with_the_frame(two_layers)`
  - One entry per row, ``None`` where the row passed, so it can be a column.
- `test_explain_returns_one_rows_trace(two_layers)`
- `test_explain_outside_the_frame_raises_naming_its_size(two_layers, position)`
  - A negative index would otherwise wrap round to the wrong row silently.
- `test_report_and_summary_are_the_functions_under_another_name(two_layers)`
- `test_a_trace_keeps_the_tests_that_did_not_run(two_layers)`
  - A trace, not a failure list: "why did nothing fire?" needs the skips.
- `test_a_passing_row_has_no_root_cause(two_layers)`
- `test_an_errored_record_counts_as_a_failure(fresh_registry)`
- `test_stats_count_failures_and_errors_separately(fresh_registry)`
- `test_throughput_of_an_instant_run_is_infinite_not_a_crash()`
  - Guards the division; a clock too coarse to measure must not raise.
- `test_progress_reports_every_n_rows_and_once_at_the_end(two_layers)`
- `test_progress_always_ends_on_the_total(two_layers)`
  - A display stopping at 9,000 of 9,500 reads as a run that died.
- `test_no_progress_callback_means_no_calls(two_layers)`
  - The default path must not pay for a feature it is not using.
- `test_an_interval_below_one_is_rejected(two_layers)`
  - Zero would divide by zero on the modulo; a negative never fires.
- `test_an_empty_frame_still_reports_completion(two_layers)`
- `test_iter_traces_yields_the_same_traces_validate_collects(two_layers)`
  - The streaming path must be the same computation, not a similar one.
- `test_iter_traces_holds_one_trace_at_a_time(two_layers)`
  - It is a generator, so nothing accumulates unless the caller accumulates.
- `test_iter_traces_reports_progress_the_same_way(two_layers)`
- `test_iter_traces_rejects_an_interval_below_one(two_layers)`
- `test_report_builder_produces_the_same_table_as_validate(two_layers)`
  - Two ways of producing one table are worth nothing if they disagree.
- `test_report_builder_summary_matches_the_eager_one(two_layers)`
  - Counters rather than records, so this is the claim worth pinning.
- `test_report_builder_honours_the_include_flags(two_layers, flags)`
- `test_report_builder_on_an_empty_frame_still_has_its_columns(two_layers)`
- `test_report_builder_rejects_bad_data_columns_up_front(two_layers)`
  - Fail when the builder is made, not after a million rows have been fed in.
- `test_loading_logs_at_debug_and_configures_nothing(caplog, fresh_registry)`
  - A library that calls basicConfig steals a decision from the application.
- `test_nothing_is_logged_above_debug_during_a_normal_run(caplog, two_layers)`
  - Validation itself is silent: it is a library call, not an application.
- `test_from_records_builds_a_run_that_reports_like_a_sequential_one(two_layers)`
  - The join between records collected elsewhere and every reporting view.
- `test_from_records_keeps_the_rules_and_stats_it_is_given(two_layers)`
  - Both are the caller's to supply: it did the run, this only reshapes it.
- `test_from_records_refuses_records_that_do_not_match_the_frame(two_layers)`
  - The mismatch every reporting view is built to make impossible.
- `test_the_run_reports_how_long_it_took(two_layers)`
  - A plausible duration, not a timestamp: seconds elapsed, not since 1970.
- `test_the_run_counts_only_the_records_that_failed(two_layers)`
  - Three rows, one failing test each on two of them, and nothing else.
- `test_a_progress_interval_of_one_reports_every_row(two_layers)`
  - One is the smallest legal interval, and the boundary the check guards.
- `test_the_context_builder_reaches_every_check(fresh_registry)`
  - `validate` builds a context per row and hands it on; nothing pinned that.
  - `check(row, ctx)`
  - `build(row)`

## `test_safety.cpython-312-pytest-9.1.1.pyc` (source was 8,388 bytes)

> Safety: no code execution from data, no path escapes, no secret leakage.

- `write(tmp_path, name, text)`
- `one_code(fresh_registry)`
- `test_yaml_cannot_construct_arbitrary_python_objects(one_code, tmp_path)`
  - safe_load, not load: a !!python/object tag must be refused, not executed.
- `test_a_rule_pattern_is_never_evaluated_as_code(one_code, tmp_path)`
- `test_loading_rules_writes_nothing_to_disk(one_code, tmp_path)`
- `test_validation_never_mutates_the_dataframe_it_reads(example_suites)`
- `test_a_suite_name_cannot_escape_the_package_via_dots(fresh_registry)`
  - A dotted name is not resolved as a path; it fails as an unknown suite,
- `test_a_suite_name_cannot_import_an_unrelated_top_level_module(fresh_registry)`
  - 'os' is resolved against the given package, never as a top-level import,
- `test_load_overrides_from_dir_does_not_recurse_into_subdirectories(one_code, tmp_path)`
- `test_a_catastrophic_regex_is_bounded_by_the_value_length(one_code, tmp_path)`
  - A nested-quantifier pattern on a short value must not hang the run.
- `test_an_ndarray_cell_does_not_break_rule_matching(one_code)`
  - Regression: pd.isna on an ndarray returns an array, and the bool() of that
- `test_a_formula_cell_is_neutralised_in_csv(fresh_registry, message)`
  - A report is meant to be opened in a spreadsheet, and comments carry values
- `test_a_negative_number_keeps_its_minus_sign(fresh_registry)`
- `test_a_formula_inside_a_comment_value_cannot_start_the_cell(fresh_registry)`
  - Comments always render as ``key=value``, so a formula taken from the data
- `test_a_formula_in_the_row_key_is_neutralised(fresh_registry)`
  - `check(row)`
- `test_the_table_view_is_left_alone(fresh_registry)`
  - Text output cannot execute, so the value is shown as the test saw it.
- `test_escaping_can_be_switched_off_for_a_machine_reader(fresh_registry)`
- `test_a_written_report_is_escaped_too(fresh_registry, tmp_path)`
- `test_comments_are_never_evaluated(fresh_registry)`
  - Comments are data all the way through: nothing formats or evals them.
- `test_error_messages_quote_the_offending_value_not_the_whole_file(one_code, tmp_path)`
  - A rule file may sit beside sensitive data; errors must stay local.

## `test_smoke.cpython-312-pytest-9.1.1.pyc` (source was 1,153 bytes)

> Smoke tests: the entry points start and do their main job.

- `test_main_runs_and_exits_zero()`
- `test_main_validates_the_demo_frame()`
- `test_a_clean_row_produces_no_report_line()`
  - Row 1 of the demo frame is clean, so its key never appears in the report.
- `test_main_hard_only_runs_and_exits_zero()`
- `test_help_exits_zero_and_lists_the_flags()`

## `test_tables_unit.cpython-312-pytest-9.1.1.pyc` (source was 2,379 bytes)

> Plain-text table rendering and the null test it shares.

- `TestIsNull()`
  - TestIsNull
  - `test_none_is_null(self)`
  - `test_nan_is_null(self)`
  - `test_pandas_na_is_null(self)`
  - `test_a_value_is_not_null(self)`
  - `test_a_list_is_never_null(self)`
  - `test_an_array_is_never_null(self)`
- `TestFormatTable()`
  - TestFormatTable
  - `test_empty_frame_renders_as_empty(self)`
  - `test_renders_header_divider_and_rows(self)`
  - `test_widths_follow_the_widest_cell(self)`
  - `test_null_cells_render_empty(self)`
  - `test_wraps_a_column_at_the_given_width(self)`
  - `test_wrapping_never_breaks_inside_a_word(self)`
  - `test_an_empty_string_still_produces_one_line(self)`

## `test_validate_row_unit.cpython-312-pytest-9.1.1.pyc` (source was 22,377 bytes)

> Unit tests: the per-row algorithm, its outcomes, and dependency skipping.

- `disable(code, name)`
- `enable(code, name)`
- `codes(outcomes)`
- `statuses(outcomes)`
- `detail(outcomes, code)`
- `test_a_passing_row_produces_no_failures(fresh_registry)`
- `test_a_failure_carries_code_message_status_and_comments(fresh_registry)`
- `test_failures_come_back_in_evaluation_order(fresh_registry)`
- `test_several_failures_are_all_reported(fresh_registry)`
- `test_a_one_argument_test_receives_the_row(fresh_registry)`
  - `check(row)`
- `test_a_two_argument_test_receives_the_context(fresh_registry)`
  - The metadata reaches the check; the object itself is a copy.
  - `check(row, ctx)`
- `test_a_check_always_receives_a_context(fresh_registry)`
  - The engine builds one when the caller passed none.
  - `check(row, ctx)`
- `test_a_signature_the_engine_cannot_call_is_rejected_at_registration(fresh_registry, arguments)`
- `test_a_starargs_test_is_accepted(fresh_registry)`
  - `check()`
- `test_returning_true_passes_and_false_fails_as_invalid(fresh_registry)`
  - `check(row)`
- `test_returning_a_bare_status_fails_with_it(fresh_registry)`
  - `check(row)`
- `test_validate_row_does_not_mutate_the_row_or_the_context(fresh_registry)`
- `test_a_test_off_by_default_does_not_run(fresh_registry)`
- `test_an_override_can_enable_an_off_by_default_test(fresh_registry)`
- `test_an_override_can_disable_an_on_by_default_test(fresh_registry)`
- `test_an_override_applies_only_to_matching_rows(fresh_registry)`
- `test_explain_row_reports_every_registered_test(fresh_registry)`
- `test_a_test_off_by_default_says_so(fresh_registry)`
- `test_a_test_disabled_by_a_rule_names_the_rule(fresh_registry)`
- `test_the_last_matching_rule_is_the_one_named(fresh_registry)`
- `test_validate_row_and_explain_row_agree_on_failures(example_suites)`
- `test_on_error_must_be_one_of_two_values(fresh_registry)`
- `test_a_dependent_runs_when_its_prerequisite_passes(fresh_registry)`
- `test_a_dependent_is_not_run_when_its_prerequisite_fails(fresh_registry)`
- `test_a_dependent_is_not_run_when_its_prerequisite_is_disabled(fresh_registry)`
  - A disabled prerequisite confirmed nothing, so it must not unlock anything.
- `test_a_dependent_is_not_run_when_its_prerequisite_errored(fresh_registry)`
- `test_every_prerequisite_must_pass_and_all_blockers_are_named(fresh_registry)`
- `test_skipping_propagates_transitively(fresh_registry)`
- `test_a_disabled_dependent_is_skipped_even_when_its_prerequisite_passes(fresh_registry)`
- `test_sibling_dependents_are_independent(fresh_registry)`
- `test_registration_order_does_not_have_to_match_dependency_order(fresh_registry)`
- `test_root_cause_is_the_first_failure_in_dependency_order(fresh_registry)`
- `test_root_cause_of_a_clean_row_is_none(fresh_registry)`
- `test_root_cause_ignores_disabled_and_skipped_outcomes(fresh_registry)`
- `test_an_errored_test_can_be_the_root_cause(fresh_registry)`
- `test_layer_is_zero_without_prerequisites(fresh_registry)`
- `test_layer_counts_the_deepest_chain(fresh_registry)`
- `test_outcomes_carry_the_layer_and_suite(fresh_registry)`
- `test_duplicate_labels_raise_before_any_test_runs(fresh_registry)`
- `test_example_tests_report_the_expected_codes(example_suites, row, expected)`
- `test_a_missing_field_reports_once_not_from_every_test_that_reads_it(example_suites)`
  - The whole point of layering: one complaint about a blank age.
- `test_failure_comments_carry_the_numbers_a_reader_needs(example_suites)`
- `test_the_off_by_default_integer_test_once_enabled(example_suites)`
- `test_disabling_a_presence_test_hides_everything_below_it(example_suites)`
- `test_check_rule_columns_is_quiet_when_every_criterion_column_is_present(fresh_registry)`
- `test_check_rule_columns_warns_about_a_column_the_data_lacks(fresh_registry)`
  - A criterion on a missing column never matches, so the rule silently never fires.
- `test_check_rule_columns_ignores_a_match_all_rule(fresh_registry)`
- `test_example_tests_handle_edge_values(example_suites, row, expected)`
- `test_the_integer_test_passes_a_whole_number_once_enabled(example_suites)`
- `test_the_example_date_helper_agrees_with_pandas_on_every_shape(example_suites, value)`
  - The ISO fast path must never change what counts as a date.
  - `through_pandas(raw)`

