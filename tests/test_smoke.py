"""Smoke checks: the entry point starts and does its main job."""

from __future__ import annotations

import pytest

from conftest import run_cli

pytestmark = pytest.mark.fast


def test_main_runs_and_exits_zero() -> None:
    result = run_cli("examples/main.py")
    assert result.returncode == 0, result.stderr


def test_main_validates_the_demo_frame() -> None:
    out = run_cli("examples/main.py").stdout
    assert "AGE_NEGATIVE" in out and "Age is negative" in out


def test_a_clean_row_produces_no_report_line() -> None:
    """Row 1 of the demo frame is clean, so its key never appears in the report."""

    failures = run_cli("examples/main.py").stdout.split("== Failures ==")[1]
    assert "\n1   " not in failures


def test_help_exits_zero_and_lists_the_flags() -> None:
    result = run_cli("examples/main.py", "--help")
    assert result.returncode == 0
    for flag in ("--data", "--rules", "--report", "--explain", "--summary"):
        assert flag in result.stdout
