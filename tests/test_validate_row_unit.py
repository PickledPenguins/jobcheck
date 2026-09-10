"""Unit tests: the per-row algorithm, its outcomes, and dependency skipping."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import pytest

from conftest import make_test
from pandas_row_validation import RowContext, registry as reg
from pandas_row_validation.results import ERRORED, FAILED, PASS, PASSED, SKIPPED, Status, TestResult

pytestmark = pytest.mark.fast

ROW = pd.Series({"age": 30, "email": "a@b.com"})


def disable(code: str, name: str = "kill_it") -> reg.OverrideRule:
    return reg.OverrideRule(name=name, action="disable", codes=[code], criteria=[], match_all=True)


def enable(code: str, name: str = "switch_on") -> reg.OverrideRule:
    return reg.OverrideRule(name=name, action="enable", codes=[code], criteria=[], match_all=True)


def codes(outcomes: list[reg.TestOutcome]) -> list[str]:
    return [o.code for o in outcomes]


def statuses(outcomes: list[reg.TestOutcome]) -> dict[str, str]:
    return {o.code: o.outcome for o in outcomes}


def detail(outcomes: list[reg.TestOutcome], code: str) -> str:
    return next(o.detail for o in outcomes if o.code == code)


# --- results ----------------------------------------------------------------


def test_a_passing_row_produces_no_failures(fresh_registry: None) -> None:
    make_test("PASSES", passes=True)
    assert reg.validate_row(ROW) == []


def test_a_failure_carries_code_message_status_and_comments(fresh_registry: None) -> None:
    make_test("FAILS", passes=False, status=Status.MALFORMED, comments={"actual": 7})
    outcome = reg.validate_row(ROW)[0]
    assert outcome.code == "FAILS"
    assert outcome.message == "FAILS failed"
    assert outcome.status == Status.MALFORMED
    assert outcome.status_label == "MALFORMED (2)"
    assert dict(outcome.comments) == {"actual": 7}


def test_failures_come_back_in_evaluation_order(fresh_registry: None) -> None:
    make_test("SECOND", passes=False, depends_on=["FIRST"])
    make_test("FIRST", passes=False)
    assert codes(reg.validate_row(ROW)) == ["FIRST"]


def test_several_failures_are_all_reported(fresh_registry: None) -> None:
    make_test("ONE", passes=False)
    make_test("TWO", passes=False)
    assert sorted(codes(reg.validate_row(ROW))) == ["ONE", "TWO"]


# --- what a test receives and may return ------------------------------------


def test_a_one_argument_test_receives_the_row(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_test(code="ONE_ARG", message="m")
    def check(row: "pd.Series[Any]") -> TestResult:
        seen.append(row)
        return PASS

    reg.validate_row(ROW)
    assert seen[0]["email"] == "a@b.com"


def test_a_two_argument_test_receives_the_context(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_test(code="TWO_ARG", message="m")
    def check(row: "pd.Series[Any]", ctx: RowContext | None) -> TestResult:
        seen.append(ctx)
        return PASS

    context = RowContext(flags={"legacy": True})
    reg.validate_row(ROW, ctx=context)
    assert seen == [context]


def test_ctx_defaults_to_none(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_test(code="NO_CTX", message="m")
    def check(row: "pd.Series[Any]", ctx: RowContext | None) -> TestResult:
        seen.append(ctx)
        return PASS

    reg.validate_row(ROW)
    assert seen == [None]


@pytest.mark.parametrize(
    "arguments",
    [pytest.param("", id="none"), pytest.param("row, ctx, extra", id="three")],
)
def test_a_signature_the_engine_cannot_call_is_rejected_at_registration(
    fresh_registry: None, arguments: str
) -> None:
    namespace: dict[str, Any] = {}
    exec(f"def check({arguments}):\n    return True", namespace)
    with pytest.raises(ValueError, match="must take \\(row\\) or \\(row, ctx\\)"):
        reg.register_test(code="BAD_SIGNATURE", message="m")(namespace["check"])


def test_a_starargs_test_is_accepted(fresh_registry: None) -> None:
    @reg.register_test(code="STAR", message="m")
    def check(*args: Any) -> TestResult:
        return PASS

    assert reg.validate_row(ROW) == []


def test_returning_true_passes_and_false_fails_as_invalid(fresh_registry: None) -> None:
    @reg.register_test(code="BOOLEAN", message="m")
    def check(row: "pd.Series[Any]") -> bool:
        return False

    outcome = reg.validate_row(ROW)[0]
    assert outcome.status == Status.INVALID


def test_returning_a_bare_status_fails_with_it(fresh_registry: None) -> None:
    @reg.register_test(code="BARE", message="m")
    def check(row: "pd.Series[Any]") -> Status:
        return Status.MISSING

    assert reg.validate_row(ROW)[0].status == Status.MISSING


def test_validate_row_does_not_mutate_the_row_or_the_context(fresh_registry: None) -> None:
    make_test("PASSES")
    row = ROW.copy()
    context = RowContext(flags={"legacy": False})
    reg.validate_row(row, ctx=context)
    assert row.equals(ROW)
    assert context == RowContext(flags={"legacy": False})


# --- enabled state ----------------------------------------------------------


def test_a_test_off_by_default_does_not_run(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("OFF", passes=False, default_enabled=False, calls=calls)
    assert reg.validate_row(ROW) == []
    assert calls == []


def test_an_override_can_enable_an_off_by_default_test(fresh_registry: None) -> None:
    make_test("OFF", passes=False, default_enabled=False)
    assert codes(reg.validate_row(ROW, overrides=[enable("OFF")])) == ["OFF"]


def test_an_override_can_disable_an_on_by_default_test(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("ON", passes=False, calls=calls)
    assert reg.validate_row(ROW, overrides=[disable("ON")]) == []
    assert calls == []


def test_an_override_applies_only_to_matching_rows(fresh_registry: None) -> None:
    make_test("ON", passes=False)
    only_internal = reg.OverrideRule(
        name="internal", action="disable", codes=["ON"],
        criteria=[reg.MatchCriterion("email", "@internal", re.compile("@internal"))],
        match_all=False,
    )
    assert codes(reg.validate_row(ROW, overrides=[only_internal])) == ["ON"]
    internal_row = pd.Series({"age": 30, "email": "qa@internal.test"})
    assert reg.validate_row(internal_row, overrides=[only_internal]) == []


# --- explanations -----------------------------------------------------------


def test_explain_row_reports_every_registered_test(fresh_registry: None) -> None:
    make_test("ONE")
    make_test("TWO", passes=False)
    assert statuses(reg.explain_row(ROW)) == {"ONE": PASSED, "TWO": FAILED}


def test_a_test_off_by_default_says_so(fresh_registry: None) -> None:
    make_test("OFF", default_enabled=False)
    assert detail(reg.explain_row(ROW), "OFF") == "disabled by off by default"


def test_a_test_disabled_by_a_rule_names_the_rule(fresh_registry: None) -> None:
    make_test("ON")
    outcomes = reg.explain_row(ROW, overrides=[disable("ON", name="suppress_for_test_accounts")])
    assert detail(outcomes, "ON") == "disabled by rule 'suppress_for_test_accounts'"


def test_the_last_matching_rule_is_the_one_named(fresh_registry: None) -> None:
    make_test("CODE")
    rules = [disable("CODE", name="first"), disable("CODE", name="second")]
    assert detail(reg.explain_row(ROW, overrides=rules), "CODE") == "disabled by rule 'second'"


def test_validate_row_and_explain_row_agree_on_failures(example_suites: None) -> None:
    row = pd.Series({"age": -5, "email": "nope"})
    failed = [o.code for o in reg.explain_row(row) if o.failed]
    assert codes(reg.validate_row(row)) == failed


def test_on_error_must_be_one_of_two_values(fresh_registry: None) -> None:
    make_test("CODE")
    with pytest.raises(ValueError, match="on_error must be 'record' or 'raise'"):
        reg.explain_row(ROW, on_error="ignore")


# --- dependencies -----------------------------------------------------------


def test_a_dependent_runs_when_its_prerequisite_passes(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("PREREQ", passes=True, calls=calls)
    make_test("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    assert codes(reg.validate_row(ROW)) == ["DEPENDENT"]
    assert calls == ["PREREQ", "DEPENDENT"]


def test_a_dependent_is_not_run_when_its_prerequisite_fails(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("PREREQ", passes=False, calls=calls)
    make_test("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    outcomes = reg.explain_row(ROW)
    assert statuses(outcomes)["DEPENDENT"] == SKIPPED
    assert detail(outcomes, "DEPENDENT") == "prerequisite did not pass: PREREQ"
    assert calls == ["PREREQ"]


def test_a_dependent_is_not_run_when_its_prerequisite_is_disabled(fresh_registry: None) -> None:
    """A disabled prerequisite confirmed nothing, so it must not unlock anything."""

    calls: list[str] = []
    make_test("PREREQ", passes=True, default_enabled=False, calls=calls)
    make_test("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    assert reg.validate_row(ROW) == []
    assert calls == []


def test_a_dependent_is_not_run_when_its_prerequisite_errored(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("PREREQ", raises=RuntimeError("boom"), calls=calls)
    make_test("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    outcomes = reg.explain_row(ROW)
    assert statuses(outcomes) == {"PREREQ": ERRORED, "DEPENDENT": SKIPPED}
    assert calls == ["PREREQ"]


def test_every_prerequisite_must_pass_and_all_blockers_are_named(fresh_registry: None) -> None:
    make_test("GOOD", passes=True)
    make_test("BAD", passes=False)
    make_test("ALSO_BAD", passes=False)
    make_test("DEPENDENT", passes=False, depends_on=["GOOD", "BAD", "ALSO_BAD"])
    outcomes = reg.explain_row(ROW)
    assert statuses(outcomes)["DEPENDENT"] == SKIPPED
    assert detail(outcomes, "DEPENDENT") == "prerequisite did not pass: BAD, ALSO_BAD"


def test_skipping_propagates_transitively(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("ROOT", passes=False, calls=calls)
    make_test("MIDDLE", passes=True, depends_on=["ROOT"], calls=calls)
    make_test("LEAF", passes=False, depends_on=["MIDDLE"], calls=calls)
    assert codes(reg.validate_row(ROW)) == ["ROOT"]
    assert calls == ["ROOT"]


def test_a_disabled_dependent_is_skipped_even_when_its_prerequisite_passes(
    fresh_registry: None,
) -> None:
    make_test("PREREQ", passes=True)
    make_test("DEPENDENT", passes=False, default_enabled=False, depends_on=["PREREQ"])
    assert reg.validate_row(ROW) == []


def test_sibling_dependents_are_independent(fresh_registry: None) -> None:
    make_test("PREREQ", passes=True)
    make_test("LEFT", passes=False, depends_on=["PREREQ"])
    make_test("RIGHT", passes=True, depends_on=["PREREQ"])
    assert codes(reg.validate_row(ROW)) == ["LEFT"]


def test_registration_order_does_not_have_to_match_dependency_order(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("DEPENDENT", passes=True, depends_on=["PREREQ"], calls=calls)
    make_test("PREREQ", passes=True, calls=calls)
    assert reg.validate_row(ROW) == []
    assert calls == ["PREREQ", "DEPENDENT"]


# --- root cause -------------------------------------------------------------


def test_root_cause_is_the_first_failure_in_dependency_order(fresh_registry: None) -> None:
    make_test("DEEP", passes=False, depends_on=["SHALLOW"])
    make_test("SHALLOW", passes=False)
    results = reg.validate_row(ROW)
    assert codes(results) == ["SHALLOW"]
    assert reg.root_cause(results) == "SHALLOW"


def test_root_cause_of_a_clean_row_is_none(fresh_registry: None) -> None:
    make_test("PASSES")
    assert reg.root_cause(reg.validate_row(ROW)) is None
    assert reg.root_cause(reg.explain_row(ROW)) is None


def test_root_cause_ignores_disabled_and_skipped_outcomes(fresh_registry: None) -> None:
    make_test("DISABLED_ONE", default_enabled=False)
    make_test("FAILS", passes=False)
    assert reg.root_cause(reg.explain_row(ROW)) == "FAILS"


def test_an_errored_test_can_be_the_root_cause(fresh_registry: None) -> None:
    make_test("BROKEN", raises=RuntimeError("boom"))
    assert reg.root_cause(reg.explain_row(ROW)) == "BROKEN"


# --- layers -----------------------------------------------------------------


def test_layer_is_zero_without_prerequisites(fresh_registry: None) -> None:
    make_test("ROOT")
    reg.validate_registry()
    assert reg.TESTS[0].layer == 0


def test_layer_counts_the_deepest_chain(fresh_registry: None) -> None:
    make_test("L0")
    make_test("L1", depends_on=["L0"])
    make_test("L2", depends_on=["L1"])
    make_test("WIDE", depends_on=["L0", "L2"])
    reg.validate_registry()
    assert {t.code: t.layer for t in reg.TESTS} == {"L0": 0, "L1": 1, "L2": 2, "WIDE": 3}


def test_outcomes_carry_the_layer_and_suite(fresh_registry: None) -> None:
    make_test("ROOT")
    make_test("LEAF", depends_on=["ROOT"])
    layers = {o.code: (o.layer, o.suite) for o in reg.explain_row(ROW)}
    assert layers == {"ROOT": (0, "base"), "LEAF": (1, "base")}


# --- duplicate labels -------------------------------------------------------


def test_duplicate_labels_raise_before_any_test_runs(fresh_registry: None) -> None:
    calls: list[str] = []
    make_test("CODE", calls=calls)
    with pytest.raises(ValueError, match=r"duplicate column labels \['age'\]"):
        reg.explain_row(pd.Series([1, 2], index=["age", "age"]))
    assert calls == []


# --- the shipped example tests ---------------------------------------------


@pytest.mark.parametrize(
    "row, expected",
    [
        pytest.param({"age": 34, "email": "a@example.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, [], id="clean"),
        pytest.param({"age": -5, "email": "a@example.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["AGE_NEGATIVE"], id="negative-age"),
        pytest.param({"age": 200, "email": "a@example.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["AGE_TOO_HIGH"], id="age-too-high"),
        pytest.param({"age": 130, "email": "a@example.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, [], id="age-at-the-limit"),
        pytest.param({"age": "abc", "email": "a@example.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["AGE_NOT_A_NUMBER"], id="age-not-a-number"),
        pytest.param({"age": 30, "email": "nope", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["EMAIL_MISSING_AT"], id="no-at-sign"),
        pytest.param({"age": 30, "email": "a@nodot", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["EMAIL_DOMAIN_INVALID"], id="domain-without-a-dot"),
        pytest.param({"age": 30, "email": "a@b.com", "start_date": "2024-05-01",
                      "end_date": "2024-03-01"}, ["DATES_OUT_OF_ORDER"], id="dates-reversed"),
        pytest.param({"age": None, "email": "a@b.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["AGE_PRESENT"], id="missing-age"),
    ],
)
def test_example_tests_report_the_expected_codes(
    example_suites: None, row: dict[str, Any], expected: list[str]
) -> None:
    assert codes(reg.validate_row(pd.Series(row))) == expected


def test_a_missing_field_reports_once_not_from_every_test_that_reads_it(
    example_suites: None,
) -> None:
    """The whole point of layering: one complaint about a blank age."""

    row = pd.Series({"age": None, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    outcomes = reg.explain_row(row)
    assert codes(reg.validate_row(row)) == ["AGE_PRESENT"]
    assert statuses(outcomes)["AGE_NOT_A_NUMBER"] == SKIPPED
    assert statuses(outcomes)["AGE_NEGATIVE"] == SKIPPED


def test_failure_comments_carry_the_numbers_a_reader_needs(example_suites: None) -> None:
    row = pd.Series({"age": 200, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    outcome = reg.validate_row(row)[0]
    assert dict(outcome.comments) == {"value": 200.0, "maximum": 130}


def test_the_off_by_default_integer_test_once_enabled(example_suites: None) -> None:
    row = pd.Series({"age": 41.5, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    assert codes(reg.validate_row(row)) == []
    assert codes(reg.validate_row(row, overrides=[enable("AGE_NOT_INTEGER")])) == ["AGE_NOT_INTEGER"]


def test_disabling_a_presence_test_hides_everything_below_it(example_suites: None) -> None:
    row = pd.Series({"age": None, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    assert codes(reg.validate_row(row, overrides=[disable("AGE_PRESENT")])) == []


# --- rule columns -----------------------------------------------------------


def test_check_rule_columns_is_quiet_when_every_criterion_column_is_present(
    fresh_registry: None,
) -> None:
    make_test("CODE")
    rule = reg.OverrideRule(
        name="on_age", action="disable", codes=["CODE"],
        criteria=[reg.MatchCriterion("age", "^1$", re.compile("^1$"))], match_all=False,
    )
    assert reg.check_rule_columns(pd.DataFrame({"age": [1]}), [rule]) == []


def test_check_rule_columns_warns_about_a_column_the_data_lacks(fresh_registry: None) -> None:
    """A criterion on a missing column never matches, so the rule silently never fires."""

    make_test("CODE")
    rule = reg.OverrideRule(
        name="legacy_only", action="disable", codes=["CODE"],
        criteria=[reg.MatchCriterion("source_sytem", "^LEGACY", re.compile("^LEGACY"))],
        match_all=False,
    )
    assert reg.check_rule_columns(pd.DataFrame({"age": [1]}), [rule]) == [
        "rule 'legacy_only' matches on column 'source_sytem', which is not in the data: "
        "the rule will never apply"
    ]


def test_check_rule_columns_ignores_a_match_all_rule(fresh_registry: None) -> None:
    make_test("CODE")
    assert reg.check_rule_columns(pd.DataFrame({"age": [1]}), [disable("CODE")]) == []


# --- example test helpers at their edges ------------------------------------


@pytest.mark.parametrize(
    "row, expected",
    [
        pytest.param({"age": [1, 2], "email": "a@b.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["AGE_NOT_A_NUMBER"], id="age-is-a-list"),
        pytest.param({"email": "a@b.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["AGE_PRESENT"], id="no-age-column"),
        pytest.param({"age": 41.0, "email": "a@b.com", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, [], id="whole-float-age"),
        pytest.param({"age": 30, "email": "a@b.com", "start_date": "not-a-date",
                      "end_date": "2024-02-01"}, ["DATES_PRESENT"], id="unparseable-date"),
        pytest.param({"age": 30, "email": "   ", "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["EMAIL_PRESENT"], id="blank-email"),
        pytest.param({"age": 30, "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["EMAIL_PRESENT"], id="no-email-column"),
        pytest.param({"age": 30, "email": None, "start_date": "2024-01-01",
                      "end_date": "2024-02-01"}, ["EMAIL_PRESENT"], id="null-email"),
        pytest.param({"age": 30, "email": "a@b.com", "start_date": None,
                      "end_date": "2024-02-01"}, ["DATES_PRESENT"], id="null-start-date"),
        pytest.param({"age": 30, "email": "a@b.com", "end_date": "2024-02-01"},
                     ["DATES_PRESENT"], id="no-start-date-column"),
    ],
)
def test_example_tests_handle_edge_values(
    example_suites: None, row: dict[str, Any], expected: list[str]
) -> None:
    assert codes(reg.validate_row(pd.Series(row))) == expected


def test_the_integer_test_passes_a_whole_number_once_enabled(example_suites: None) -> None:
    row = pd.Series({"age": 41.0, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    assert codes(reg.validate_row(row, overrides=[enable("AGE_NOT_INTEGER")])) == []
