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
    validate,
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


def test_a_dangling_prerequisite_lists_the_loaded_files(fresh_registry: None) -> None:
    make_check("DEPENDENT", depends_on=["ABSENT"])
    with pytest.raises(ValueError) as raised:
        reg.validate_registry()
    assert message_of(raised) == (
        "Check 'DEPENDENT' depends on 'ABSENT', which is not registered. "
        "Either the code is a typo, or it lives in a check file that was not loaded "
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
    outcomes = validate(FRAME)
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=FRAME, key_column="nope")
    assert message_of(raised) == (
        "key_column ['nope'] is not in the data. Available columns: id, age.")


def test_a_key_column_without_a_frame_says_to_pass_one(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(validate(FRAME), key_column="id")
    assert message_of(raised) == (
        "key_column needs the frame it names columns in; pass df as well.")


def test_data_columns_without_a_frame_say_to_pass_one(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(validate(FRAME), data_columns=["age"])
    assert message_of(raised) == "data_columns names columns in the frame; pass df as well."


UNUSABLE = (
    "cannot be used. Each name must appear exactly once in the frame, once in "
    "data_columns, and not be one of the report's own columns ['row', 'code', 'status', "
    "'layer', 'outcome', 'message', 'comments', 'is_root_cause']. Frame columns: "
)


def test_data_columns_that_are_not_there_list_the_columns(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(validate(FRAME), df=FRAME, data_columns=["nope"])
    assert message_of(raised) == f"data_columns ['nope'] {UNUSABLE}id, age."


def test_a_repeated_data_column_names_the_repeat(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(validate(FRAME), df=FRAME, data_columns=["age", "age"])
    assert message_of(raised) == f"data_columns ['age'] {UNUSABLE}id, age."


def test_an_ambiguous_data_column_is_refused_with_the_frame_columns(
    fresh_registry: None,
) -> None:
    make_check("CODE", passes=False)
    frame = pd.DataFrame([[1, 2, 3]], columns=["id", "age", "age"])
    outcomes = validate(FRAME)
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=frame, data_columns=["age"])
    assert message_of(raised) == f"data_columns ['age'] {UNUSABLE}id, age, age."


def test_a_data_column_clashing_with_a_report_column_is_refused(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    frame = pd.DataFrame([{"id": 1, "code": "x"}])
    with pytest.raises(ValueError) as raised:
        build_report(validate(frame), df=frame, data_columns=["code"])
    assert message_of(raised) == f"data_columns ['code'] {UNUSABLE}id, code."


def test_a_frame_of_the_wrong_length_says_to_pass_the_same_one(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    outcomes = validate(FRAME)
    bigger = pd.DataFrame([{"id": 1}, {"id": 2}])
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=bigger)
    assert message_of(raised) == (
        "outcomes cover 1 row(s) but the frame has 2: "
        "pass the same frame the outcomes were collected from."
    )


def test_an_unknown_format_names_the_two_that_work(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    report = build_report(validate(FRAME), df=FRAME)
    with pytest.raises(ValueError) as raised:
        render_report(report, fmt="pdf")
    assert message_of(raised) == "fmt must be 'table' or 'csv', got 'pdf'."


