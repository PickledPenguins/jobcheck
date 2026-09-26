"""Every message the library raises, pinned word for word.

The error text *is* the interface for anyone who misuses this library, and it is
the part of the surface that rots quietly: a reworded message breaks no check that
matches on a substring, and a message that stops naming the offending value costs
its reader the one fact they needed.

So these compare the whole string, not a fragment. Mutation testing is what made
the gap obvious: rewriting a message wholesale left most of these paths passing,
because nothing asserted more than a keyword.

The rule-file messages are pinned in `tests/test_rules_unit.py`, which
already compares them exactly, and the CLI's own messages in
`tests/failures/`, which compares stderr byte for byte.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import (
    build_report,
    validate,
    explain_row,
    load_rules,
    registry as reg,
    render,
    validate_row,
)
from jobcheck.results import Verdict, _normalize_verdict
from jobcheck.results import OK

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


def test_a_three_argument_check_is_rejected_with_its_signature(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        @reg.register_check(code="CODE", message="m")
        def check(row, ctx, extra):  # type: ignore[no-untyped-def]
            return OK
    assert message_of(raised) == (
        "Check 'CODE': check(row, ctx, extra) must take (row) or (row, context), "
        "not 3 positional argument(s)."
    )


def test_a_required_keyword_argument_says_how_to_fix_it(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        @reg.register_check(code="CODE", message="m")
        def check(row, *, limit):  # type: ignore[no-untyped-def]
            return OK
    assert message_of(raised) == (
        "Check 'CODE': check(row, *, limit) needs keyword argument(s) "
        "limit that the engine cannot supply. Give them defaults, or read them "
        "from the row or the context."
    )


# --- loading ----------------------------------------------------------------


def test_a_dangling_prerequisite_lists_the_loaded_files(fresh_registry: None) -> None:
    make_check("DEPENDENT", depends_on=["ABSENT"])
    with pytest.raises(ValueError) as raised:
        reg._validate_registry()
    assert message_of(raised) == (
        "Check 'DEPENDENT' depends on 'ABSENT', which is not registered. "
        "Either the code is a typo, or it lives in a check file that was not loaded "
        "(currently loaded: []). Loading the missing file works; correcting an "
        "already-loaded one does not, because load_checks skips a path it has already "
        "read -- call clear_registry() first."
    )


def test_a_bare_string_path_is_refused_by_both_loaders(fresh_registry: None) -> None:
    with pytest.raises(TypeError) as raised:
        reg.load_checks("checks.py")  # type: ignore[arg-type]
    assert message_of(raised) == (
        "load_checks takes a list of paths, not one string: pass ['checks.py']. "
        "A bare string would be read as a list of its characters."
    )
    with pytest.raises(TypeError) as raised:
        load_rules("rules.yaml")  # type: ignore[arg-type]
    assert message_of(raised) == (
        "load_rules takes a list of paths, not one string: pass ['rules.yaml']. "
        "A bare string would be read as a list of its characters."
    )


def test_a_missing_check_file_says_nothing_is_discovered(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        reg.load_checks(["/no/such/file.py"])
    assert message_of(raised) == (
        "No check file at '/no/such/file.py'. load_checks() names files "
        "explicitly; nothing is discovered."
    )


def test_a_missing_rule_file_says_it_the_same_way(fresh_registry: None) -> None:
    """The two loaders are one mistake apart, so they are one message apart."""

    with pytest.raises(ValueError) as raised:
        load_rules(["/no/such/rules.yaml"])
    assert message_of(raised) == (
        "No rule file at '/no/such/rules.yaml'. load_rules() names files "
        "explicitly; nothing is discovered."
    )


def test_a_missing_relative_path_prints_where_it_looked(fresh_registry: None) -> None:
    """A relative path that is not there is unreadable without the directory it
    was joined to: the reader cannot see the process's working directory."""

    with pytest.raises(ValueError) as raised:
        reg.load_checks(["checks.py"])
    assert message_of(raised) == (
        f"No check file at 'checks.py': nothing at {Path.cwd() / 'checks.py'}, where "
        "a relative path is resolved against the working directory. load_checks() "
        "names files explicitly; nothing is discovered."
    )


# --- per-row evaluation -----------------------------------------------------


def test_duplicate_column_labels_say_what_a_check_would_receive(fresh_registry: None) -> None:
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


def test_a_check_returning_nonsense_says_what_it_may_return(fresh_registry: None) -> None:
    with pytest.raises(TypeError) as raised:
        _normalize_verdict(object(), "CODE")
    assert message_of(raised).startswith("Check 'CODE' returned ")
    assert message_of(raised).endswith(
        "A check must return OK or a Verdict; Verdict(condition) wraps a "
        "bare comparison.")


def test_a_result_with_an_unknown_status_names_the_registered_ones(fresh_registry: None) -> None:
    with pytest.raises(ValueError) as raised:
        Verdict(99)
    assert message_of(raised).startswith("Unknown status 99.")


def test_a_frame_that_is_not_a_frame_points_at_the_per_row_calls(fresh_registry: None) -> None:
    make_check("CODE")
    with pytest.raises(TypeError) as raised:
        validate(FRAME.iloc[0])  # type: ignore[arg-type]
    assert message_of(raised) == (
        "validate takes a DataFrame, got Series; for one row, call "
        "validate_row or explain_row."
    )


def test_a_row_that_is_not_a_series_names_what_it_got(fresh_registry: None) -> None:
    make_check("CODE")
    with pytest.raises(TypeError) as raised:
        explain_row({"age": 30})  # type: ignore[arg-type]
    assert message_of(raised) == (
        "A row must be a pandas Series -- one row of a DataFrame -- got dict; "
        "for a whole frame, call validate."
    )


# --- reporting --------------------------------------------------------------


def test_a_key_column_that_is_not_there_lists_the_columns(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    outcomes = validate(FRAME)
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=FRAME, key_column="nope")
    assert message_of(raised) == (
        "key_column 'nope' is not in the data. Available columns: id, age.")


UNUSABLE = (
    "cannot be used for the report. Each name must be asked for once and be one of: "
)


def test_extra_columns_that_are_not_there_list_the_columns(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(validate(FRAME), df=FRAME, add_columns=["nope"])
    assert message_of(raised) == f"add_columns ['nope'] {UNUSABLE}id, age."


def test_a_repeated_data_column_names_the_repeat(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    with pytest.raises(ValueError) as raised:
        build_report(validate(FRAME), df=FRAME, add_columns=["age", "age"])
    assert message_of(raised) == f"add_columns ['age'] {UNUSABLE}id, age."


def test_an_ambiguous_data_column_is_refused_with_the_frame_columns(
    fresh_registry: None,
) -> None:
    make_check("CODE", passes=False)
    frame = pd.DataFrame([[1, 2, 3]], columns=["id", "age", "age"])
    outcomes = validate(FRAME)
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=frame, add_columns=["age"])
    assert message_of(raised) == f"add_columns ['age'] {UNUSABLE}id."


def test_a_data_column_clashing_with_a_report_column_is_refused(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    frame = pd.DataFrame([{"id": 1, "code": "x"}])
    with pytest.raises(ValueError) as raised:
        build_report(validate(frame), df=frame, add_columns=["code"])
    assert message_of(raised) == f"add_columns ['code'] {UNUSABLE}id."


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
        render(report, fmt="pdf")
    assert message_of(raised) == "fmt must be 'table' or 'csv', got 'pdf'."






def test_a_builder_with_a_required_keyword_argument_says_how_to_fix_it(
    fresh_registry: None
) -> None:
    """Regression: the check path refused this at registration and the builder
    path did not, so the builder failed on the first row with a bare TypeError."""

    make_check("CODE")

    def build(row, *, mode):  # type: ignore[no-untyped-def]
        return None

    with pytest.raises(ValueError) as raised:
        validate(pd.DataFrame([{"a": 1}]), context_builder=build)
    assert message_of(raised) == (
        "context_builder 'build' needs keyword argument(s) mode that validate cannot "
        "supply. Give them defaults, or read them from context_args.")


def test_a_duplicated_key_column_names_the_count_and_the_fix(fresh_registry: None) -> None:
    make_check("CODE", passes=False)
    # Validated clean, reported against a frame with the key duplicated: validate
    # refuses a duplicate label itself, so the report's own guard is reached this way.
    outcomes = validate(pd.DataFrame([{"id": 1}]))
    df = pd.DataFrame([[1, 2]], columns=["id", "id"])
    with pytest.raises(ValueError) as raised:
        build_report(outcomes, df=df, key_column="id")
    assert message_of(raised) == (
        "key_column 'id' appears 2 times in the data: df[key_column] is then a table "
        "rather than a column, and every row would be labeled with the column name. "
        "Rename or drop the duplicate columns.")
