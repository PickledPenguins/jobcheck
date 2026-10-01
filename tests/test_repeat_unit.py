"""Copies of one row: `validate(repeat_key=...)` and `register_check(repeat=True)`.

Rows sharing a `repeat_key` value are copies, as `explode` makes them. The first
runs every check; a later copy runs only the checks that repeat -- declared, or
inherited from a prerequisite -- and records the rest as `shared`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

from conftest import make_check
from jobcheck import (
    OK, Outcome, RowContext, Status, Verdict, build_report, register_check, registry_table,
    summarize_outcomes, validate,
)
from jobcheck.rules import Rule, _MatchCriterion

pytestmark = pytest.mark.fast


def copies() -> pd.DataFrame:
    """Job J1 in three copies, then J2 in one."""

    return pd.DataFrame({"id": ["J1", "J1", "J1", "J2"], "name": ["a", "a2", "b", "c"]})


def by_code(row_outcomes: list[Any]) -> dict[str, Any]:
    return {outcome.code: outcome for outcome in row_outcomes}


def test_a_check_that_does_not_repeat_runs_on_the_first_copy_only(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("ONCE", calls=calls)
    outcomes = validate(copies(), repeat_key="id")
    assert calls == ["ONCE", "ONCE"]   # J1's first copy and J2
    assert [row[0].outcome for row in outcomes] == [
        Outcome.PASSED, Outcome.SHARED, Outcome.SHARED, Outcome.PASSED]


def test_a_repeated_check_runs_on_every_copy(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("EACH", calls=calls, repeat=True)
    validate(copies(), repeat_key="id")
    assert calls == ["EACH"] * 4


def test_without_repeat_key_every_check_runs_on_every_row(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("ONCE", calls=calls)
    outcomes = validate(copies())
    assert calls == ["ONCE"] * 4
    assert all(row[0].outcome is Outcome.PASSED for row in outcomes)


def test_a_shared_outcome_passes_status_and_says_where(
    fresh_registry: None,
) -> None:
    make_check("ONCE", passes=False, status=Status.MALFORMED, comments={"v": 1})
    shared = validate(copies(), repeat_key="id")[1][0]
    assert shared.outcome is Outcome.SHARED
    assert shared.status == Status.PASS
    assert shared.detail == "failed at position 0, the first row with id J1"
    assert not shared.failed
    assert shared.message == "" and dict(shared.comments) == {}
    assert shared.layer == 0


def test_a_shared_outcome_keeps_its_checks_layer(fresh_registry: None) -> None:
    make_check("BASE")
    make_check("ONCE", depends_on=["BASE"])
    assert by_code(validate(copies(), repeat_key="id")[1])["ONCE"].layer == 1


def test_a_repeated_check_runs_on_a_copy_when_its_shared_prerequisite_passed(
    fresh_registry: None,
) -> None:
    calls: list[str] = []
    make_check("NAMES")
    make_check("DIR", depends_on=["NAMES"], calls=calls, repeat=True)
    outcomes = validate(copies(), repeat_key="id")
    assert calls == ["DIR"] * 4
    assert [by_code(row)["DIR"].outcome for row in outcomes] == [Outcome.PASSED] * 4


def test_a_repeated_check_on_a_copy_is_handed_that_copys_context(
    fresh_registry: None,
) -> None:
    seen: list[Any] = []

    @register_check("EACH", "m", repeat=True)
    def each(row: "pd.Series[Any]", context: Any) -> Any:
        seen.append(context.name)
        return OK

    @dataclass
    class Named(RowContext):
        name: str = ""

    validate(copies(), repeat_key="id",
             context_builder=lambda row: Named(name=row["name"]))
    assert seen == ["a", "a2", "b", "c"]


def test_a_dependent_of_a_repeated_check_repeats_and_follows_its_own_copy(
    fresh_registry: None,
) -> None:
    @register_check("DIR", "dir missing", repeat=True)
    def dir_exists(row: "pd.Series[Any]") -> Verdict:
        return Verdict(row["name"] != "a2")

    seen: list[str] = []

    @register_check("CHILD", "child missing", depends_on=["DIR"])
    def child_exists(row: "pd.Series[Any]") -> Any:
        seen.append(row["name"])
        return OK

    outcomes = validate(copies(), repeat_key="id")
    assert seen == ["a", "b", "c"]
    assert by_code(outcomes[1])["CHILD"].outcome is Outcome.SKIPPED
    assert by_code(outcomes[1])["CHILD"].detail == "prerequisite did not pass: DIR"
    assert registry_table().set_index("code")["repeat"].to_dict() == {
        "DIR": "declared", "CHILD": "inherited"}


def test_a_repeated_check_reads_a_shared_prerequisite_from_the_first_copy(
    fresh_registry: None,
) -> None:
    """The prerequisite ran once, on the first copy; every copy is gated by that."""

    calls: list[str] = []

    @register_check("NAMES", "names blank")
    def names(row: "pd.Series[Any]") -> Verdict:
        return Verdict(row["id"] != "J1")

    make_check("DIR", depends_on=["NAMES"], calls=calls, repeat=True)
    outcomes = validate(copies(), repeat_key="id")
    assert calls == ["DIR"]   # J2 only
    assert [by_code(row)["DIR"].outcome for row in outcomes[:3]] == [Outcome.SKIPPED] * 3
    assert by_code(outcomes[2])["NAMES"].outcome is Outcome.SHARED


def disable_on(name: str, codes: list[str]) -> Rule:
    """A rule disabling *codes* on the copy whose `name` is *name*."""

    pattern = f"^{name}$"
    return Rule(name=f"skip_{name}", action="disable", codes=codes,
                criteria=[_MatchCriterion("name", pattern, re.compile(pattern))],
                match_all=False, message="why the rule exists")


def test_a_check_disabled_on_every_copy_reads_as_disabled_on_each(
    fresh_registry: None,
) -> None:
    make_check("NAMES", default_enabled=False)
    make_check("DIR", depends_on=["NAMES"], repeat=True)
    copy = by_code(validate(copies(), repeat_key="id")[1])
    assert copy["NAMES"].detail == "disabled by off by default"
    assert copy["DIR"].detail == "prerequisite disabled: NAMES"


def test_a_rule_disables_a_shared_check_on_the_copy_it_matches(fresh_registry: None) -> None:
    make_check("ONCE")
    make_check("EACH", repeat=True)
    outcomes = validate(copies(), rules=[disable_on("a2", ["ONCE", "EACH"])], repeat_key="id")
    assert [by_code(row)["ONCE"].outcome for row in outcomes[:3]] == [
        Outcome.PASSED, Outcome.DISABLED, Outcome.SHARED]
    assert by_code(outcomes[1])["ONCE"].detail == "disabled by rule 'skip_a2'"
    assert by_code(outcomes[1])["EACH"].outcome is Outcome.DISABLED


def test_a_shared_check_disabled_on_the_first_copy_runs_on_the_next(
    fresh_registry: None,
) -> None:
    calls: list[str] = []
    make_check("ONCE", calls=calls)
    outcomes = validate(copies(), rules=[disable_on("a", ["ONCE"])], repeat_key="id")
    assert calls == ["ONCE", "ONCE"]   # J1's second copy, then J2
    assert [by_code(row)["ONCE"].outcome for row in outcomes[:3]] == [
        Outcome.DISABLED, Outcome.PASSED, Outcome.SHARED]
    assert by_code(outcomes[2])["ONCE"].detail == (
        "passed at position 1, the first row with id J1 to enable it")


def test_a_dependent_is_settled_with_the_prerequisite_a_rule_disabled(
    fresh_registry: None,
) -> None:
    """Skipped below a disabled check is not a result: the dependent runs on the
    copy that enables the chain, and is skipped on a copy that disables it."""

    calls: list[str] = []
    make_check("TOP")
    make_check("BELOW", depends_on=["TOP"], calls=calls)
    outcomes = validate(copies(), rules=[disable_on("a", ["TOP"]), disable_on("b", ["TOP"])],
                        repeat_key="id")
    assert calls == ["BELOW", "BELOW"]   # J1's second copy, then J2
    assert [by_code(row)["BELOW"].outcome for row in outcomes[:3]] == [
        Outcome.SKIPPED, Outcome.PASSED, Outcome.SKIPPED]
    assert by_code(outcomes[2])["BELOW"].detail == "prerequisite disabled: TOP"


def test_copies_need_not_be_adjacent(fresh_registry: None) -> None:
    calls: list[str] = []
    make_check("ONCE", calls=calls)
    df = pd.DataFrame({"id": ["J1", "J2", "J1"]})
    outcomes = validate(df, repeat_key="id")
    assert calls == ["ONCE", "ONCE"]
    assert outcomes[2][0].detail == "passed at position 0, the first row with id J1"


def test_a_shared_failure_is_reported_and_counted_once(fresh_registry: None) -> None:
    make_check("ONCE", passes=False)
    make_check("EACH", repeat=True)
    df = copies()
    outcomes = validate(df, repeat_key="id")
    report = build_report(outcomes, df=df, key_column="id")
    assert report.index.get_level_values("code").tolist() == ["ONCE", "ONCE"]   # J1 once, J2 once
    summary = summarize_outcomes(outcomes).set_index("code")
    assert summary.loc["ONCE", ["failed", "shared", "root_cause_rows"]].tolist() == [2, 2, 2]
    assert summary.loc["EACH", ["passed", "shared"]].tolist() == [4, 0]


def test_a_check_that_raised_is_shared_as_errored_in_detail(fresh_registry: None) -> None:
    make_check("ONCE", raises=RuntimeError("boom"))
    shared = validate(copies(), repeat_key="id")[1][0]
    assert shared.outcome is Outcome.SHARED
    assert shared.status == Status.PASS
    assert shared.detail == "errored at position 0, the first row with id J1"


def test_a_repeat_key_not_in_the_data_is_refused_even_for_an_empty_frame(
    fresh_registry: None,
) -> None:
    make_check("A")
    with pytest.raises(ValueError, match=r"repeat_key 'job' is not in the data\. "
                                         r"Available columns: id, name\."):
        validate(copies().iloc[:0], repeat_key="job")


def test_a_repeat_key_naming_two_columns_is_refused(fresh_registry: None) -> None:
    make_check("A")
    df = pd.DataFrame([[1, 2]], columns=["id", "id"])
    with pytest.raises(ValueError, match=r"^repeat_key 'id' appears 2 times in the data\. "
                                         r"Rename or drop the duplicate columns\.$"):
        validate(df, repeat_key="id")


def test_a_blank_repeat_key_value_is_refused_with_its_position(fresh_registry: None) -> None:
    make_check("A")
    df = pd.DataFrame({"id": ["J1", None]})
    with pytest.raises(ValueError, match=r"^repeat_key 'id' is blank at position 1: every row "
                                         r"needs a value to say which rows are its copies\.$"):
        validate(df, repeat_key="id")


def test_an_unhashable_repeat_key_value_is_refused_with_its_position(
    fresh_registry: None,
) -> None:
    make_check("A")
    df = pd.DataFrame({"id": [["J1"]]})
    with pytest.raises(TypeError, match=r"^repeat_key 'id' holds \['J1'\] at position 0, "
                                        r"which cannot be compared as a key: use a column "
                                        r"of text or numbers\.$"):
        validate(df, repeat_key="id")


def test_repeat_must_be_a_bool(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="Check 'A': repeat must be True or False, got 1"):
        register_check("A", "m", repeat=1)(lambda row: OK)  # type: ignore[arg-type]
