"""Unit checks: the report library — collection, the failure table, rendering."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import engine
from jobcheck import registry as reg
from jobcheck import results as res
from jobcheck import report as rep
from jobcheck import tables, validate
from jobcheck.results import OK, Status, Verdict

pytestmark = pytest.mark.fast

FRAME = pd.DataFrame(
    [
        {"id": 101, "age": 34},     # clean
        {"id": 102, "age": -5},     # fails AGE_IN_RANGE
        {"id": 103, "age": None},   # fails AGE_PRESENT, which blocks AGE_IN_RANGE
    ]
)


@pytest.fixture
def two_layers(fresh_registry: None) -> None:
    """A root check that fails on some rows, and a dependent that it blocks."""

    @reg.register_check(code="AGE_PRESENT", message="Age is missing")
    def age_present(row: "pd.Series[Any]") -> Any:
        return OK if row["age"] is not None and not pd.isna(row["age"]) else Verdict(Status.MISSING)

    @reg.register_check(code="AGE_IN_RANGE", message="Age is out of range",
                       depends_on=["AGE_PRESENT"])
    def age_in_range(row: "pd.Series[Any]") -> Any:
        if row["age"] > 130:
            return Verdict(Status.INVALID, {"maximum": 130, "actual": row["age"]})
        if row["age"] < 0:
            return Verdict(Status.INVALID, {"minimum": 0, "actual": row["age"]})
        return OK


def outcomes(df: pd.DataFrame = FRAME) -> list[list[res.CheckOutcome]]:
    return validate(df)


def report_for(df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    """Build a report for a frame the test made up on the spot."""

    return rep.build_report(validate(df), df=df, **kwargs)


# --- collection -------------------------------------------------------------


def test_validate_returns_one_list_per_row(two_layers: None) -> None:
    collected = outcomes()
    assert len(collected) == len(FRAME)
    assert [o.code for o in collected[0]] == ["AGE_PRESENT", "AGE_IN_RANGE"]


def test_validate_passes_rules_through(two_layers: None) -> None:
    rule = reg.Rule(name="off", action="disable", codes=["AGE_IN_RANGE"],
                            criteria=[], match_all=True, message="why the rule exists")
    collected = validate(FRAME, rules=[rule])
    assert {o.outcome for row in collected for o in row if o.code == "AGE_IN_RANGE"} == {"disabled"}


def test_validate_can_be_made_fatal_on_a_raising_check(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        validate(FRAME, on_error="raise")


# --- building the report ----------------------------------------------------


def test_the_report_has_one_row_per_failure(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    assert tuple(report.columns) == rep._REPORT_COLUMNS
    assert list(report["code"]) == ["AGE_IN_RANGE", "AGE_PRESENT"]
    assert list(report["row"]) == ["102", "103"]


def test_a_clean_frame_produces_an_empty_report_with_columns(two_layers: None) -> None:
    report = report_for(pd.DataFrame([{"id": 1, "age": 30}]))
    assert report.empty
    assert tuple(report.columns) == rep._REPORT_COLUMNS


def test_the_report_carries_status_layer_and_comments(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id").set_index("row")
    row = report.loc["102"]
    assert row["status"] == "INVALID (3)"
    assert row["layer"] == 1
    assert row["comments"] == "actual=-5.0; minimum=0"
    assert row["message"] == "Age is out of range"


def test_two_failures_at_the_same_layer_are_both_root_causes(fresh_registry: None) -> None:
    """Neither is upstream of the other, so naming one of them would be arbitrary."""

    make_check("FIRST", passes=False)
    make_check("SECOND", passes=False)
    report = report_for(pd.DataFrame([{"age": 1}]))
    assert list(report["is_root_cause"]) == [True, True]


def test_a_failure_below_another_is_not_a_root_cause(fresh_registry: None) -> None:
    make_check("PARENT")
    make_check("FIRST", passes=False)
    make_check("CHILD", passes=False, depends_on=["PARENT"])
    report = report_for(pd.DataFrame([{"age": 1}]))
    flagged = dict(zip(report["code"], report["is_root_cause"]))
    assert flagged == {"FIRST": True, "CHILD": False}


def test_a_broken_check_never_takes_the_flag_from_a_data_failure(
    fresh_registry: None,
) -> None:
    """Decided 2026-09-28 (F.47): data failures come first. The broken check sits on
    layer 0 and the real failure on layer 1, yet the real one is flagged."""

    make_check("BROKEN", raises=RuntimeError("bug"))
    make_check("PARENT")
    make_check("REAL", passes=False, depends_on=["PARENT"])
    outcomes = validate(pd.DataFrame([{"age": 1}]))
    assert engine.root_causes(outcomes[0]) == ["REAL"]
    summary = rep.summarize_outcomes(outcomes).set_index("code")
    assert summary.loc["BROKEN", "root_cause_rows"] == 0
    assert summary.loc["REAL", "root_cause_rows"] == 1


def test_a_row_whose_only_problem_is_a_broken_check_is_still_flagged(
    fresh_registry: None,
) -> None:
    """Otherwise a filter on is_root_cause would never show the row at all."""

    make_check("BROKEN", raises=RuntimeError("bug"))
    make_check("FINE")
    report = report_for(pd.DataFrame([{"age": 1}]))
    assert list(zip(report["code"], report["is_root_cause"])) == [("BROKEN", True)]
    assert rep.summarize_outcomes(validate(pd.DataFrame([{"age": 1}]))).set_index(
        "code").loc["BROKEN", "root_cause_rows"] == 1


def test_rows_without_a_key_column_are_labeled_by_index(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME)
    assert list(report["row"]) == ["1", "2"]


def test_a_missing_key_value_is_labeled_rather_than_rendered_as_nan(two_layers: None) -> None:
    frame = pd.DataFrame([{"id": None, "age": -5}])
    report = rep.build_report(validate(frame), df=frame, key_column="id")
    assert list(report["row"]) == ["<no key>"]


def test_without_a_frame_rows_are_numbered_by_position(two_layers: None) -> None:
    assert list(rep.build_report(outcomes(), df=FRAME)["row"]) == ["1", "2"]


def test_a_whole_float_key_loses_its_decimal(two_layers: None) -> None:
    """An integer id column pandas widened to float still reads as 102, not 102.0."""

    frame = pd.DataFrame([{"id": 102.0, "age": -5}])
    report = rep.build_report(validate(frame), df=frame, key_column="id")
    assert list(report["row"]) == ["102"]


def test_an_unknown_key_column_is_rejected(two_layers: None) -> None:
    with pytest.raises(ValueError, match=r"key_column 'nope' is not in the data"):
        rep.build_report(outcomes(), df=FRAME, key_column="nope")


def test_a_frame_of_the_wrong_length_is_rejected(two_layers: None) -> None:
    with pytest.raises(ValueError, match="outcomes cover 3 row\\(s\\) but the frame has 1"):
        rep.build_report(outcomes(), df=FRAME.head(1))


# --- data columns -----------------------------------------------------------


def test_extra_columns_sit_between_the_row_key_and_the_code(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", add_columns=["age"])
    assert tuple(report.columns) == ("row", "age", *rep._REPORT_COLUMNS[1:])


def test_extra_columns_keep_the_order_they_were_given(two_layers: None) -> None:
    frame = pd.DataFrame([{"id": 1, "age": -5, "batch": "B1", "region": "EU"}])
    report = rep.build_report(validate(frame), df=frame, key_column="id",
                              add_columns=["region", "batch"])
    assert list(report.columns)[:3] == ["row", "region", "batch"]


def test_a_data_column_repeats_on_every_failure_of_its_row(two_layers: None) -> None:
    frame = pd.DataFrame([{"id": 1, "age": -5, "batch": "B1"}])
    report = rep.build_report(validate(frame), df=frame, key_column="id",
                              add_columns=["batch"])
    assert list(report["batch"]) == ["B1"]


def test_data_column_values_render_like_the_row_key(two_layers: None) -> None:
    """Whole floats lose the .0; a missing value is blank rather than nan."""

    frame = pd.DataFrame([{"id": 1, "age": -5, "batch": 7.0, "region": None}])
    report = rep.build_report(validate(frame), df=frame, key_column="id",
                              add_columns=["batch", "region"])
    assert list(report["batch"]) == ["7"]
    assert list(report["region"]) == [""]


def test_extra_columns_reach_the_csv_too(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", add_columns=["age"])
    assert report.to_csv(index=False).splitlines()[0].startswith("row,age,code")


def test_extra_columns_work_without_a_key_column(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, add_columns=["age"])
    assert list(report.columns)[:2] == ["row", "age"]


def test_an_empty_data_columns_list_changes_nothing(two_layers: None) -> None:
    assert tuple(rep.build_report(outcomes(), df=FRAME, add_columns=[]).columns) == \
        rep._REPORT_COLUMNS


def test_an_unknown_data_column_is_rejected(two_layers: None) -> None:
    with pytest.raises(ValueError, match=r"add_columns \['nope'\] cannot be used"):
        rep.build_report(outcomes(), df=FRAME, add_columns=["nope"])


def test_a_repeated_data_column_is_rejected(two_layers: None) -> None:
    with pytest.raises(ValueError, match=r"add_columns \['age'\] cannot be used"):
        rep.build_report(outcomes(), df=FRAME, add_columns=["age", "age"])


def test_a_duplicated_frame_column_is_rejected_rather_than_misread(two_layers: None) -> None:
    """Regression: df[add_columns] returns one value per matching column, so a
    duplicated label produced more values than names and zip paired them by
    position -- the second 'batch' value printed under the 'age' heading."""

    frame = pd.DataFrame([[1, "A", "B", -5]], columns=["id", "batch", "batch", "age"])
    outs = validate(pd.DataFrame([{"id": 1, "age": -5}]))
    with pytest.raises(ValueError, match=r"add_columns \['batch'\] cannot be used"):
        rep.build_report(outs, df=frame, key_column="id", add_columns=["batch", "age"])


def test_a_duplicated_key_column_is_rejected_rather_than_misread(two_layers: None) -> None:
    """Regression: df[key_column] is a DataFrame when the label is repeated, so
    every row was labeled with the column *name* -- 'id' on every line -- and
    zip() then truncated the report to the number of labels produced."""

    frame = pd.DataFrame([[1, "A", 1], [2, "B", 2]], columns=["id", "batch", "id"])
    outs = validate(pd.DataFrame([{"id": 1, "age": -5}, {"id": 2, "age": -5}]))
    with pytest.raises(ValueError, match=r"key_column 'id' appears 2 times"):
        rep.build_report(outs, df=frame, key_column="id")


def test_a_duplicate_elsewhere_in_the_frame_does_not_block_other_columns(
    two_layers: None,
) -> None:
    frame = pd.DataFrame([[1, "A", "B", -5]], columns=["id", "batch", "batch", "age"])
    outs = validate(pd.DataFrame([{"id": 1, "age": -5}]))
    report = rep.build_report(outs, df=frame, key_column="id", add_columns=["age"])
    assert list(report["age"]) == ["-5"]


def test_a_data_column_colliding_with_a_report_column_is_rejected(two_layers: None) -> None:
    """Silently overwriting the report's own column would hide the failure."""

    frame = pd.DataFrame([{"id": 1, "age": -5, "code": "SOURCE-1"}])
    with pytest.raises(ValueError, match=r"add_columns \['code'\] cannot be used"):
        rep.build_report(validate(frame), df=frame, key_column="id",
                         add_columns=["code"])


def test_the_key_column_may_also_be_shown_as_a_data_column(two_layers: None) -> None:
    """Nothing stops it, and it is a reasonable thing to want when the key is
    also a value worth reading."""

    report = rep.build_report(outcomes(), df=FRAME, key_column="id", add_columns=["id"])
    assert list(report["row"]) == list(report["id"])


def test_include_skipped_adds_the_blocked_checks_with_their_reason(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", include="blocked")
    skipped = report[report["outcome"] == "skipped"]
    assert list(skipped["code"]) == ["AGE_IN_RANGE"]
    assert list(skipped["detail"]) == ["prerequisite did not pass: AGE_PRESENT"]


def test_include_passed_turns_the_report_into_an_audit_trail(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", include="all")
    assert len(report) == 6
    assert set(report["outcome"]) == {"passed", "failed", "skipped"}


def test_an_errored_check_appears_in_the_report(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("boom"))
    report = report_for(pd.DataFrame([{"age": 1}]))
    assert list(report["outcome"]) == ["errored"]
    assert list(report["status"]) == ["ERROR (9)"]
    assert list(report["detail"]) == ["RuntimeError: boom"]


# --- comments and titles ------------------------------------------------------


def test_comments_render_sorted_so_output_is_stable() -> None:
    assert rep.render_comments({"zebra": 1, "actual": 2}) == "actual=2; zebra=1"


def test_empty_comments_render_as_nothing() -> None:
    assert rep.render_comments({}) == ""


def test_every_table_carries_its_own_title(two_layers: None) -> None:
    """What lets a caller head each table without naming it."""

    assert rep.build_report(outcomes(), df=FRAME).attrs["title"] == "Report"
    assert rep.row_explanation(outcomes()[0]).attrs["title"] == "Row explanation"
    assert rep.summarize_outcomes(outcomes()).attrs["title"] == "Summary"


def test_the_title_survives_selecting_and_filtering(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    narrowed = report[report["code"] == "AGE_PRESENT"][["row", "code"]]
    assert narrowed.attrs["title"] == "Report"


# --- explanations and summaries --------------------------------------------


def test_row_explanation_lists_every_check_in_order(two_layers: None) -> None:
    table = rep.row_explanation(outcomes()[2])
    assert list(table.columns) == ["layer", "code", "outcome", "status", "detail"]
    assert list(table["code"]) == ["AGE_PRESENT", "AGE_IN_RANGE"]


def test_only_relevant_hides_the_checks_that_passed(two_layers: None) -> None:
    table = rep.row_explanation(outcomes()[1], include="blocked")
    assert list(table["code"]) == ["AGE_IN_RANGE"]


def test_the_summary_counts_every_status(two_layers: None) -> None:
    table = rep.summarize_outcomes(outcomes()).set_index("code")
    assert table.loc["AGE_PRESENT"].to_dict() == {
        "layer": 0, "failed": 1, "root_cause_rows": 1, "errored": 0, "skipped": 0,
        "disabled": 0, "passed": 2}
    assert table.loc["AGE_IN_RANGE"].to_dict() == {
        "layer": 1, "failed": 1, "root_cause_rows": 1, "errored": 0, "skipped": 1,
        "disabled": 0, "passed": 1}


def test_the_summary_puts_the_worst_check_first(fresh_registry: None) -> None:
    """Most failures first, then most errors, then most skips, then by code.

    Three checks with distinct failure counts, asserted as a list: a set of the
    first two codes in a two-check registry was true in any order.
    """

    make_check("RARE", passes=False)
    make_check("COMMON", passes=False)
    make_check("NEVER")
    frame = pd.DataFrame([{"age": 1}, {"age": 2}, {"age": 3}])
    collected = validate(frame)
    # Turn RARE's failure on rows 2 and 3 into passes, so it fails once.
    for row_outcomes in collected[1:]:
        rare = next(o for o in row_outcomes if o.code == "RARE")
        rare.outcome = res.Outcome.PASSED
    assert list(rep.summarize_outcomes(collected)["code"]) == ["COMMON", "RARE", "NEVER"]


def test_the_summary_of_nothing_has_columns_and_no_rows(fresh_registry: None) -> None:
    table = rep.summarize_outcomes([])
    assert table.empty
    assert list(table.columns) == [
        "code", "layer", "failed", "root_cause_rows", "errored", "skipped", "disabled",
        "passed"
    ]


def test_root_cause_rows_counts_the_rows_each_code_explains(fresh_registry: None) -> None:
    """Two codes failing at the same layer on the same row are both its root
    cause, so the row counts against each."""

    make_check("RARE", passes=False)
    make_check("COMMON", passes=False)
    frame = pd.DataFrame([{"age": 1}, {"age": 2}])
    collected = validate(frame)
    rare = next(o for o in collected[1] if o.code == "RARE")
    rare.outcome = res.Outcome.PASSED
    table = rep.summarize_outcomes(collected).set_index("code")
    assert table["root_cause_rows"].to_dict() == {"COMMON": 2, "RARE": 1}


def test_a_check_that_never_was_a_root_cause_counts_zero(two_layers: None) -> None:
    table = rep.summarize_outcomes(outcomes(pd.DataFrame([{"id": 1, "age": 30}])))
    assert list(table["root_cause_rows"]) == [0, 0]


def test_validate_hands_each_row_the_context_its_builder_returned(
    fresh_registry: None,
) -> None:
    """The context_builder is the adopter's one hook, so its result has to arrive.

    Written against a surviving mutant: passing ``context=None`` instead of
    ``context_builder(row)`` broke nothing any check asserted.
    """

    from jobcheck import OK, RowContext, Outcome

    # A plain subclass rather than a nested dataclass: fresh_registry evicts the
    # test module from sys.modules, and @dataclass resolves annotations through
    # it when the class is built inside a function.
    class Allowed(RowContext):
        def __init__(self, allowed: bool) -> None:
            self.allowed = allowed

    @reg.register_check(code="NEEDS_CTX", message="the context said no")
    def check(row: "pd.Series[Any]", context: "RowContext | None") -> Verdict:
        if context is None:
            return Verdict(Status.INVALID, {"context": "missing"})
        allowed = getattr(context, "allowed", False)
        return OK if allowed else Verdict(Status.INVALID, {"allowed": allowed})

    frame = pd.DataFrame([{"id": 1, "allow": True}, {"id": 2, "allow": False}])
    outcomes = validate(
        frame, context_builder=lambda row: Allowed(allowed=bool(row["allow"]))
    )
    assert [o[0].outcome for o in outcomes] == [Outcome.PASSED, Outcome.FAILED]
    assert outcomes[1][0].comments == {"allowed": False}





def test_the_summary_reads_a_generator_once_and_still_finds_the_root_causes(
    two_layers: None,
) -> None:
    """The counts and the root causes come from one walk, so a generator of
    outcomes is not spent before the second."""

    table = rep.summarize_outcomes(row for row in outcomes())
    assert table["root_cause_rows"].sum() == 2


def test_the_summary_refuses_validate_rows_failures_only_lists(two_layers: None) -> None:
    """Counted as if complete, they dropped AGE_IN_RANGE's blocked row and every
    pass, and printed the wrong counts with nothing to say so."""

    failures_only = [engine.validate_row(row) for _, row in FRAME.iterrows()]
    assert [len(row) for row in failures_only] == [0, 1, 1]
    with pytest.raises(ValueError) as raised:
        rep.summarize_outcomes(failures_only)
    assert str(raised.value) == (
        "summarize_outcomes needs every check's outcome on every row, but the list for "
        "row 1 holds 1 and the one before it 0: pass validate's result, or explain_row's "
        "per row. validate_row keeps only the failures.")


def test_explain_row_per_row_is_the_streaming_form_of_the_summary(two_layers: None) -> None:
    streamed = rep.summarize_outcomes(engine.explain_row(row) for _, row in FRAME.iterrows())
    pd.testing.assert_frame_equal(streamed, rep.summarize_outcomes(outcomes()))


def test_a_report_beyond_failures_refuses_failures_only_lists(two_layers: None) -> None:
    """`include="blocked"` would print no skipped line from such a list; the
    failures-only default reads nothing they lack, so it takes them."""

    failures_only = [engine.validate_row(row) for _, row in FRAME.iterrows()]
    assert len(rep.build_report(failures_only, df=FRAME)) == 2
    with pytest.raises(ValueError, match=r"^build_report\(include='blocked'\) needs every "
                                         "check's outcome on every row, but the list for "
                                         "row 1 holds 1 and the one before it 0"):
        rep.build_report(failures_only, df=FRAME, include="blocked")


def test_a_short_last_list_is_named_by_its_own_row(two_layers: None) -> None:
    """Each list is compared with the one before it, and named by its own position."""

    complete = outcomes()
    lists = [complete[0], complete[1], complete[2][:1]]
    with pytest.raises(ValueError, match="the list for row 2 holds 1 and the one before it 2"):
        rep.build_report(lists, df=FRAME, include="all")


def test_an_empty_explanation_still_has_its_columns(fresh_registry: None) -> None:
    """A caller building a frame from several explanations needs the shape even
    when one row explained nothing."""

    assert list(rep.row_explanation([]).columns) == [
        "layer", "code", "outcome", "status", "detail"]


# --- root causes, and keys that identify a row ------------------------------


def two_independent_failures(fresh: None) -> tuple[list[list[Any]], pd.DataFrame]:
    """A row failing two chains: one deep, one shallow, deep registered first."""

    make_check("P")
    make_check("Q", depends_on=["P"])
    make_check("DEEP", passes=False, depends_on=["Q"])
    make_check("SHALLOW_A", passes=False)
    make_check("SHALLOW_B", passes=False)
    frame = pd.DataFrame([{"id": 1}])
    return validate(frame), frame


def test_every_failure_at_the_shallowest_layer_is_a_root_cause(fresh_registry: None) -> None:
    """Two failures at the same depth are two root causes, not a race between them."""

    outcomes, frame = two_independent_failures(fresh_registry)
    report = rep.build_report(outcomes, df=frame)
    flagged = set(report.loc[report["is_root_cause"], "code"])
    assert flagged == {"SHALLOW_A", "SHALLOW_B"}


def test_a_deeper_failure_is_not_a_root_cause(fresh_registry: None) -> None:
    outcomes, frame = two_independent_failures(fresh_registry)
    report = rep.build_report(outcomes, df=frame)
    assert not report.loc[report["code"] == "DEEP", "is_root_cause"].any()


def test_the_root_cause_is_not_always_the_first_line(fresh_registry: None) -> None:
    """The claim the docstring used to make, pinned as false so it stays fixed."""

    outcomes, frame = two_independent_failures(fresh_registry)
    report = rep.build_report(outcomes, df=frame)
    assert report.iloc[0]["code"] == "DEEP"
    assert not report.iloc[0]["is_root_cause"]


def test_a_single_key_column_may_hold_the_separator(fresh_registry: None) -> None:
    """Nothing is joined, so nothing is ambiguous."""

    make_check("FAILS", passes=False)
    frame = pd.DataFrame([{"k1": "a|b"}])
    report = rep.build_report(validate(frame), df=frame, key_column="k1")
    assert list(report["row"]) == ["a|b"]




def test_an_unknown_include_level_names_the_levels(two_layers: None) -> None:
    with pytest.raises(ValueError, match="include must be one of failures, blocked, all"):
        rep.build_report(outcomes(), df=FRAME, include="everything")


def test_row_explanation_rejects_an_unknown_include_level(two_layers: None) -> None:
    with pytest.raises(ValueError, match="include must be one of"):
        rep.row_explanation(outcomes()[0], include="everything")


def test_a_frame_offering_no_extra_columns_says_so(fresh_registry: None) -> None:
    """Every column of this frame is one the report already uses, so there is
    nothing left to ask for, and the message says that rather than listing air."""

    make_check("FAILS", passes=False)
    frame = pd.DataFrame([{"code": "x", "status": "y"}])
    with pytest.raises(ValueError, match=r"be one of: \(none available\)"):
        rep.build_report(validate(frame), df=frame, add_columns=["code"])


# --- which columns the report shows -------------------------------------------


def test_the_report_shows_its_default_columns_in_their_order(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    assert list(report.columns) == tables._DEFAULT_COLUMNS["Report"]


def test_editing_the_defaults_changes_every_report(two_layers: None, monkeypatch: Any) -> None:
    """The one place a run's shipped columns are chosen, with no argument per call."""

    monkeypatch.setitem(tables._DEFAULT_COLUMNS, "Report", ["row", "code", "message"])
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", add_columns=["age"])
    assert list(report.columns) == ["row", "age", "code", "message"]


def test_added_columns_lead_when_the_defaults_leave_out_row(
    two_layers: None, monkeypatch: Any
) -> None:
    monkeypatch.setitem(tables._DEFAULT_COLUMNS, "Report", ["code", "status"])
    report = rep.build_report(outcomes(), df=FRAME, add_columns=["age"])
    assert list(report.columns) == ["age", "code", "status"]


def test_a_report_column_hidden_by_the_defaults_is_not_a_data_column(
    two_layers: None, monkeypatch: Any
) -> None:
    """add_columns copies data in; a hidden report column comes back only by
    editing the defaults, so one argument never means two things."""

    monkeypatch.setitem(tables._DEFAULT_COLUMNS, "Report", ["row", "code"])
    with pytest.raises(ValueError, match=r"add_columns \['comments'\] cannot be used"):
        rep.build_report(outcomes(), df=FRAME, add_columns=["comments"])


def test_dropping_a_column_with_pandas_keeps_the_title(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    trimmed = report.drop(columns=["comments", "detail"])
    assert trimmed.attrs["title"] == "Report"
    assert "comments" not in trimmed.columns


def test_add_columns_reads_a_column_whose_label_is_a_number(fresh_registry: None) -> None:
    """Asked for by name as text, read by the frame's own label: `"5"` passed the
    check against the offered names and then raised KeyError on `df[["5"]]`."""

    make_check("ALWAYS", passes=False)
    frame = pd.DataFrame({5: ["five"], "id": [1]})
    report = rep.build_report(validate(frame), df=frame, add_columns=["5"])
    assert report[["row", "5", "code"]].values.tolist() == [["0", "five", "ALWAYS"]]


# --- found by reading the mutation survivors, 2026-09-25 ---------------------


def a_long(word: str, count: int = 12) -> str:
    """Text wider than any wrap width here, breakable only between words."""

    return " ".join([word] * count)


def outcome(code: str, outcome: res.Outcome, **fields: Any) -> res.CheckOutcome:
    return res.CheckOutcome(code=code, outcome=outcome, **fields)


def test_summary_ties_on_failed_are_broken_by_errored_worst_first() -> None:
    frame_outcomes = [
        [outcome("A_CODE", res.Outcome.FAILED), outcome("Z_CODE", res.Outcome.FAILED)],
        [outcome("A_CODE", res.Outcome.PASSED), outcome("Z_CODE", res.Outcome.ERRORED)],
    ]
    assert list(rep.summarize_outcomes(frame_outcomes)["code"]) == ["Z_CODE", "A_CODE"]


def test_root_cause_rows_count_rows_not_names() -> None:
    frame_outcomes = [
        [outcome("A_CODE", res.Outcome.FAILED)],
        [outcome("Z_CODE", res.Outcome.FAILED)],
        [outcome("Z_CODE", res.Outcome.FAILED)],
    ]
    table = rep.summarize_outcomes(frame_outcomes)
    assert table[["code", "root_cause_rows"]].values.tolist() == [["Z_CODE", 2],
                                                                 ["A_CODE", 1]]


def test_a_null_index_label_is_named_no_key(two_layers: None) -> None:
    """Without a key column the index labels the rows, and an index can hold a
    null as easily as a column can -- a set_index on a column with blanks."""

    df = FRAME.copy()
    df.index = pd.Index(["a", "b", None])
    report = rep.build_report(outcomes(df), df=df)
    assert "<no key>" in list(report["row"])
