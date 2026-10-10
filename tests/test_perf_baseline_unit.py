"""Unit checks for the performance baseline's own logic.

The gate is only as good as the arithmetic under it, and that arithmetic never
runs in the fast suite -- so it is tested here directly, with the clock and the
file replaced. What matters: a first measurement is recorded rather than
compared, a stored one is compared against a tolerance derived from its measured
spread, and a baseline from a different machine is discarded rather than trusted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import perf_baseline as pb

pytestmark = pytest.mark.fast


@pytest.fixture
def baseline_file(tmp_path: Path, monkeypatch: Any) -> Path:
    path = tmp_path / "perf-baseline.json"
    monkeypatch.setattr(pb, "BASELINE", path)
    return path


def test_tolerance_follows_the_spread_between_a_floor_and_a_cap() -> None:
    assert pb.tolerance({"spread": 0.0}) == pb.MIN_TOLERANCE
    assert pb.tolerance({"spread": 0.30}) == pytest.approx(0.60)
    assert pb.tolerance({"spread": 5.0}) == pb.MAX_TOLERANCE
    assert pb.tolerance({}) == pb.MIN_TOLERANCE


def test_measure_reports_a_median_and_a_relative_spread() -> None:
    result = pb.measure(lambda: None, repeats=3)
    assert result["repeats"] == 3.0
    assert result["median"] >= 0.0
    assert result["spread"] >= 0.0


def test_the_first_measurement_is_recorded_not_compared(baseline_file: Path) -> None:
    verdict, median, limit, ratio = pb.compare("thing", lambda: None)
    assert verdict == "recorded"
    assert limit == float("inf")
    assert ratio == 0.0
    stored = json.loads(baseline_file.read_text())
    assert "thing" in stored["measurements"]
    assert stored["measurements"]["thing"]["median"] == pytest.approx(median)


def test_a_stored_measurement_is_compared_against_its_median_plus_tolerance(
        baseline_file: Path) -> None:
    """The limit is the stored median plus its tolerance, and the ratio says how
    far the new measurement moved from that median."""
    baseline_file.write_text(json.dumps({
        "machine": pb.machine(),
        "measurements": {"thing": {"median": 1.0, "spread": 0.0, "repeats": 5.0}},
    }))
    verdict, median, limit, ratio = pb.compare("thing", lambda: None)
    assert verdict == "compared"
    assert limit == pytest.approx(1.0 * (1 + pb.MIN_TOLERANCE))
    assert ratio == pytest.approx(median / 1.0)


def test_a_baseline_from_another_machine_is_discarded(baseline_file: Path) -> None:
    """Otherwise the first run on a new machine gates against numbers from an old one."""
    baseline_file.write_text(json.dumps({
        "machine": {"python": "1.0", "platform": "elsewhere", "processor": "other"},
        "measurements": {"thing": {"median": 1e-9, "spread": 0.0, "repeats": 5.0}},
    }))
    verdict, _median, _limit, _ratio = pb.compare("thing", lambda: None)
    assert verdict == "recorded"
    assert json.loads(baseline_file.read_text())["machine"] == pb.machine()


def test_the_machine_record_names_the_interpreter_and_the_host() -> None:
    described = pb.machine()
    assert set(described) == {"python", "platform", "processor"}
    assert described["python"][0].isdigit()
