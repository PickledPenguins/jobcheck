"""Every message the library raises, pinned word for word.

The error text *is* the interface for anyone who misuses this library, and it is
the part of the surface that rots quietly: a reworded message breaks no check that
matches on a substring, and a message that stops naming the offending value costs
its reader the one fact they needed.

So these compare the whole string, not a fragment. Mutation testing is what made
the gap obvious: rewriting a message wholesale left most of these paths passing,
because nothing asserted more than a keyword.

The rule-file messages are pinned in `tests/test_overrides_unit.py`, which
already compares them exactly, and the CLI's own messages in
`tests/failures/`, which compares stderr byte for byte.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import (
    build_report,
    collect_outcomes,
    explain_row,
    registry as reg,
    render_report,
    validate_row,
)
from jobcheck.results import Status, CheckResult, normalise_result

pytestmark = pytest.mark.fast

FRAME = pd.DataFrame([{"id": 1, "age": 30}])


def message_of(raised: pytest.ExceptionInfo[Exception]) -> str:
    return str(raised.value)


# --- registration -----------------------------------------------------------


def test_an_empty_code_says_what_a_code_must_be(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.register_check(code="", message="m")(lambda row: True)
    assert message_of(raised) == "Check code must be a non-empty string, got ''."


def test_a_missing_message_says_what_the_message_is_for(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.register_check(code="CODE", message="")(lambda row: True)
    assert message_of(raised) == "Check 'CODE': message must be the text a person sees on failure."


def test_a_duplicate_code_names_what_registered_it(fresh_registry: None) -> None:
    make_check("TAKEN")
    with pytest.raises(ValueError) as raised:
        reg.register_check(code="TAKEN", message="m")(lambda row: True)
    assert "Duplicate check code 'TAKEN' (registering " in message_of(raised)
    assert message_of(raised).endswith(
        "Codes are permanent identifiers and must be unique.")


def test_a_string_depends_on_explains_why_it_is_wrong(fresh_registry: None) -> None:
    """Regression: register_check used to do list(depends_on or []) before the guard
    could see it, so a mistyped bare string became its characters and the failure
    arrived later as a missing prerequisite called 'O'."""

    with pytest.raises(ValueError) as raised:
        reg.register_check(code="CODE", message="m", depends_on="OTHER")(  # type: ignore[arg-type]
            lambda row: True)
    assert message_of(raised) == (
        "Check 'CODE': depends_on must be a list of check codes, got 'OTHER'. "
        "A bare string is a list of its characters, which is never what you meant."
    )


def test_a_string_depends_on_in_a_group_says_the_same(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.check_group(depends_on="OTHER")  # type: ignore[arg-type]
    assert message_of(raised) == (
        "check_group depends_on must be a list of check codes, got 'OTHER'. "
        "A bare string is a list of its characters, which is never what you meant."
    )


def test_a_non_boolean_default_enabled_names_the_value(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.register_check(code="CODE", message="m", default_enabled="yes")(  # type: ignore[arg-type]
            lambda row: True)
    assert message_of(raised) == (
        "Check 'CODE': default_enabled must be True or False, got 'yes'.")


def test_a_non_text_description_names_the_value(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.register_check(code="CODE", message="m", description=7)(  # type: ignore[arg-type]
            lambda row: True)
    assert message_of(raised) == "Check 'CODE': description must be text, got 7."


def test_a_non_text_suite_says_what_to_do_instead(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.register_check(code="CODE", message="m", suite=7)(  # type: ignore[arg-type]
            lambda row: True)
    assert message_of(raised) == (
        "Check 'CODE': suite must be the name of a suite, got 7. Leave it out "
        "to take the name of the directory the check lives in."
    )


def test_a_three_argument_test_is_rejected_with_its_signature(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        @reg.register_check(code="CODE", message="m")
        def check(row, ctx, extra):  # type: ignore[no-untyped-def]
            return True
    assert message_of(raised) == (
        "Check 'CODE': check(row, ctx, extra) must take (row) or (row, ctx), "
        "not 3 positional argument(s)."
    )


def test_a_required_keyword_argument_says_how_to_fix_it(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        @reg.register_check(code="CODE", message="m")
        def check(row, *, limit):  # type: ignore[no-untyped-def]
            return True
    assert message_of(raised) == (
        "Check 'CODE': check(row, *, limit) needs keyword argument(s) "
        "limit that the engine cannot supply. Give them defaults, or read them "
        "from the row or the context."
    )


# --- loading ----------------------------------------------------------------


def test_an_unknown_suite_names_the_subpackage_it_expected(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.load_suites(["nope_tests"], package="example_suites")
    assert message_of(raised) == (
        "Unknown suite 'nope_tests': expected a subpackage 'example_suites.nope_tests' "
        "(directory example_suites/nope_tests/ containing an __init__.py). "
        "Pass package= to point this at your own checks."
    )


def test_an_unknown_package_says_what_package_means_here(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.load_suites([], package="no_such_package_anywhere")
    assert message_of(raised) == (
        "Unknown package 'no_such_package_anywhere': it is not importable from here. "
        "package= is the package your own checks live in."
    )


def test_a_module_where_a_package_was_expected_says_which(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg._import_test_modules("json.decoder")
    assert message_of(raised) == (
        "'json.decoder' is a module, not a package; expected a package directory")


def test_a_dangling_prerequisite_lists_the_loaded_suites(fresh_registry: None) -> None:
    make_check("DEPENDENT", depends_on=["ABSENT"])
    with pytest.raises(ValueError) as raised:
        reg.validate_registry()
    assert message_of(raised) == (
        "Check 'DEPENDENT' depends on 'ABSENT', which is not registered. "
        "Either the code is a typo, or it belongs to a suite that was not loaded "
        "(currently loaded: [])."
    )


def test_a_missing_test_file_says_nothing_is_discovered(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.load_checks(["/no/such/file.py"])
    assert message_of(raised) == (
        "No check file at '/no/such/file.py'. load_checks() names files "
        "explicitly; nothing is discovered."
    )


# --- per-row evaluation -----------------------------------------------------


def test_duplicate_column_labels_say_what_a_test_would_receive(fresh_registry: None) -> None:
    make_check("CODE")
    row = pd.Series([1, 2], index=["age", "age"])
    with pytest.raises(ValueError) as raised:
        explain_row(row)
    assert message_of(raised) == (
        "Row has duplicate column labels ['age']: a check reading one of them would "
        "be handed a Series instead of a value. Rename or drop the duplicate columns "
        "before validating."
    )


def test_an_unknown_on_error_names_the_two_that_work(fresh_registry: None) -> None:
    make_check("CODE")
    with pytest.raises(ValueError) as raised:
        validate_row(pd.Series({"age": 1}), on_error="explode")
    assert message_of(raised) == "on_error must be 'record' or 'raise', got 'explode'."


def test_a_test_returning_nonsense_says_what_it_may_return(fresh_registry: None) -> None:
    with pytest.raises(TypeError) as raised:
        normalise_result(object(), "CODE")
    assert message_of(raised).startswith("Check 'CODE' returned ")
    assert message_of(raised).endswith(
        "A check must return PASS, a CheckResult, a bool, or a Status value.")


def test_a_result_with_an_unknown_status_names_the_registered_ones(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        CheckResult(99)
    assert message_of(raised).startswith("Unknown status 99.")


# --- reporting --------------------------------------------------------------


def test_a_key_column_that_is_not_there_lists_the_columns(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    outcomes = collect_outcomes(FRAME)
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=FRAME, key_column="nope")
    assert message_of(raised) == (
        "key_column ['nope'] is not in the data. Available columns: id, age.")


def test_a_key_column_without_a_frame_says_to_pass_one(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(collect_outcomes(FRAME), key_column="id")
    assert message_of(raised) == (
        "key_column needs the frame it names columns in; pass df as well.")


def test_data_columns_without_a_frame_say_to_pass_one(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(collect_outcomes(FRAME), data_columns=["age"])
    assert message_of(raised) == "data_columns names columns in the frame; pass df as well."


def test_data_columns_that_are_not_there_list_the_columns(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(collect_outcomes(FRAME), df=FRAME, data_columns=["nope"])
    assert message_of(raised) == (
        "data_columns ['nope'] is not in the data. Available columns: id, age.")


def test_a_repeated_data_column_names_the_repeat(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(collect_outcomes(FRAME), df=FRAME, data_columns=["age", "age"])
    assert message_of(raised) == "data_columns names ['age'] more than once."


def test_an_ambiguous_data_column_says_to_rename_it(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    frame = pd.DataFrame([[1, 2, 3]], columns=["id", "age", "age"])
    outcomes = collect_outcomes(FRAME)
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=frame, data_columns=["age"])
    assert message_of(raised) == (
        "data_columns ['age'] appears more than once in the frame, so the report "
        "cannot tell which column you meant. Rename or drop the duplicates first."
    )


def test_a_data_column_clashing_with_a_report_column_shows_the_fix(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    frame = pd.DataFrame([{"id": 1, "code": "x"}])
    with pytest.raises(ValueError) as raised:
        build_report(collect_outcomes(frame), df=frame, data_columns=["code"])
    assert message_of(raised) == (
        "data_columns ['code'] would collide with the report's own column(s) of the "
        "same name. Rename the column in the frame first, e.g. "
        "df.rename(columns={'code': 'source_code'})."
    )


def test_a_frame_of_the_wrong_length_says_to_pass_the_same_one(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    outcomes = collect_outcomes(FRAME)
    bigger = pd.DataFrame([{"id": 1}, {"id": 2}])
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=bigger)
    assert message_of(raised) == (
        "outcomes cover 1 row(s) but the frame has 2: "
        "pass the same frame the outcomes were collected from."
    )


def test_an_unknown_format_names_the_two_that_work(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    report = build_report(collect_outcomes(FRAME), df=FRAME)
    with pytest.raises(ValueError) as raised:
        render_report(report, fmt="pdf")
    assert message_of(raised) == "fmt must be 'table' or 'csv', got 'pdf'."


# --- the whole-frame entry point --------------------------------------------


def test_a_progress_interval_below_one_names_the_value(fresh_registry: None) -> None:
    from jobcheck import validate

    make_check("CODE")
    with pytest.raises(ValueError) as raised:
        validate(FRAME, progress_every=0)
    assert message_of(raised) == "progress_every must be at least 1, got 0."


def test_from_records_of_the_wrong_length_says_what_it_needs(fresh_registry: None) -> None:
    from jobcheck import ValidationRun

    make_check("CODE")
    with pytest.raises(ValueError) as raised:
        ValidationRun.from_records(FRAME, [])
    assert message_of(raised) == (
        "0 row(s) of outcomes for a frame of 1 row(s): "
        "from_records() needs one list per row, in frame order."
    )


def test_explaining_a_row_outside_the_frame_names_the_range(fresh_registry: None) -> None:
    from jobcheck import validate

    make_check("CODE")
    run = validate(FRAME)
    with pytest.raises(IndexError) as raised:
        run.explain(5)
    assert str(raised.value) == (
        "No row at position 5: the frame has 1 row(s), so positions run 0..0.")
