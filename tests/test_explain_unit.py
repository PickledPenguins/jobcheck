"""Unit checks: the per-row algorithm, its outcomes, and dependency skipping."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import pytest

from conftest import failures, first_cause, make_check
from jobcheck import RowContext, registry as reg
from jobcheck import results as res
from jobcheck.results import OK, Status, Verdict, Outcome
from jobcheck import engine
from jobcheck.views import _root_causes
from jobcheck import rules
from jobcheck.rules import _MatchCriterion

pytestmark = pytest.mark.fast

ROW = pd.Series({"age": 30, "email": "a@b.com"})


def disable(code: str, name: str = "kill_it") -> reg.Rule:
    return reg.Rule(name=name, action="disable", codes=[code], criteria=[], match_all=True, message="why the rule exists")


def enable(code: str, name: str = "switch_on") -> reg.Rule:
    return reg.Rule(name=name, action="enable", codes=[code], criteria=[], match_all=True, message="why the rule exists")


def codes(outcomes: list[res.CheckOutcome]) -> list[str]:
    return [o.code for o in outcomes]


def statuses(outcomes: list[res.CheckOutcome]) -> dict[str, str]:
    return {o.code: o.outcome for o in outcomes}


def detail(outcomes: list[res.CheckOutcome], code: str) -> str:
    return next(o.detail for o in outcomes if o.code == code)


# --- results ----------------------------------------------------------------


def test_a_failure_carries_code_message_status_and_comments(fresh_registry: None) -> None:
    make_check("FAILS", passes=False, status=Status.MALFORMED, comments={"actual": 7})
    outcome = failures(ROW)[0]
    assert outcome.code == "FAILS"
    assert outcome.message == "FAILS failed"
    assert outcome.status == Status.MALFORMED
    assert outcome.status_label == "MALFORMED (2)"
    assert dict(outcome.comments) == {"actual": 7}


# --- what a check receives and may return ------------------------------------


def test_a_one_argument_check_receives_the_row(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_check(code="ONE_ARG", message="m")
    def check(row: "pd.Series[Any]") -> Verdict:
        seen.append(row)
        return OK

    failures(ROW)
    assert seen[0]["email"] == "a@b.com"


def test_a_two_argument_check_receives_the_context(fresh_registry: None) -> None:
    seen: list[Any] = []

    @reg.register_check(code="TWO_ARG", message="m")
    def check(row: "pd.Series[Any]", ctx: RowContext | None) -> Verdict:
        seen.append(ctx)
        return OK

    context = RowContext()
    failures(ROW, context=context)
    # `is`, not `==`: every bare context is equal, so the empty default would pass.
    assert seen[0] is context


def test_an_unnamed_context_is_an_empty_one_not_none(fresh_registry: None) -> None:
    """The per-row calls hand what `validate` hands: a check taking
    ``(row, context)`` sees a ``RowContext`` whichever entry point ran it."""

    seen: list[Any] = []

    @reg.register_check(code="NO_CTX", message="m")
    def check(row: "pd.Series[Any]", ctx: RowContext | None) -> Verdict:
        seen.append(ctx)
        return OK

    failures(ROW)
    engine._explain(ROW)
    engine._explain(ROW, context=None)
    assert seen == [RowContext(), RowContext(), RowContext()]
    assert all(isinstance(ctx, RowContext) for ctx in seen)


def test_a_check_taking_no_arguments_is_rejected_at_registration(
    fresh_registry: None,
) -> None:
    with pytest.raises(ValueError, match=r"must take \(row\) or \(row, context\)"):
        @reg.register_check(code="BAD_SIGNATURE", message="m")
        def check() -> bool:
            return True


def test_a_starargs_check_is_accepted(fresh_registry: None) -> None:
    @reg.register_check(code="STAR", message="m")
    def check(*args: Any) -> Verdict:
        return OK

    assert failures(ROW) == []


def test_explaining_a_row_does_not_mutate_the_row_or_the_context(fresh_registry: None) -> None:
    make_check("PASSES")
    row = ROW.copy()
    context = RowContext()
    failures(row, context=context)
    assert row.equals(ROW)
    assert context == RowContext()


# --- enabled state ----------------------------------------------------------


def test_a_rule_can_enable_an_off_by_default_check(fresh_registry: None) -> None:
    make_check("OFF", passes=False, default_enabled=False)
    assert codes(failures(ROW, rules=[enable("OFF")])) == ["OFF"]


def test_a_rule_applies_only_to_matching_rows(fresh_registry: None) -> None:
    make_check("ON", passes=False)
    only_internal = reg.Rule(
        name="internal", action="disable", codes=["ON"],
        criteria=[_MatchCriterion("email", "@internal", re.compile("@internal"))],
        match_all=False, message="why the rule exists")
    assert codes(failures(ROW, rules=[only_internal])) == ["ON"]
    internal_row = pd.Series({"age": 30, "email": "qa@internal.test"})
    assert failures(internal_row, rules=[only_internal]) == []


# --- explanations -----------------------------------------------------------


def test_every_registered_check_has_an_outcome_registered_check(fresh_registry: None) -> None:
    make_check("ONE")
    make_check("TWO", passes=False)
    assert statuses(engine._explain(ROW)) == {"ONE": Outcome.PASSED, "TWO": Outcome.FAILED}


def test_a_check_off_by_default_does_not_run_and_says_so(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("OFF", passes=False, default_enabled=False, calls=calls)
    assert detail(engine._explain(ROW), "OFF") == "disabled by default"
    assert calls == []


def test_a_check_disabled_by_a_rule_does_not_run_and_names_the_rule(
    fresh_registry: None,
) -> None:
    calls: list[str] = []
    make_check("ON", passes=False, calls=calls)
    outcomes = engine._explain(ROW, rules=[disable("ON", name="suppress_for_test_accounts")])
    assert detail(outcomes, "ON") == "disabled by rule 'suppress_for_test_accounts'"
    assert calls == []


def test_the_last_matching_rule_is_the_one_named(fresh_registry: None) -> None:
    make_check("CODE")
    rules = [disable("CODE", name="first"), disable("CODE", name="second")]
    assert detail(engine._explain(ROW, rules=rules), "CODE") == "disabled by rule 'second'"


# --- dependencies -----------------------------------------------------------


def test_a_dependent_is_not_run_when_its_prerequisite_fails(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("PREREQ", passes=False, calls=calls)
    make_check("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    outcomes = engine._explain(ROW)
    assert statuses(outcomes)["DEPENDENT"] == Outcome.SKIPPED
    assert detail(outcomes, "DEPENDENT") == "prerequisite did not pass: PREREQ"
    assert calls == ["PREREQ"]


def test_a_dependent_is_not_run_when_its_prerequisite_errored(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("PREREQ", raises=RuntimeError("boom"), calls=calls)
    make_check("DEPENDENT", passes=False, depends_on=["PREREQ"], calls=calls)
    outcomes = engine._explain(ROW)
    assert statuses(outcomes) == {"PREREQ": Outcome.ERRORED, "DEPENDENT": Outcome.SKIPPED}
    assert calls == ["PREREQ"]


def test_skipping_propagates_transitively(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("ROOT", passes=False, calls=calls)
    make_check("MIDDLE", passes=True, depends_on=["ROOT"], calls=calls)
    make_check("LEAF", passes=False, depends_on=["MIDDLE"], calls=calls)
    assert codes(failures(ROW)) == ["ROOT"]
    assert calls == ["ROOT"]


def test_a_disabled_dependent_is_skipped_even_when_its_prerequisite_passes(
    fresh_registry: None,
) -> None:
    make_check("PREREQ", passes=True)
    make_check("DEPENDENT", passes=False, default_enabled=False, depends_on=["PREREQ"])
    assert failures(ROW) == []


def test_sibling_dependents_are_independent(fresh_registry: None) -> None:
    make_check("PREREQ", passes=True)
    make_check("LEFT", passes=False, depends_on=["PREREQ"])
    make_check("RIGHT", passes=True, depends_on=["PREREQ"])
    assert codes(failures(ROW)) == ["LEFT"]


def test_registration_order_does_not_have_to_match_dependency_order(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("DEPENDENT", passes=True, depends_on=["PREREQ"], calls=calls)
    make_check("PREREQ", passes=True, calls=calls)
    assert failures(ROW) == []
    assert calls == ["PREREQ", "DEPENDENT"]


# --- root cause -------------------------------------------------------------


def test_root_cause_ignores_disabled_and_skipped_outcomes(fresh_registry: None) -> None:
    make_check("DISABLED_ONE", default_enabled=False)
    make_check("FAILS", passes=False)
    assert first_cause(engine._explain(ROW)) == "FAILS"


def test_an_errored_outcome_carries_the_layer_and_a_pointer_to_detail(
        fresh_registry: None) -> None:
    """An errored outcome is a reportable failure like any other, so it has to
    carry what the report and the root-cause rule read: its layer, and a message.
    The message is a fixed pointer to `detail`, not the check's own message, which
    would claim a verdict on data the check never finished reading. Mutation found
    only its `detail` under test, and a check that raised at the wrong layer
    changes which code a row reports as its cause.
    """

    make_check("BASE")
    make_check("RAISES", depends_on=["BASE"], raises=RuntimeError("boom"))
    outcome = next(o for o in engine._explain(ROW) if o.code == "RAISES")
    assert outcome.outcome == Outcome.ERRORED
    assert outcome.layer == 1
    assert outcome.message == "check raised; see detail"
    assert outcome.status == Status.ERROR
    assert outcome.detail.startswith("RuntimeError: boom (conftest.py:")


def test_an_errored_check_can_be_the_root_cause(fresh_registry: None) -> None:
    make_check("BROKEN", raises=RuntimeError("boom"))
    assert first_cause(engine._explain(ROW)) == "BROKEN"


# --- layers -----------------------------------------------------------------


def test_layer_counts_the_deepest_chain(fresh_registry: None) -> None:
    make_check("L0")
    make_check("L1", depends_on=["L0"])
    make_check("L2", depends_on=["L1"])
    make_check("WIDE", depends_on=["L0", "L2"])
    reg._validate_registry()
    assert {t.code: t.layer for t in reg._CHECKS} == {"L0": 0, "L1": 1, "L2": 2, "WIDE": 3}


def test_outcomes_carry_the_layer(fresh_registry: None) -> None:
    make_check("ROOT")
    make_check("LEAF", depends_on=["ROOT"])
    layers = {o.code: o.layer for o in engine._explain(ROW)}
    assert layers == {"ROOT": 0, "LEAF": 1}


# --- duplicate labels -------------------------------------------------------


def test_duplicate_labels_raise_before_any_check_runs(fresh_registry: None) -> None:
    """A duplicate label hands the check a Series, which every value helper turns
    into None -- so the check would silently pass on data it never read."""

    calls: list[str] = []
    make_check("CODE", calls=calls)
    with pytest.raises(ValueError, match=r"duplicate column labels \['age'\]"):
        engine._explain(pd.Series([1, 2], index=["age", "age"]))
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
        pytest.param({}, ["ROW_ALL_NULL", "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"],
                     id="empty-row"),
        pytest.param({"totally": "unrelated"},
                     ["AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"], id="unrelated-columns"),
    ],
)
def test_example_checks_report_the_expected_codes(
    example_checks: None, row: dict[str, Any], expected: list[str]
) -> None:
    assert codes(failures(pd.Series(row))) == expected


def test_a_missing_field_reports_once_not_from_every_check_that_reads_it(
    example_checks: None,
) -> None:
    """The whole point of layering: one complaint about a blank age."""

    row = pd.Series({"age": None, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    outcomes = engine._explain(row)
    assert codes(failures(row)) == ["AGE_PRESENT"]
    assert statuses(outcomes)["AGE_NOT_A_NUMBER"] == Outcome.SKIPPED
    assert statuses(outcomes)["AGE_NEGATIVE"] == Outcome.SKIPPED


def test_failure_comments_carry_the_numbers_a_reader_needs(example_checks: None) -> None:
    row = pd.Series({"age": 200, "email": "a@b.com", "start_date": "2024-01-01",
                     "end_date": "2024-02-01"})
    outcome = failures(row)[0]
    assert dict(outcome.comments) == {"value": 200.0, "maximum": 130}


# --- rule columns -----------------------------------------------------------


def test_check_rule_columns_is_quiet_when_every_criterion_column_is_present(
    fresh_registry: None,
) -> None:
    """A match-all rule has no criterion columns, so it is never warned about."""

    make_check("CODE")
    rule = reg.Rule(
        name="on_age", action="disable", codes=["CODE"],
        criteria=[_MatchCriterion("age", "^1$", re.compile("^1$"))], match_all=False, message="why the rule exists")
    assert rules.warn_missing_rule_columns(
        pd.DataFrame({"age": [1]}), [rule, disable("CODE")]) == []


def test_check_rule_columns_warns_about_a_column_the_data_lacks(fresh_registry: None) -> None:
    """A criterion on a missing column never matches, so the rule silently never fires."""

    make_check("CODE")
    rule = reg.Rule(
        name="legacy_only", action="disable", codes=["CODE"],
        criteria=[_MatchCriterion("source_sytem", "^LEGACY", re.compile("^LEGACY"))],
        match_all=False, message="why the rule exists")
    assert rules.warn_missing_rule_columns(pd.DataFrame({"age": [1]}), [rule]) == [
        "rule 'legacy_only' matches on column 'source_sytem', which is not in the data: "
        "the rule will never apply"
    ]


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
def test_example_checks_handle_edge_values(
    example_checks: None, row: dict[str, Any], expected: list[str]
) -> None:
    assert codes(failures(pd.Series(row))) == expected


def test_the_off_by_default_integer_check_once_enabled(example_checks: None) -> None:
    def row(age: float) -> "pd.Series[Any]":
        return pd.Series({"age": age, "email": "a@b.com", "start_date": "2024-01-01",
                          "end_date": "2024-02-01"})

    assert codes(failures(row(41.5))) == []
    assert codes(failures(row(41.5), rules=[enable("AGE_NOT_INTEGER")])) == ["AGE_NOT_INTEGER"]
    assert codes(failures(row(41.0), rules=[enable("AGE_NOT_INTEGER")])) == []


def test_a_child_blocked_by_a_disabled_parent_says_disabled(fresh_registry: None) -> None:
    """"Did not pass" reads as a failure; a chain switched off at its root is not one.
    A disabled prerequisite confirmed nothing, so it must not unlock anything."""

    calls: list[str] = []
    make_check("PARENT")
    make_check("CHILD", passes=False, depends_on=["PARENT"], calls=calls)
    rule = reg.Rule(name="off", action="disable", codes=["PARENT"], criteria=[],
                            match_all=True, source_file="<test>", message="why the rule exists")
    outcomes = engine._explain(pd.Series({"a": 1}), rules=[rule])
    assert [(o.code, o.outcome, o.detail) for o in outcomes] == [
        ("PARENT", "disabled", "disabled by rule 'off'"),
        ("CHILD", "skipped", "prerequisite disabled: PARENT"),
    ]
    assert calls == []


def test_a_mix_of_disabled_and_failed_prerequisites_says_did_not_pass(
    fresh_registry: None,
) -> None:
    """Only when *every* blocker was disabled is "disabled" the whole truth. Every
    blocker is named, and only the blockers."""

    make_check("GOOD")
    make_check("OFF")
    make_check("BROKEN", passes=False)
    make_check("CHILD", depends_on=["GOOD", "OFF", "BROKEN"])
    rule = reg.Rule(name="off", action="disable", codes=["OFF"], criteria=[],
                            match_all=True, source_file="<test>", message="why the rule exists")
    outcomes = engine._explain(pd.Series({"a": 1}), rules=[rule])
    assert outcomes[-1].outcome == Outcome.SKIPPED
    assert outcomes[-1].detail == "prerequisite did not pass: OFF, BROKEN"


def test_root_causes_are_every_failure_at_the_shallowest_layer(
    fresh_registry: None,
) -> None:
    """A deeper failure under a passing prerequisite is not one; a clean row has none."""

    make_check("A", passes=False)
    make_check("B", passes=False)
    make_check("OPEN")
    make_check("DEEPER", passes=False, depends_on=["OPEN"])
    outcomes = engine._explain(pd.Series({"a": 1}))
    assert _root_causes(outcomes) == ["A", "B"]
    reg.clear_registry()
    make_check("PASSES")
    assert _root_causes(engine._explain(pd.Series({"a": 1}))) == []
