"""Unit checks: the per-row algorithm, its outcomes, and dependency skipping."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import pytest

from conftest import first_cause, make_check
from jobcheck import RowContext, registry as reg
from jobcheck import results as res
from jobcheck.results import ERRORED, FAILED, PASS, PASSED, SKIPPED, Status, CheckResult
from jobcheck import engine
from jobcheck import rules

pytestmark = pytest.mark.fast

ROW = pd.Series({"age": 30, "email": "a@b.com"})


def disable(code: str, name: str = "kill_it") -> reg.OverrideRule:
    return reg.OverrideRule(name=name, action="disable", codes=[code], criteria=[], match_all=True, message="why the rule exists")


def enable(code: str, name: str = "switch_on") -> reg.OverrideRule:
    return reg.OverrideRule(name=name, action="enable", codes=[code], criteria=[], match_all=True, message="why the rule exists")


def codes(outcomes: list[res.CheckOutcome]) -> list[str]:
    return [o.code for o in outcomes]


def statuses(outcomes: list[res.CheckOutcome]) -> dict[str, str]:
    return {o.code: o.outcome for o in outcomes}


def detail(outcomes: list[res.CheckOutcome], code: str) -> str:
    return next(o.detail for o in outcomes if o.code == code)


# --- results ----------------------------------------------------------------


def test_a_passing_row_produces_no_failures(fresh_registry: None) -> None:
    make_check("PASSES", passes=True)
    assert engine.validate_row(ROW) == []


def test_a_failure_carries_code_message_status_and_comments(fresh_registry: None) -> None:
    make_check("FAILS", passes=False, status=Status.MALFORMED, comments={"actual": 7})
    outcome = engine.validate_row(ROW)[0]
    assert outcome.code == "FAILS"
    assert outcome.message == "FAILS failed"
    assert outcome.status == Status.MALFORMED
    assert outcome.status_label == "MALFORMED (2)"
    assert dict(outcome.comments) == {"actual": 7}


def test_failures_come_back_in_evaluation_order(fresh_registry: None) -> None:
    make_check("SECOND", passes=False, depends_on=["FIRST"])
    make_check("FIRST", passes=False)
    assert codes(engine.validate_row(ROW)) == ["FIRST"]


def test_several_failures_are_all_reported(fresh_registry: None) -> None:
    make_check("ONE", passes=False)
    make_check("TWO", passes=False)
    assert sorted(codes(engine.validate_row(ROW))) == ["ONE", "TWO"]


# --- what a check receives and may return ------------------------------------


def test_a_one_argument_test_receives_the_row(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_check(code="ONE_ARG", message="m")
    def check(row: "pd.Series[Any]") -> CheckResult:
        seen.append(row)
        return PASS

    engine.validate_row(ROW)
    assert seen[0]["email"] == "a@b.com"


def test_a_two_argument_test_receives_the_context(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_check(code="TWO_ARG", message="m")
    def check(row: "pd.Series[Any]", ctx: RowContext | None) -> CheckResult:
        seen.append(ctx)
        return PASS

    context = RowContext()
    engine.validate_row(ROW, context=context)
    assert seen == [context]


def test_ctx_defaults_to_none(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_check(code="NO_CTX", message="m")
    def check(row: "pd.Series[Any]", ctx: RowContext | None) -> CheckResult:
        seen.append(ctx)
        return PASS

    engine.validate_row(ROW)
    assert seen == [None]


@pytest.mark.parametrize(
    "arguments",
    [pytest.param("", id="none"), pytest.param("row, context, extra", id="three")],
)
def test_a_signature_the_engine_cannot_call_is_rejected_at_registration(
    fresh_registry: None, arguments: str
) -> None:
    namespace: dict[str, Any] = {}
    exec(f"def check({arguments}):\n    return True", namespace)
    with pytest.raises(ValueError, match=r"must take \(row\) or \(row, context\)"):
        reg.register_check(code="BAD_SIGNATURE", message="m")(namespace["check"])


def test_a_starargs_test_is_accepted(fresh_registry: None) -> None:
    @reg.register_check(code="STAR", message="m")
    def check(*args: Any) -> CheckResult:
        return PASS

    assert engine.validate_row(ROW) == []


def test_a_condition_wrapped_in_a_result_fails_as_invalid(fresh_registry: None) -> None:
    @reg.register_check(code="BOOLEAN", message="m")
    def check(row: "pd.Series[Any]") -> CheckResult:
        return CheckResult(1 < 0)

    outcome = engine.validate_row(ROW)[0]
    assert outcome.status == Status.INVALID


def test_a_named_status_fails_with_it(fresh_registry: None) -> None:
    @reg.register_check(code="BARE", message="m")
    def check(row: "pd.Series[Any]") -> CheckResult:
        return CheckResult(Status.MISSING)

    assert engine.validate_row(ROW)[0].status == Status.MISSING


def test_validate_row_does_not_mutate_the_row_or_the_context(fresh_registry: None) -> None:
    make_check("PASSES")
    row = ROW.copy()
    context = RowContext()
    engine.validate_row(row, context=context)
    assert row.equals(ROW)
    assert context == RowContext()


# --- enabled state ----------------------------------------------------------


def test_a_test_off_by_default_does_not_run(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("OFF", passes=False, default_enabled=False, calls=calls)
    assert engine.validate_row(ROW) == []
    assert calls == []


def test_an_override_can_enable_an_off_by_default_test(fresh_registry: None) -> None:
    make_check("OFF", passes=False, default_enabled=False)
    assert codes(engine.validate_row(ROW, overrides=[enable("OFF")])) == ["OFF"]


def test_an_override_can_disable_an_on_by_default_test(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("ON", passes=False, calls=calls)
    assert engine.validate_row(ROW, overrides=[disable("ON")]) == []
    assert calls == []


def test_an_override_applies_only_to_matching_rows(fresh_registry: None) -> None:
    make_check("ON", passes=False)
    only_internal = reg.OverrideRule(
        name="internal", action="disable", codes=["ON"],
        criteria=[reg.MatchCriterion("email", "@internal", re.compile("@internal"))],
        match_all=False, message="why the rule exists")
    assert codes(engine.validate_row(ROW, overrides=[only_internal])) == ["ON"]
    internal_row = pd.Series({"age": 30, "email": "qa@internal.test"})
    assert engine.validate_row(internal_row, overrides=[only_internal]) == []


# --- explanations -----------------------------------------------------------


def test_explain_row_reports_every_registered_test(fresh_registry: None) -> None:
    make_check("ONE")
    make_check("TWO", passes=False)
    assert statuses(engine.explain_row(ROW)) == {"ONE": PASSED, "TWO": FAILED}


def test_a_test_off_by_default_says_so(fresh_registry: None) -> None:
    make_check("OFF", default_enabled=False)
    assert detail(engine.explain_row(ROW), "OFF") == "disabled by off by default"


def test_a_test_disabled_by_a_rule_names_the_rule(fresh_registry: None) -> None:
    make_check("ON")
    outcomes = engine.explain_row(ROW, overrides=[disable("ON", name="suppress_for_test_accounts")])
    assert detail(outcomes, "ON") == "disabled by rule 'suppress_for_test_accounts'"


def test_the_last_matching_rule_is_the_one_named(fresh_registry: None) -> None:
    make_check("CODE")
    rules = [disable("CODE", name="first"), disable("CODE", name="second")]
    assert detail(engine.explain_row(ROW, overrides=rules), "CODE") == "disabled by rule 'second'"


def test_validate_row_and_explain_row_agree_on_failures(example_checks: None) -> None:
    row = pd.Series({"age": -5, "email": "nope"})
    failed = [o.code for o in engine.explain_row(row) if o.failed]
    assert codes(engine.validate_row(row)) == failed


def test_on_error_must_be_one_of_two_values(fresh_registry: None) -> None:
    make_check("CODE")
    with pytest.raises(ValueError, match="on_error must be 'record' or 'raise'"):
        engine.explain_row(ROW, on_error="ignore")


# --- dependencies -----------------------------------------------------------


def test_a_dependent_runs_when_its_prerequisite_passes(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("PREREQ", passes=True, calls=calls)
    make_check("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    assert codes(engine.validate_row(ROW)) == ["DEPENDENT"]
    assert calls == ["PREREQ", "DEPENDENT"]


def test_a_dependent_is_not_run_when_its_prerequisite_fails(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("PREREQ", passes=False, calls=calls)
    make_check("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    outcomes = engine.explain_row(ROW)
    assert statuses(outcomes)["DEPENDENT"] == SKIPPED
    assert detail(outcomes, "DEPENDENT") == "prerequisite did not pass: PREREQ"
    assert calls == ["PREREQ"]


def test_a_dependent_is_not_run_when_its_prerequisite_is_disabled(fresh_registry: None) -> None:
    """A disabled prerequisite confirmed nothing, so it must not unlock anything."""

    calls: list[str] = []
    make_check("PREREQ", passes=True, default_enabled=False, calls=calls)
    make_check("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    assert engine.validate_row(ROW) == []
    assert calls == []


def test_a_dependent_is_not_run_when_its_prerequisite_errored(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("PREREQ", raises=RuntimeError("boom"), calls=calls)
    make_check("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    outcomes = engine.explain_row(ROW)
    assert statuses(outcomes) == {"PREREQ": ERRORED, "DEPENDENT": SKIPPED}
    assert calls == ["PREREQ"]


def test_every_prerequisite_must_pass_and_all_blockers_are_named(fresh_registry: None) -> None:
    make_check("GOOD", passes=True)
    make_check("BAD", passes=False)
    make_check("ALSO_BAD", passes=False)
    make_check("DEPENDENT", passes=False, depends_on=["GOOD", "BAD", "ALSO_BAD"])
    outcomes = engine.explain_row(ROW)
    assert statuses(outcomes)["DEPENDENT"] == SKIPPED
    assert detail(outcomes, "DEPENDENT") == "prerequisite did not pass: BAD, ALSO_BAD"


def test_skipping_propagates_transitively(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("ROOT", passes=False, calls=calls)
    make_check("MIDDLE", passes=True, depends_on=["ROOT"], calls=calls)
    make_check("LEAF", passes=False, depends_on=["MIDDLE"], calls=calls)
    assert codes(engine.validate_row(ROW)) == ["ROOT"]
    assert calls == ["ROOT"]


def test_a_disabled_dependent_is_skipped_even_when_its_prerequisite_passes(
    fresh_registry: None,
) -> None:
    make_check("PREREQ", passes=True)
    make_check("DEPENDENT", passes=False, default_enabled=False, depends_on=["PREREQ"])
    assert engine.validate_row(ROW) == []


def test_sibling_dependents_are_independent(fresh_registry: None) -> None:
    make_check("PREREQ", passes=True)
    make_check("LEFT", passes=False, depends_on=["PREREQ"])
    make_check("RIGHT", passes=True, depends_on=["PREREQ"])
    assert codes(engine.validate_row(ROW)) == ["LEFT"]


def test_registration_order_does_not_have_to_match_dependency_order(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("DEPENDENT", passes=True, depends_on=["PREREQ"], calls=calls)
    make_check("PREREQ", passes=True, calls=calls)
    assert engine.validate_row(ROW) == []
    assert calls == ["PREREQ", "DEPENDENT"]


# --- root cause -------------------------------------------------------------


def test_root_cause_is_the_first_failure_in_dependency_order(fresh_registry: None) -> None:
    make_check("DEEP", passes=False, depends_on=["SHALLOW"])
    make_check("SHALLOW", passes=False)
    results = engine.validate_row(ROW)
    assert codes(results) == ["SHALLOW"]
    assert first_cause(results) == "SHALLOW"


def test_root_cause_of_a_clean_row_is_none(fresh_registry: None) -> None:
    make_check("PASSES")
    assert first_cause(engine.validate_row(ROW)) is None
    assert first_cause(engine.explain_row(ROW)) is None


def test_root_cause_ignores_disabled_and_skipped_outcomes(fresh_registry: None) -> None:
    make_check("DISABLED_ONE", default_enabled=False)
    make_check("FAILS", passes=False)
    assert first_cause(engine.explain_row(ROW)) == "FAILS"


def test_an_errored_outcome_carries_the_layer_and_the_message(fresh_registry: None) -> None:
    """An errored outcome is a reportable failure like any other, so it has to
    carry what the report and the root-cause rule read: its layer, and the
    check's message. Mutation found only its `detail` under test, and a check
    that raised at the wrong layer changes which code a row reports as its cause.
    """

    make_check("BASE")
    make_check("RAISES", depends_on=["BASE"], raises=RuntimeError("boom"))
    outcome = next(o for o in engine.explain_row(ROW) if o.code == "RAISES")
    assert outcome.outcome == ERRORED
    assert outcome.layer == 1
    assert outcome.message == "RAISES failed"
    assert outcome.status == Status.ERROR
    assert outcome.detail == "RuntimeError: boom"


def test_an_errored_test_can_be_the_root_cause(fresh_registry: None) -> None:
    make_check("BROKEN", raises=RuntimeError("boom"))
    assert first_cause(engine.explain_row(ROW)) == "BROKEN"


# --- layers -----------------------------------------------------------------


def test_layer_is_zero_without_prerequisites(fresh_registry: None) -> None:
    make_check("ROOT")
    reg.validate_registry()
    assert reg.CHECKS[0].layer == 0


def test_layer_counts_the_deepest_chain(fresh_registry: None) -> None:
    make_check("L0")
    make_check("L1", depends_on=["L0"])
    make_check("L2", depends_on=["L1"])
    make_check("WIDE", depends_on=["L0", "L2"])
    reg.validate_registry()
    assert {t.code: t.layer for t in reg.CHECKS} == {"L0": 0, "L1": 1, "L2": 2, "WIDE": 3}


def test_outcomes_carry_the_layer(fresh_registry: None) -> None:
    make_check("ROOT")
    make_check("LEAF", depends_on=["ROOT"])
    layers = {o.code: o.layer for o in engine.explain_row(ROW)}
    assert layers == {"ROOT": 0, "LEAF": 1}


# --- duplicate labels -------------------------------------------------------


def test_duplicate_labels_raise_before_any_test_runs(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("CODE", calls=calls)
    with pytest.raises(ValueError, match=r"duplicate column labels \['age'\]"):
        engine.explain_row(pd.Series([1, 2], index=["age", "age"]))
    assert calls == []


# --- the shipped example checks ---------------------------------------------


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
    example_checks: None, row: dict[str, Any], expected: list[str]
) -> None:
    assert codes(engine.validate_row(pd.Series(row))) == expected


def test_a_missing_field_reports_once_not_from_every_test_that_reads_it(
    example_checks: None,
) -> None:
    """The whole point of layering: one complaint about a blank age."""

    row = pd.Series({"age": None, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    outcomes = engine.explain_row(row)
    assert codes(engine.validate_row(row)) == ["AGE_PRESENT"]
    assert statuses(outcomes)["AGE_NOT_A_NUMBER"] == SKIPPED
    assert statuses(outcomes)["AGE_NEGATIVE"] == SKIPPED


def test_failure_comments_carry_the_numbers_a_reader_needs(example_checks: None) -> None:
    row = pd.Series({"age": 200, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    outcome = engine.validate_row(row)[0]
    assert dict(outcome.comments) == {"value": 200.0, "maximum": 130}


def test_the_off_by_default_integer_test_once_enabled(example_checks: None) -> None:
    row = pd.Series({"age": 41.5, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    assert codes(engine.validate_row(row)) == []
    assert codes(engine.validate_row(row, overrides=[enable("AGE_NOT_INTEGER")])) == ["AGE_NOT_INTEGER"]


def test_disabling_a_presence_test_hides_everything_below_it(example_checks: None) -> None:
    row = pd.Series({"age": None, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    assert codes(engine.validate_row(row, overrides=[disable("AGE_PRESENT")])) == []


# --- rule columns -----------------------------------------------------------


def test_check_rule_columns_is_quiet_when_every_criterion_column_is_present(
    fresh_registry: None,
) -> None:
    make_check("CODE")
    rule = reg.OverrideRule(
        name="on_age", action="disable", codes=["CODE"],
        criteria=[reg.MatchCriterion("age", "^1$", re.compile("^1$"))], match_all=False, message="why the rule exists")
    assert rules.check_override_columns(pd.DataFrame({"age": [1]}), [rule]) == []


def test_check_rule_columns_warns_about_a_column_the_data_lacks(fresh_registry: None) -> None:
    """A criterion on a missing column never matches, so the rule silently never fires."""

    make_check("CODE")
    rule = reg.OverrideRule(
        name="legacy_only", action="disable", codes=["CODE"],
        criteria=[reg.MatchCriterion("source_sytem", "^LEGACY", re.compile("^LEGACY"))],
        match_all=False, message="why the rule exists")
    assert rules.check_override_columns(pd.DataFrame({"age": [1]}), [rule]) == [
        "rule 'legacy_only' matches on column 'source_sytem', which is not in the data: "
        "the rule will never apply"
    ]


def test_check_rule_columns_ignores_a_match_all_rule(fresh_registry: None) -> None:
    make_check("CODE")
    assert rules.check_override_columns(pd.DataFrame({"age": [1]}), [disable("CODE")]) == []


# --- example check helpers at their edges ------------------------------------


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
    example_checks: None, row: dict[str, Any], expected: list[str]
) -> None:
    assert codes(engine.validate_row(pd.Series(row))) == expected


def test_the_integer_test_passes_a_whole_number_once_enabled(example_checks: None) -> None:
    row = pd.Series({"age": 41.0, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    assert codes(engine.validate_row(row, overrides=[enable("AGE_NOT_INTEGER")])) == []


def test_a_child_blocked_by_a_disabled_parent_says_disabled(fresh_registry: None) -> None:
    """"Did not pass" reads as a failure; a chain switched off at its root is not one."""

    make_check("PARENT")
    make_check("CHILD", depends_on=["PARENT"])
    rule = reg.OverrideRule(name="off", action="disable", codes=["PARENT"], criteria=[],
                            match_all=True, source_file="<test>", message="why the rule exists")
    outcomes = engine.explain_row(pd.Series({"a": 1}), overrides=[rule])
    assert [(o.code, o.outcome, o.detail) for o in outcomes] == [
        ("PARENT", "disabled", "disabled by rule 'off'"),
        ("CHILD", "skipped", "prerequisite disabled: PARENT"),
    ]


def test_a_child_blocked_by_a_failing_parent_still_says_did_not_pass(
    fresh_registry: None,
) -> None:
    make_check("PARENT", passes=False)
    make_check("CHILD", depends_on=["PARENT"])
    outcomes = engine.explain_row(pd.Series({"a": 1}))
    assert outcomes[1].detail == "prerequisite did not pass: PARENT"


def test_a_mix_of_disabled_and_failed_prerequisites_says_did_not_pass(
    fresh_registry: None,
) -> None:
    """Only when *every* blocker was disabled is "disabled" the whole truth."""

    make_check("OFF")
    make_check("BROKEN", passes=False)
    make_check("CHILD", depends_on=["OFF", "BROKEN"])
    rule = reg.OverrideRule(name="off", action="disable", codes=["OFF"], criteria=[],
                            match_all=True, source_file="<test>", message="why the rule exists")
    outcomes = engine.explain_row(pd.Series({"a": 1}), overrides=[rule])
    assert outcomes[-1].detail == "prerequisite did not pass: OFF, BROKEN"


def test_root_causes_returns_every_failure_at_the_shallowest_layer(
    fresh_registry: None,
) -> None:
    make_check("A", passes=False)
    make_check("B", passes=False)
    make_check("DEEPER", passes=False, depends_on=[])
    outcomes = engine.explain_row(pd.Series({"a": 1}))
    assert engine.root_causes(outcomes) == ["A", "B", "DEEPER"]


def test_root_causes_excludes_a_downstream_failure(fresh_registry: None) -> None:
    make_check("PARENT")
    make_check("SHALLOW", passes=False)
    make_check("CHILD", passes=False, depends_on=["PARENT"])
    outcomes = engine.explain_row(pd.Series({"a": 1}))
    assert engine.root_causes(outcomes) == ["SHALLOW"]


def test_root_causes_is_empty_for_a_row_that_passed(fresh_registry: None) -> None:
    make_check("PASSES")
    assert engine.root_causes(engine.explain_row(pd.Series({"a": 1}))) == []


def test_root_cause_returns_one_of_the_root_causes(fresh_registry: None) -> None:
    make_check("A", passes=False)
    make_check("B", passes=False)
    outcomes = engine.explain_row(pd.Series({"a": 1}))
    assert first_cause(outcomes) in engine.root_causes(outcomes)
