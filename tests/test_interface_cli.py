"""Interface checks: the CLI contract — flags, defaults, exit codes, routing."""

from __future__ import annotations

from typing import Any

import pytest

import main
from conftest import run_cli

pytestmark = pytest.mark.fast


# --- argument parsing -------------------------------------------------------


def test_defaults_when_no_flags_are_given() -> None:
    args = main.parse_args([])
    assert args.suites == ["hard_checks", "soft_checks"]
    assert args.overrides == ["examples/rules/error_overrides.yaml"]
    assert args.verbose == 0


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["-e", "hard_checks", "soft_checks"], id="multi-value"),
        pytest.param(["-e", "hard_checks", "-e", "soft_checks"], id="repeated"),
        pytest.param(["-e", "hard_checks", "-o", "x.yaml", "-e", "soft_checks"], id="interleaved"),
        pytest.param(["--suites", "hard_checks", "--suites", "soft_checks"], id="long-form"),
    ],
)
def test_suites_flatten_in_the_order_given(argv: list[str]) -> None:
    assert main.parse_args(argv).suites == ["hard_checks", "soft_checks"]


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["-o", "a.yaml", "b.yaml"], id="multi-value"),
        pytest.param(["-o", "a.yaml", "-o", "b.yaml"], id="repeated"),
        pytest.param(["--overrides", "a.yaml", "-e", "hard_checks", "--overrides", "b.yaml"],
                     id="interleaved"),
    ],
)
def test_overrides_flatten_in_the_order_given(argv: list[str]) -> None:
    assert main.parse_args(argv).overrides == ["a.yaml", "b.yaml"]


@pytest.mark.parametrize(
    "argv, expected",
    [
        pytest.param([], 0, id="absent"),
        pytest.param(["-v"], 1, id="one"),
        pytest.param(["-vv"], 2, id="two"),
        pytest.param(["-v", "-v", "-v"], 3, id="three"),
        pytest.param(["--verbose"], 1, id="long-form"),
    ],
)
def test_verbose_counts(argv: list[str], expected: int) -> None:
    assert main.parse_args(argv).verbose == expected


def test_passing_a_suite_replaces_the_default_rather_than_extending_it() -> None:
    assert main.parse_args(["-e", "hard_checks"]).suites == ["hard_checks"]


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


def test_cascading_tests_are_absent_from_the_report() -> None:
    """Row 5 has no age at all: only AGE_PRESENT is reported for it."""

    failures = run_cli("examples/main.py").stdout.split("== Failures ==")[1]
    age_lines = [line for line in failures.splitlines() if line.startswith("5 ")]
    assert [line.split("|")[1].strip() for line in age_lines] == [
        "AGE_PRESENT", "DATES_PRESENT", "EMAIL_PRESENT"
    ]


def test_include_skipped_shows_what_a_failure_blocked() -> None:
    failures = run_cli("examples/main.py", "--include-skipped").stdout.split("== Failures ==")[1]
    assert "prerequisite did not pass: AGE_PRESENT" in failures


def test_the_csv_report_format_is_selectable() -> None:
    out = run_cli("examples/main.py", "--report", "csv").stdout.split("== Failures ==")[1]
    assert out.splitlines()[1].startswith("row,code,status,layer,suite,outcome")


def test_the_report_can_be_written_to_a_file(tmp_path: Any) -> None:
    path = tmp_path / "report.csv"
    result = run_cli("examples/main.py", "--report-file", str(path), "--report", "csv")
    assert result.returncode == 0
    assert f"wrote {path}" in result.stdout
    assert path.read_text(encoding="utf-8").startswith("row,code,status")


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
    result = run_cli("examples/main.py", "-e")
    assert result.returncode == 2
    assert "expected at least one argument" in result.stderr


def test_unknown_suite_exits_one() -> None:
    result = run_cli("examples/main.py", "-e", "nope_tests")
    assert result.returncode == 1
    assert "Unknown suite 'nope_tests'" in result.stderr


def test_missing_override_file_exits_one() -> None:
    result = run_cli("examples/main.py", "-o", "no_such_file.yaml")
    assert result.returncode == 1
    assert "FileNotFoundError" in result.stderr
    assert "no_such_file.yaml" in result.stderr


# --- output routing and shape ----------------------------------------------


def test_results_go_to_stdout_and_nothing_to_stderr() -> None:
    result = run_cli("examples/main.py")
    assert result.stdout.startswith("Loaded suites: ['base', 'hard_checks', 'soft_checks']")
    assert result.stderr == ""


def test_errors_go_to_stderr_and_leave_stdout_clean() -> None:
    result = run_cli("examples/main.py", "-e", "nope_tests")
    assert "Traceback" in result.stderr
    assert "== Registry ==" not in result.stdout


def test_default_run_prints_the_registry_tables_and_the_failures() -> None:
    out = run_cli("examples/main.py").stdout
    assert "== Registry ==" in out
    assert "== Registry vs overrides ==" in out
    assert "== Failures ==" in out
    assert "== Override rules (by rule) ==" not in out


def test_debug_one_adds_the_cross_reference_column_only() -> None:
    out = run_cli("examples/main.py", "-v").stdout
    assert "could_be_overridden_by" in out
    assert "source_file" not in out
    assert "== Override rules (by rule) ==" not in out


def test_debug_two_adds_source_files_and_the_by_rule_table() -> None:
    out = run_cli("examples/main.py", "-vv").stdout
    assert "source_file" in out
    assert "== Override rules (by rule) ==" in out
    assert "codes_hit_count" in out


def test_suite_selection_changes_which_codes_are_registered() -> None:
    result = run_cli("examples/main.py", "-e", "hard_checks",
                     "-o", "examples/rules/split_by_topic/01_age_rules.yaml")
    assert result.returncode == 0, result.stderr
    assert "AGE_NEGATIVE" in result.stdout
    assert "EMAIL_MISSING_AT" not in result.stdout


def test_narrowing_suites_without_narrowing_rules_exits_one() -> None:
    """The default rule file names soft_checks codes, so loading only hard_checks
    is a load-time error rather than a silent skip."""

    result = run_cli("examples/main.py", "-e", "hard_checks")
    assert result.returncode == 1
    assert "unknown code 'EMAIL_MISSING_AT'" in result.stderr


def test_main_hard_only_registers_no_email_checks() -> None:
    out = run_cli("examples/main_hard_only.py").stdout
    assert out.startswith("Loaded suites: ['base', 'hard_checks']")
    assert "EMAIL" not in out


def test_main_hard_only_rejects_an_unknown_flag() -> None:
    """It takes no options, but still parses, so a mistyped flag is not ignored."""

    result = run_cli("examples/main_hard_only.py", "-v")
    assert result.returncode == 2
    assert "unrecognized arguments: -v" in result.stderr


def test_main_hard_only_has_help() -> None:
    result = run_cli("examples/main_hard_only.py", "--help")
    assert result.returncode == 0
    assert "loading only the hard_checks suite" in result.stdout


# --- reading a data file ----------------------------------------------------


def test_data_defaults_to_the_built_in_frame() -> None:
    assert main.parse_args([]).data is None


def test_key_column_defaults_to_id() -> None:
    assert main.parse_args([]).key_column == "id"


def test_no_registry_is_off_by_default() -> None:
    assert main.parse_args([]).no_registry is False


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
    assert "no such data file: no/such/file.csv" in result.stderr


def test_a_data_file_with_no_columns_exits_two(tmp_path: Any) -> None:
    path = tmp_path / "blank.csv"
    path.write_text("")
    result = run_cli("examples/main.py", "--data", str(path))
    assert result.returncode == 2
    assert "holds no columns to read" in result.stderr


def test_an_unknown_key_column_exits_two_and_lists_the_real_ones() -> None:
    result = run_cli("examples/main.py", "--data", "examples/data/customers.csv",
                     "--key-column", "customer_id")
    assert result.returncode == 2
    assert "--key-column 'customer_id' is not a column of the data" in result.stderr
    assert "id, name, age" in result.stderr


def test_the_key_column_chooses_what_labels_a_report_row() -> None:
    result = run_cli("examples/main.py", "--data", "examples/data/customers.csv",
                     "--key-column", "name", "--no-registry")
    assert result.returncode == 0
    assert "Alan Turing" in result.stdout
    assert "AGE_NEGATIVE" in result.stdout


def test_no_registry_prints_the_report_without_the_registry_tables() -> None:
    result = run_cli("examples/main.py", "--no-registry")
    assert result.returncode == 0
    assert "== Registry ==" not in result.stdout
    assert "== Registry vs overrides ==" not in result.stdout
    assert "== Failures ==" in result.stdout


def test_the_registry_tables_are_printed_without_the_flag() -> None:
    result = run_cli("examples/main.py")
    assert result.returncode == 0
    assert "== Registry ==" in result.stdout


def test_a_csv_row_that_is_entirely_blank_reports_the_base_suite_test() -> None:
    # Failures in the data are a report, not an error: the run exits 0 and the
    # reader decides. Only a broken *invocation* exits non-zero.
    result = run_cli("examples/main.py", "--data", "examples/data/customers.csv",
                     "--no-registry")
    assert result.returncode == 0
    assert "ROW_ALL_NULL" in result.stdout
