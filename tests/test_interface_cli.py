"""Interface checks: the CLI contract — the parser's defaults, and what only a
subprocess shows: the working directory, exit codes reaching the shell, and
which stream each line goes to.

Every other path of the entry point is driven in process by
`tests/test_main_unit.py`, and run as a subprocess, byte for byte, by the
example and failure catalogs.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

import main
from conftest import PROJECT_ROOT, run_cli

pytestmark = pytest.mark.fast


# --- argument parsing -------------------------------------------------------


def test_defaults_when_no_flags_are_given() -> None:
    args = main.build_parser().parse_args([])
    assert args.data is None
    assert args.rules == [os.path.join(PROJECT_ROOT, "examples/rules/error_rules.yaml")]
    assert args.report == "table"
    assert args.explain is None
    assert args.summary is False


def test_rules_takes_several_files_in_order_and_replaces_the_default() -> None:
    parser = main.build_parser()
    assert parser.parse_args(["--rules", "a.yaml", "b.yaml"]).rules == ["a.yaml", "b.yaml"]
    assert parser.parse_args(["--rules", "a.yaml"]).rules == ["a.yaml"]


# --- what only a subprocess shows -------------------------------------------


def test_the_entry_point_runs_from_any_directory(tmp_path: Any) -> None:
    """Its check files and its default rule file are named relative to the
    clone it lives in, not to wherever it was started."""

    result = run_cli(os.path.join(PROJECT_ROOT, "examples/main.py"), cwd=str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Loaded 3 rule(s) from 1 file(s)")
    assert "== Report" in result.stdout


def test_a_run_with_failing_rows_exits_zero_with_everything_on_stdout() -> None:
    """Validation failures are data, not a process error."""

    result = run_cli("examples/main.py")
    assert result.returncode == 0
    assert result.stdout.startswith("Loaded 3 rule(s) from 1 file(s)")
    assert "AGE_NEGATIVE" in result.stdout
    assert result.stderr == ""


def test_an_error_is_one_line_on_stderr_and_stdout_stays_clean() -> None:
    result = run_cli("examples/main.py", "--rules", "no_such_file.yaml")
    assert result.returncode == 2
    assert result.stderr.startswith("error: No rule file at")
    assert "Traceback" not in result.stderr
    assert "No rule file at 'no_such_file.yaml'" in result.stderr
    assert "load_rules() names files explicitly" in result.stderr
    assert "== Registry" not in result.stdout


# --- reading a data file ----------------------------------------------------


def test_load_frame_reads_every_column_of_a_csv_as_text(tmp_path: Any) -> None:
    # A check that judges whether a value is a number has to see what the file
    # said; pandas inferring the column would repair "41.5" before anything
    # looked at it.
    path = tmp_path / "rows.csv"
    path.write_text("id,age\n1,41.5\n2,007\n")
    frame = main.load_frame(str(path))
    assert list(frame["age"]) == ["41.5", "007"]


def test_load_frame_reads_an_empty_cell_as_missing_not_as_the_word(tmp_path: Any) -> None:
    import pandas as pd

    path = tmp_path / "rows.csv"
    path.write_text("id,age\n1,\n")
    assert pd.isna(main.load_frame(str(path))["age"][0])
