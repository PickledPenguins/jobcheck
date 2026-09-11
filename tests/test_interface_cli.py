"""Interface checks: the CLI contract — flags, defaults, exit codes, routing."""

from __future__ import annotations

from typing import Any

import pytest

import main
from conftest import run_cli

pytestmark = pytest.mark.fast


# --- argument parsing -------------------------------------------------------


def test_defaults_when_no_flags_are_given() -> None:
    args = main.build_parser().parse_args([])
    assert args.data is None
    assert args.rules == ["examples/rules/error_overrides.yaml"]
    assert args.report == "table"
    assert args.explain is None
    assert args.summary is False


def test_rules_takes_several_files_in_the_order_given() -> None:
    args = main.build_parser().parse_args(["--rules", "a.yaml", "b.yaml"])
    assert args.rules == ["a.yaml", "b.yaml"]


def test_passing_rules_replaces_the_default_rather_than_extending_it() -> None:
    assert main.build_parser().parse_args(["--rules", "a.yaml"]).rules == ["a.yaml"]


# --- exit codes -------------------------------------------------------------


def test_success_exits_zero() -> None:
    assert run_cli("examples/main.py").returncode == 0


def test_failing_rows_still_exit_zero() -> None:
    """Validation failures are data, not a process error."""

    result = run_cli("examples/main.py")
    assert "AGE_NEGATIVE" in result.stdout
    assert result.returncode == 0


def test_the_report_names_each_row_by_its_key_column_and_root_cause() -> None:
    failures = run_cli("examples/main.py").stdout.split("== Failures ==")[1]
    assert "2        | AGE_NEGATIVE" in failures
    assert "minimum=0; value=-5.0" in failures
    assert "<no key>" in failures


def test_cascading_checks_are_absent_from_the_report() -> None:
    """Row 5 has no age at all: only AGE_PRESENT is reported for it."""

    failures = run_cli("examples/main.py").stdout.split("== Failures ==")[1]
    age_lines = [line for line in failures.splitlines() if line.startswith("5 ")]
    assert [line.split("|")[1].strip() for line in age_lines] == [
        "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"
    ]


def test_the_csv_report_format_is_selectable() -> None:
    out = run_cli("examples/main.py", "--report", "csv").stdout.split("== Failures ==")[1]
    assert out.splitlines()[1].startswith("row,code,status,layer,outcome")


def test_explain_prints_one_row_and_its_root_cause() -> None:
    out = run_cli("examples/main.py", "--explain", "5").stdout
    assert "== Row 5 ==" in out
    assert "prerequisite did not pass: AGE_PRESENT" in out
    # Row 5 is entirely empty, so every layer-0 check fails and all of them are
    # root causes -- none is upstream of another.
    last = out.strip().splitlines()[-1]
    assert last.startswith("root causes: ")
    assert "ROW_ALL_NULL" in last


def test_explain_outside_the_frame_exits_two() -> None:
    result = run_cli("examples/main.py", "--explain", "99")
    assert result.returncode == 2
    assert "--explain 99 is outside the frame's 6 row(s)" in result.stderr


def test_summary_reports_counts_and_root_causes() -> None:
    out = run_cli("examples/main.py", "--summary").stdout
    assert "== Summary ==" in out
    assert "skipped" in out
    assert "Root cause of each failing row:" in out


def test_unknown_flag_exits_two() -> None:
    result = run_cli("examples/main.py", "--nope")
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_flag_without_its_value_exits_two() -> None:
    result = run_cli("examples/main.py", "--rules")
    assert result.returncode == 2
    assert "expected at least one argument" in result.stderr


def test_missing_override_file_exits_one() -> None:
    result = run_cli("examples/main.py", "--rules", "no_such_file.yaml")
    assert result.returncode == 1
    assert "FileNotFoundError" in result.stderr
    assert "no_such_file.yaml" in result.stderr


# --- output routing and shape ----------------------------------------------


def test_results_go_to_stdout_and_nothing_to_stderr() -> None:
    result = run_cli("examples/main.py")
    assert result.stdout.startswith("Loaded 3 override rule(s) from 1 file(s)")
    assert result.stderr == ""


def test_errors_go_to_stderr_and_leave_stdout_clean() -> None:
    result = run_cli("examples/main.py", "--rules", "no_such_file.yaml")
    assert "Traceback" in result.stderr
    assert "== Registry ==" not in result.stdout


def test_the_default_run_prints_the_registry_and_the_failures() -> None:
    out = run_cli("examples/main.py").stdout
    assert "== Registry ==" in out
    assert "== Failures ==" in out


# --- reading a data file ----------------------------------------------------


def test_load_frame_returns_the_demo_frame_when_no_path_is_given() -> None:
    frame = main.load_frame(None)
    assert list(frame["id"])[:5] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert len(frame) == 6


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


def test_a_missing_data_file_exits_two_naming_the_path() -> None:
    result = run_cli("examples/main.py", "--data", "no/such/file.csv")
    assert result.returncode == 2
    assert "cannot read no/such/file.csv" in result.stderr


def test_a_data_file_with_no_columns_exits_two(tmp_path: Any) -> None:
    path = tmp_path / "blank.csv"
    path.write_text("")
    result = run_cli("examples/main.py", "--data", str(path))
    assert result.returncode == 2
    assert "cannot read" in result.stderr


def test_a_csv_file_is_validated_when_one_is_named() -> None:
    # Failures in the data are a report, not an error: the run exits 0 and the
    # reader decides. Only a broken *invocation* exits non-zero.
    result = run_cli("examples/main.py", "--data", "examples/data/customers.csv")
    assert result.returncode == 0
    assert "ROW_ALL_NULL" in result.stdout
