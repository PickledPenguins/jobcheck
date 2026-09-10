"""Performance: a gate against this machine's own baseline, not a printout.

Marked ``perf`` and in neither commit suite: these repeat their work several
times and would make every commit slower for a signal that belongs to a release.
Run them with ``./run-tests.sh perf``; the first run on a machine records the
baseline into a gitignored file and says so, and later runs fail when a median
moves past the machine's measured noise.

Memory ceilings live in ``./run-tests.sh memory`` instead: ``tracemalloc``
roughly triples the time it measures, so a run that gates both at once gates
neither honestly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pytest

from conftest import make_check
from perf_baseline import compare
from jobcheck import collect_outcomes, iter_traces, registry as reg
from jobcheck import report as rep

pytestmark = pytest.mark.perf

ROWS = 4_000


def frame(rows: int = ROWS) -> pd.DataFrame:
    pattern = [
        {"age": 34, "email": "a@b.com", "start_date": "2024-01-01", "end_date": "2024-02-01"},
        {"age": -5, "email": "nope", "start_date": "2024-01-01", "end_date": "2024-02-01"},
        {"age": 200, "email": "c@nodot", "start_date": "2024-01-01", "end_date": "2024-02-01"},
        {"age": None, "email": None, "start_date": None, "end_date": None},
    ]
    return pd.DataFrame([pattern[i % 4] for i in range(rows)])


def gate(name: str, work: Callable[[], Any]) -> None:
    """Compare one measurement against the baseline, or record it the first time."""

    verdict, median, limit, ratio = compare(name, work)
    if verdict == "recorded":
        pytest.skip(f"baseline recorded for {name}: {median:.3f}s "
                    f"(rerun to gate against it)")
    assert median <= limit, (
        f"{name}: {median:.3f}s against a baseline limit of {limit:.3f}s "
        f"({ratio:.2f}x the recorded median)"
    )


def test_validating_a_frame_has_not_got_slower(example_suites: None) -> None:
    df = frame()
    gate("collect_outcomes/4000", lambda: collect_outcomes(df))


def test_streaming_a_frame_has_not_got_slower(example_suites: None) -> None:
    df = frame()
    gate("iter_traces/4000", lambda: [t.root_cause for t in iter_traces(df)])


def test_building_a_report_has_not_got_slower(example_suites: None) -> None:
    df = frame()
    outcomes = collect_outcomes(df)
    gate("build_report/4000", lambda: rep.build_report(outcomes, df=df, key_column=None))


def test_rendering_a_report_has_not_got_slower(example_suites: None) -> None:
    df = frame()
    report = rep.build_report(collect_outcomes(df), df=df)
    gate("render_report/4000", lambda: rep.render_report(report, fmt="csv"))


def test_summarising_has_not_got_slower(example_suites: None) -> None:
    outcomes = collect_outcomes(frame())
    gate("summarise_outcomes/4000", lambda: rep.summarise_outcomes(outcomes))


def test_resolving_many_rules_has_not_got_slower(fresh_registry: None, tmp_path: Path) -> None:
    for index in range(50):
        make_check(f"CODE_{index}")
    rules = "\n".join(
        f"- name: rule_{index}\n  action: disable\n  codes: [CODE_{index}]\n"
        f"  match:\n    - column: email\n      pattern: '^no'"
        for index in range(50)
    )
    path = tmp_path / "rules.yaml"
    path.write_text(rules)
    overrides = reg.load_overrides(str(path))
    df = frame(1_000)
    gate("collect_outcomes/1000-rows-50-rules", lambda: collect_outcomes(df, overrides=overrides))
