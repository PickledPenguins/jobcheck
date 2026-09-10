"""Property-based checks for the three invariants the whole design rests on.

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

import pandas as pd
import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from conftest import make_check  # noqa: E402
from jobcheck import registry as reg  # noqa: E402
from jobcheck.results import PASSED  # noqa: E402
from jobcheck import engine

pytestmark = pytest.mark.long

# A small alphabet of check codes, so generated dependency graphs actually overlap
# instead of each check being an island -- overlap is where the invariants can break.
CODES = st.sampled_from([f"T{i}" for i in range(6)])


@st.composite
def dependency_graphs(draw: st.DrawFn) -> list[tuple[str, list[str], bool]]:
    """A registry: each check's code, its prerequisites, and whether it passes.

    Prerequisites are drawn only from codes already placed, so the graph is
    acyclic by construction -- a cycle is `_topological_order`'s job to catch,
    not this generator's job to produce.
    """

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
def test_a_test_never_runs_unless_every_prerequisite_passed(
    fresh_registry: None, graph: list[tuple[str, list[str], bool]]
) -> None:
    reg.clear_registry()
    calls: list[str] = []
    for code, depends_on, passes in graph:
        make_check(code, passes=passes, depends_on=depends_on, calls=calls)

    engine.validate_row(pd.Series({"age": 1}))
    outcomes = engine.explain_row(pd.Series({"age": 1}))
    by_code = {outcome.code: outcome for outcome in outcomes}

    for code, depends_on, _passes in graph:
        if code not in calls:
            continue
        for prerequisite in depends_on:
            assert by_code[prerequisite].outcome == PASSED, (
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

    outcomes = engine.explain_row(pd.Series({"age": 1}))
    failures = [outcome for outcome in outcomes if outcome.failed]
    cause = engine.root_cause(outcomes)

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
