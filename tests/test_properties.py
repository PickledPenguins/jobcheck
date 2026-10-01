"""Property-based checks for the three invariants the whole design rests on, and
for copies of a row under `validate(repeat_key=...)`.

`tests/test_fuzz.py` checks these too, but only against the fixed seed it uses;
Hypothesis explores the input space on its own and shrinks a failure down to the
smallest case that still reproduces it, which is the piece example-based fuzzing
cannot do.

``hypothesis`` is in the ``dev`` extra, so a normal development install runs
these. The import guard exists for someone running the suite against a bare
runtime install, and `tests/test_api_contract.py` asserts the dependency is
declared, so a silent skip cannot become the permanent state without the suite
saying so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from conftest import first_cause, make_check  # noqa: E402
from jobcheck import registry as reg  # noqa: E402
from jobcheck.results import Outcome, Status, Verdict  # noqa: E402
from jobcheck.rules import Rule, _MatchCriterion  # noqa: E402
from jobcheck import engine, validate  # noqa: E402

pytestmark = pytest.mark.long


@st.composite
def dependency_graphs(draw: st.DrawFn) -> list[tuple[str, list[str], bool]]:
    """A registry: each check's code, its prerequisites, and whether it passes.

    Prerequisites are drawn only from codes already placed, so the graph is
    acyclic by construction -- a cycle is `_topological_order`'s job to catch,
    not this generator's job to produce.
    """

    # A small alphabet of codes, so generated graphs overlap instead of each
    # check being an island -- overlap is where the invariants can break.
    size = draw(st.integers(min_value=1, max_value=6))
    codes = draw(st.permutations([f"T{i}" for i in range(6)]))[:size]
    checks = []
    for index, code in enumerate(codes):
        if index == 0:
            depends_on: list[str] = []
        else:
            depends_on = draw(st.lists(st.sampled_from(codes[:index]), max_size=2, unique=True))
        passes = draw(st.booleans())
        checks.append((code, depends_on, passes))
    return checks


@given(dependency_graphs())
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_a_check_never_runs_unless_every_prerequisite_passed(
    fresh_registry: None, graph: list[tuple[str, list[str], bool]]
) -> None:
    reg.clear_registry()
    calls: list[str] = []
    for code, depends_on, passes in graph:
        make_check(code, passes=passes, depends_on=depends_on, calls=calls)

    outcomes = engine._explain(pd.Series({"age": 1}))
    by_code = {outcome.code: outcome for outcome in outcomes}

    for code, depends_on, _passes in graph:
        if code not in calls:
            continue
        for prerequisite in depends_on:
            assert by_code[prerequisite].outcome == Outcome.PASSED, (
                f"{code} ran while its prerequisite {prerequisite} had not passed"
            )


@given(dependency_graphs())
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_root_cause_is_always_the_shallowest_failure(
    fresh_registry: None, graph: list[tuple[str, list[str], bool]]
) -> None:
    reg.clear_registry()
    for code, depends_on, passes in graph:
        make_check(code, passes=passes, depends_on=depends_on)

    outcomes = engine._explain(pd.Series({"age": 1}))
    failures = [outcome for outcome in outcomes if outcome.failed]
    cause = first_cause(outcomes)

    if not failures:
        assert cause is None
        return
    shallowest = min(outcome.layer for outcome in failures)
    assert next(o for o in outcomes if o.code == cause).layer == shallowest


@given(dependency_graphs())
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_evaluation_order_is_a_topological_order_of_the_graph(
    fresh_registry: None, graph: list[tuple[str, list[str], bool]]
) -> None:
    reg.clear_registry()
    for code, depends_on, passes in graph:
        make_check(code, passes=passes, depends_on=depends_on)

    order = [check.code for check in reg._get_topo_order()]
    position = {code: index for index, code in enumerate(order)}
    depends_by_code = {code: depends_on for code, depends_on, _ in graph}

    assert sorted(order) == sorted(depends_by_code)
    for code, depends_on in depends_by_code.items():
        for prerequisite in depends_on:
            assert position[prerequisite] < position[code], (
                f"{prerequisite} must be evaluated before {code}"
            )


# --- copies of a row ---------------------------------------------------------


@dataclass
class CopyCase:
    """A registry, a frame of copies, and the rules that switch checks off per row.

    Row *i* is named `r<i>`; its key says whose copy it is. Whether a check
    passes, and whether a rule disables it, is drawn per check and per row.
    """

    graph: list[tuple[str, list[str], bool]]
    keys: list[str]
    passes: dict[tuple[str, int], bool]
    disabled: set[tuple[str, int]]


@st.composite
def copy_cases(draw: st.DrawFn, all_repeat: bool = False) -> CopyCase:
    graph = [(code, depends_on, all_repeat or draw(st.booleans()))
             for code, depends_on, _ in draw(dependency_graphs())]
    rows = draw(st.integers(min_value=1, max_value=6))
    keys = draw(st.lists(st.sampled_from(["K0", "K1", "K2"]), min_size=rows, max_size=rows))
    pairs = [(code, i) for code, _, _ in graph for i in range(rows)]
    passes = {pair: draw(st.booleans()) for pair in pairs}
    disabled = {pair for pair in pairs if draw(st.integers(min_value=0, max_value=3)) == 0}
    return CopyCase(graph, keys, passes, disabled)


def run_copies(case: CopyCase, repeat_key: str | None = "key") -> tuple[
        list[list[Any]], list[tuple[str, int]]]:
    """Register *case*'s checks and validate its frame: the outcomes, and every
    call as `(code, row)`."""

    reg.clear_registry()
    calls: list[tuple[str, int]] = []
    for code, depends_on, repeat in case.graph:
        def check(row: "pd.Series[Any]", *, code: str = code) -> Verdict:
            calls.append((code, row["i"]))
            return Verdict(Status.PASS if case.passes[(code, row["i"])] else Status.INVALID)
        reg.register_check(code, f"{code} failed", depends_on=depends_on,
                           repeat=repeat)(check)
    rules = []
    for i in range(len(case.keys)):
        codes = [code for code, row in case.disabled if row == i]
        if codes:
            rules.append(Rule(name=f"off_r{i}", action="disable", codes=sorted(codes),
                              criteria=[_MatchCriterion("name", f"^r{i}$",
                                                        re.compile(f"^r{i}$"))],
                              match_all=False, message="drawn"))
    df = pd.DataFrame({"key": case.keys, "name": [f"r{i}" for i in range(len(case.keys))],
                       "i": range(len(case.keys))})
    return validate(df, rules=rules, repeat_key=repeat_key), calls


def chain_enabled(case: CopyCase, code: str, row: int) -> bool:
    """No rule disables *code*, or any check it depends on, on *row*."""

    depends_by_code = {c: depends_on for c, depends_on, _ in case.graph}
    return ((code, row) not in case.disabled
            and all(chain_enabled(case, d, row) for d in depends_by_code[code]))


COPY_SETTINGS = settings(max_examples=200,
                         suppress_health_check=[HealthCheck.function_scoped_fixture])


@given(copy_cases())
@COPY_SETTINGS
def test_a_check_that_does_not_repeat_settles_once_per_key(
    fresh_registry: None, case: CopyCase
) -> None:
    """It is called at most once per key, and settled on exactly one copy when
    some copy enables its chain: every other enabled copy shares that result."""

    outcomes, calls = run_copies(case)
    for check in reg._CHECKS:
        if check.repeats:
            continue
        for key in set(case.keys):
            rows = [i for i, k in enumerate(case.keys) if k == key]
            assert len([1 for code, i in calls if code == check.code and i in rows]) <= 1
            enabled = [i for i in rows if chain_enabled(case, check.code, i)]
            settled = [i for i in enabled
                       if outcomes[i][_position(check.code)].outcome is not Outcome.SHARED]
            assert len(settled) == (1 if enabled else 0)
            if enabled:
                assert settled[0] == enabled[0]
            for i in set(rows) - set(enabled):   # switched off here: never shared
                assert outcomes[i][_position(check.code)].outcome in (
                    Outcome.DISABLED, Outcome.SKIPPED)


@given(copy_cases())
@COPY_SETTINGS
def test_a_shared_outcome_passes_and_names_an_earlier_copy_that_did_it(
    fresh_registry: None, case: CopyCase
) -> None:
    outcomes, _ = run_copies(case)
    for i, row_outcomes in enumerate(outcomes):
        for outcome in row_outcomes:
            if outcome.outcome is not Outcome.SHARED:
                continue
            assert outcome.status == Status.PASS and not outcome.failed
            match = re.fullmatch(r"(\w+) at position (\d+), the first row with key (\w+)"
                                 r"( to enable it)?", outcome.detail)
            assert match is not None, outcome.detail
            what, where, key, later = match.groups()
            earlier = int(where)
            assert earlier < i and case.keys[earlier] == key == case.keys[i]
            assert (later is not None) == (case.keys.index(key) != earlier)
            original = outcomes[earlier][_position(outcome.code)]
            assert original.outcome.value == what


@given(copy_cases())
@COPY_SETTINGS
def test_a_check_is_disabled_exactly_where_a_rule_disables_it(
    fresh_registry: None, case: CopyCase
) -> None:
    outcomes, _ = run_copies(case)
    for i, row_outcomes in enumerate(outcomes):
        for outcome in row_outcomes:
            assert ((outcome.outcome is Outcome.DISABLED)
                    == ((outcome.code, i) in case.disabled)), (outcome, i)


@given(copy_cases(all_repeat=True))
@COPY_SETTINGS
def test_when_every_check_repeats_copies_change_nothing(
    fresh_registry: None, case: CopyCase
) -> None:
    assert run_copies(case)[0] == run_copies(case, repeat_key=None)[0]


def _position(code: str) -> int:
    """Where *code*'s outcome is in each row's list: evaluation order."""

    return [check.code for check in reg._get_topo_order()].index(code)
