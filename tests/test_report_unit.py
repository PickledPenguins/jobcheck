"""Unit checks: the report library — collection, the failure table, rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import make_check, one_row_report
from jobcheck import registry as reg
from jobcheck import results as res
from jobcheck import report as rep
from jobcheck import validate
from jobcheck.results import PASS, Status, CheckResult

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
        return PASS if row["age"] is not None and not pd.isna(row["age"]) else CheckResult(Status.MISSING)

    @reg.register_check(code="AGE_IN_RANGE", message="Age is out of range",
                       depends_on=["AGE_PRESENT"])
    def age_in_range(row: "pd.Series[Any]") -> Any:
        if row["age"] > 130:
            return CheckResult(Status.INVALID, {"maximum": 130, "actual": row["age"]})
        if row["age"] < 0:
            return CheckResult(Status.INVALID, {"minimum": 0, "actual": row["age"]})
        return PASS


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


def test_validate_passes_overrides_through(two_layers: None) -> None:
    rule = reg.OverrideRule(name="off", action="disable", codes=["AGE_IN_RANGE"],
                            criteria=[], match_all=True, message="why the rule exists")
    collected = validate(FRAME, overrides=[rule])
    assert {o.outcome for row in collected for o in row if o.code == "AGE_IN_RANGE"} == {"disabled"}


def test_validate_can_be_made_fatal_on_a_raising_check(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        validate(FRAME, on_error="raise")


# --- building the report ----------------------------------------------------


def test_the_report_has_one_row_per_failure(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    assert list(report.columns) == rep.REPORT_COLUMNS
    assert list(report["code"]) == ["AGE_IN_RANGE", "AGE_PRESENT"]
    assert list(report["row"]) == ["102", "103"]


def test_a_clean_frame_produces_an_empty_report_with_columns(two_layers: None) -> None:
    report = report_for(pd.DataFrame([{"id": 1, "age": 30}]))
    assert report.empty
    assert list(report.columns) == rep.REPORT_COLUMNS


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


def test_rows_without_a_key_column_are_labelled_by_index(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME)
    assert list(report["row"]) == ["1", "2"]


def test_a_missing_key_value_is_labelled_rather_than_rendered_as_nan(two_layers: None) -> None:
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
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", extra_columns=["age"])
    assert list(report.columns) == ["row", "age", *rep.REPORT_COLUMNS[1:]]


def test_extra_columns_keep_the_order_they_were_given(two_layers: None) -> None:
    frame = pd.DataFrame([{"id": 1, "age": -5, "batch": "B1", "region": "EU"}])
    report = rep.build_report(validate(frame), df=frame, key_column="id",
                              extra_columns=["region", "batch"])
    assert list(report.columns)[:3] == ["row", "region", "batch"]


def test_a_data_column_repeats_on_every_failure_of_its_row(two_layers: None) -> None:
    frame = pd.DataFrame([{"id": 1, "age": -5, "batch": "B1"}])
    report = rep.build_report(validate(frame), df=frame, key_column="id",
                              extra_columns=["batch"])
    assert list(report["batch"]) == ["B1"]


def test_data_column_values_render_like_the_row_key(two_layers: None) -> None:
    """Whole floats lose the .0; a missing value is blank rather than nan."""

    frame = pd.DataFrame([{"id": 1, "age": -5, "batch": 7.0, "region": None}])
    report = rep.build_report(validate(frame), df=frame, key_column="id",
                              extra_columns=["batch", "region"])
    assert list(report["batch"]) == ["7"]
    assert list(report["region"]) == [""]


def test_extra_columns_reach_the_csv_too(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", extra_columns=["age"])
    assert rep.render_report(report, fmt="csv").splitlines()[0].startswith("row,age,code")


def test_extra_columns_work_without_a_key_column(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, extra_columns=["age"])
    assert list(report.columns)[:2] == ["row", "age"]


def test_an_empty_data_columns_list_changes_nothing(two_layers: None) -> None:
    assert list(rep.build_report(outcomes(), df=FRAME, extra_columns=[]).columns) == \
        rep.REPORT_COLUMNS


def test_an_unknown_data_column_is_rejected(two_layers: None) -> None:
    with pytest.raises(ValueError, match=r"extra_columns \['nope'\] cannot be used"):
        rep.build_report(outcomes(), df=FRAME, extra_columns=["nope"])


def test_a_repeated_data_column_is_rejected(two_layers: None) -> None:
    with pytest.raises(ValueError, match=r"extra_columns \['age'\] cannot be used"):
        rep.build_report(outcomes(), df=FRAME, extra_columns=["age", "age"])


def test_a_duplicated_frame_column_is_rejected_rather_than_misread(two_layers: None) -> None:
    """Regression: df[extra_columns] returns one value per matching column, so a
    duplicated label produced more values than names and zip paired them by
    position -- the second 'batch' value printed under the 'age' heading."""

    frame = pd.DataFrame([[1, "A", "B", -5]], columns=["id", "batch", "batch", "age"])
    outs = validate(pd.DataFrame([{"id": 1, "age": -5}]))
    with pytest.raises(ValueError, match=r"extra_columns \['batch'\] cannot be used"):
        rep.build_report(outs, df=frame, key_column="id", extra_columns=["batch", "age"])


def test_a_duplicate_elsewhere_in_the_frame_does_not_block_other_columns(
    two_layers: None,
) -> None:
    frame = pd.DataFrame([[1, "A", "B", -5]], columns=["id", "batch", "batch", "age"])
    outs = validate(pd.DataFrame([{"id": 1, "age": -5}]))
    report = rep.build_report(outs, df=frame, key_column="id", extra_columns=["age"])
    assert list(report["age"]) == ["-5"]


def test_a_data_column_colliding_with_a_report_column_is_rejected(two_layers: None) -> None:
    """Silently overwriting the report's own column would hide the failure."""

    frame = pd.DataFrame([{"id": 1, "age": -5, "code": "SOURCE-1"}])
    with pytest.raises(ValueError, match=r"extra_columns \['code'\] cannot be used"):
        rep.build_report(validate(frame), df=frame, key_column="id",
                         extra_columns=["code"])


def test_the_key_column_may_also_be_shown_as_a_data_column(two_layers: None) -> None:
    """Nothing stops it, and it is a reasonable thing to want when the key is
    also a value worth reading."""

    report = rep.build_report(outcomes(), df=FRAME, key_column="id", extra_columns=["id"])
    assert list(report["row"]) == list(report["id"])


def test_include_skipped_adds_the_blocked_tests_with_their_reason(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", include="blocked")
    skipped = report[report["outcome"] == "skipped"]
    assert list(skipped["code"]) == ["AGE_IN_RANGE"]
    assert list(skipped["detail"]) == ["prerequisite did not pass: AGE_PRESENT"]


def test_include_passed_turns_the_report_into_an_audit_trail(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id", include="all")
    assert len(report) == 6
    assert set(report["outcome"]) == {"passed", "failed", "skipped"}


def test_an_errored_test_appears_in_the_report(fresh_registry: None) -> None:
    make_check("BOOM", raises=RuntimeError("boom"))
    report = report_for(pd.DataFrame([{"age": 1}]))
    assert list(report["outcome"]) == ["errored"]
    assert list(report["status"]) == ["ERROR (9)"]
    assert list(report["detail"]) == ["RuntimeError: boom"]


# --- rendering --------------------------------------------------------------


def test_comments_render_sorted_so_output_is_stable() -> None:
    assert rep.render_comments({"zebra": 1, "actual": 2}) == "actual=2; zebra=1"


def test_empty_comments_render_as_nothing() -> None:
    assert rep.render_comments({}) == ""


def test_the_table_format_is_bordered_and_wrapped(two_layers: None) -> None:
    text = rep.render_report(rep.build_report(outcomes(), df=FRAME, key_column="id"))
    header, divider, first = text.splitlines()[:3]
    assert [part.strip() for part in header.split(" | ")[:3]] == ["row", "code", "status"]
    assert set(divider) <= {"-", "+"}
    assert first.startswith("102")


def test_the_csv_format_round_trips(two_layers: None) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    parsed = pd.read_csv(pd.io.common.StringIO(rep.render_report(report, fmt="csv")))
    assert list(parsed.columns) == rep.REPORT_COLUMNS
    assert list(parsed["code"]) == ["AGE_IN_RANGE", "AGE_PRESENT"]


def test_an_unknown_format_is_rejected(two_layers: None) -> None:
    with pytest.raises(ValueError, match="fmt must be 'table' or 'csv', got 'json'"):
        rep.render_report(rep.build_report(outcomes(), df=FRAME), fmt="json")


def test_write_report_writes_what_render_report_returns(two_layers: None, tmp_path: Path) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    path = tmp_path / "report.csv"
    rep.write_report(report, str(path))
    assert path.read_text(encoding="utf-8") == rep.render_report(report, fmt="csv")


def test_write_report_can_write_the_table_format(two_layers: None, tmp_path: Path) -> None:
    report = rep.build_report(outcomes(), df=FRAME, key_column="id")
    path = tmp_path / "report.txt"
    rep.write_report(report, str(path), fmt="table")
    assert path.read_text(encoding="utf-8").startswith("row ")


def test_print_report_prints_the_rendered_table(
    two_layers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    rep.print_report(rep.build_report(outcomes(), df=FRAME, key_column="id"))
    out = capsys.readouterr().out
    assert "AGE_IN_RANGE" in out
    assert out.splitlines()[0].startswith("row")


def test_print_report_says_so_when_nothing_failed(
    two_layers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    rep.print_report(report_for(pd.DataFrame([{"id": 1, "age": 30}])))
    assert capsys.readouterr().out == "No failures.\n"


# --- explanations and summaries --------------------------------------------


def test_row_explanation_lists_every_test_in_order(two_layers: None) -> None:
    table = rep.row_explanation(outcomes()[2])
    assert list(table.columns) == ["layer", "code", "outcome", "status", "detail"]
    assert list(table["code"]) == ["AGE_PRESENT", "AGE_IN_RANGE"]


def test_only_relevant_hides_the_tests_that_passed(two_layers: None) -> None:
    table = rep.row_explanation(outcomes()[1], include="blocked")
    assert list(table["code"]) == ["AGE_IN_RANGE"]


def test_print_row_explanation_ends_with_the_root_cause(
    two_layers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    rep.print_row_explanation(outcomes()[1])
    assert capsys.readouterr().out.strip().endswith("root cause: AGE_IN_RANGE")


def test_print_row_explanation_says_when_the_row_passed(
    two_layers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    rep.print_row_explanation(outcomes()[0])
    assert "root cause: none - the row passed" in capsys.readouterr().out


def test_the_summary_counts_every_status(two_layers: None) -> None:
    table = rep.summarize_outcomes(outcomes()).set_index("code")
    assert list(table.loc["AGE_PRESENT"]) == [0, 1, 0, 0, 0, 2]
    assert list(table.loc["AGE_IN_RANGE"]) == [1, 1, 0, 1, 0, 1]


def test_the_summary_puts_the_worst_test_first(two_layers: None) -> None:
    assert set(rep.summarize_outcomes(outcomes())["code"][:2]) == {"AGE_IN_RANGE", "AGE_PRESENT"}


def test_the_summary_of_nothing_has_columns_and_no_rows(fresh_registry: None) -> None:
    table = rep.summarize_outcomes([])
    assert table.empty
    assert list(table.columns) == [
        "code", "layer", "failed", "errored", "skipped", "disabled", "passed"
    ]


def test_root_cause_counts_is_importable_from_the_package() -> None:
    """Regression: it was documented as part of the reporting surface but never
    re-exported, so importing it raised."""

    from jobcheck import root_cause_counts

    assert root_cause_counts is rep.root_cause_counts


def test_root_cause_counts_rank_by_rows(fresh_registry: None) -> None:
    make_check("COMMON", passes=False)
    frame = pd.DataFrame([{"age": 1}, {"age": 2}])
    assert rep.root_cause_counts(validate(frame)).to_dict("records") == [
        {"root_cause": "COMMON", "rows": 2}
    ]


def test_print_summary_shows_counts_and_the_root_cause_tally(
    two_layers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    rep.print_summary(outcomes())
    out = capsys.readouterr().out
    assert "skipped" in out
    assert "Root cause of each failing row:" in out
    assert "AGE_IN_RANGE | 1" in out
    assert "AGE_PRESENT  | 1" in out


def test_print_summary_says_when_every_row_passed(
    two_layers: None, capsys: pytest.CaptureFixture[str]
) -> None:
    rep.print_summary(outcomes(pd.DataFrame([{"id": 1, "age": 30}])))
    assert "Root causes: none - every row passed." in capsys.readouterr().out


def test_print_summary_with_no_rows_says_nothing_ran(
    fresh_registry: None, capsys: pytest.CaptureFixture[str]
) -> None:
    table = rep.print_summary([])
    assert capsys.readouterr().out == "No checks ran.\n"
    assert table.empty


def test_validate_hands_each_row_the_context_its_builder_returned(
    fresh_registry: None,
) -> None:
    """The context_builder is the adopter's one hook, so its result has to arrive.

    Written against a surviving mutant: passing ``context=None`` instead of
    ``context_builder(row)`` broke nothing any check asserted.
    """

    from jobcheck import FAILED, PASS, PASSED, RowContext

    # A plain subclass rather than a nested dataclass: fresh_registry evicts the
    # test module from sys.modules, and @dataclass resolves annotations through
    # it when the class is built inside a function.
    class Allowed(RowContext):
        def __init__(self, allowed: bool) -> None:
            self.allowed = allowed

    @reg.register_check(code="NEEDS_CTX", message="the context said no")
    def check(row: "pd.Series[Any]", context: "RowContext | None") -> CheckResult:
        if context is None:
            return CheckResult(Status.INVALID, {"context": "missing"})
        allowed = getattr(context, "allowed", False)
        return PASS if allowed else CheckResult(Status.INVALID, {"allowed": allowed})

    frame = pd.DataFrame([{"id": 1, "allow": True}, {"id": 2, "allow": False}])
    outcomes = validate(
        frame, context_builder=lambda row: Allowed(allowed=bool(row["allow"]))
    )
    assert [o[0].outcome for o in outcomes] == [PASSED, FAILED]
    assert outcomes[1][0].comments == {"allowed": False}


# --- what lands on disk -----------------------------------------------------
#
# Written against surviving mutants: the encoding and the newline handling of
# write_report were both dropped without a check noticing, and each decides
# whether the file another tool reads is the file this one meant to write.


def test_a_written_report_is_utf_8(fresh_registry: None, tmp_path: Path) -> None:
    report = one_row_report(comments={"value": "Karen Spärck Jones"})
    path = tmp_path / "report.csv"
    rep.write_report(report, str(path))
    raw = path.read_bytes()
    assert "Spärck".encode("utf-8") in raw
    assert raw.decode("utf-8")


def test_a_written_report_uses_unix_line_endings(fresh_registry: None,
                                                 tmp_path: Path) -> None:
    """csv writes \\r\\n unless the handle is opened with newline=""."""

    report = one_row_report()
    path = tmp_path / "report.csv"
    rep.write_report(report, str(path))
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def formula_report(fresh: None) -> pd.DataFrame:
    """A report whose data column holds a value a spreadsheet would execute."""

    make_check("CELL", passes=False)
    frame = pd.DataFrame([{"id": 1, "name": "=SUM(A1:A9)"}])
    return rep.build_report(validate(frame), df=frame, key_column="id",
                            extra_columns=["name"])


def test_a_written_report_escapes_formulas_by_default(fresh_registry: None,
                                                      tmp_path: Path) -> None:
    path = tmp_path / "report.csv"
    rep.write_report(formula_report(fresh_registry), str(path))
    assert "'=SUM(A1:A9)" in path.read_text(encoding="utf-8")


def test_an_empty_explanation_still_has_its_columns(fresh_registry: None) -> None:
    """A caller building a frame from several explanations needs the shape even
    when one row explained nothing."""

    assert list(rep.row_explanation([]).columns) == [
        "layer", "code", "outcome", "status", "detail"]


def test_printing_a_report_wraps_the_message_column(fresh_registry: None,
                                                    capsys: Any) -> None:
    """print_report passes its wrap width down; without it a long message runs
    the table off the screen."""

    report = one_row_report(message="a message far longer than the wrap width "
                                    "chosen for the report table by default")
    rep.print_report(report)
    out = capsys.readouterr().out
    assert max(len(line) for line in out.splitlines()) < 200
    assert len(out.splitlines()) > 3


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
    assert report.iloc[0]["is_root_cause"] is False or not report.iloc[0]["is_root_cause"]


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
        rep.build_report(validate(frame), df=frame, extra_columns=["code"])
