"""Interface tests: the CLI contract — flags, defaults, exit codes, routing."""

from __future__ import annotations

from typing import Any

import pytest

import main
from conftest import run_cli

pytestmark = pytest.mark.fast


# --- argument parsing -------------------------------------------------------


def test_defaults_when_no_flags_are_given() -> None:
    args = main.parse_args([])
    assert args.suites == ["hard_tests", "soft_tests"]
    assert args.overrides == ["examples/rules/error_overrides.yaml"]
    assert args.verbose == 0


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["-e", "hard_tests", "soft_tests"], id="multi-value"),
        pytest.param(["-e", "hard_tests", "-e", "soft_tests"], id="repeated"),
        pytest.param(["-e", "hard_tests", "-o", "x.yaml", "-e", "soft_tests"], id="interleaved"),
        pytest.param(["--suites", "hard_tests", "--suites", "soft_tests"], id="long-form"),
    ],
)
def test_suites_flatten_in_the_order_given(argv: list[str]) -> None:
    assert main.parse_args(argv).suites == ["hard_tests", "soft_tests"]


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["-o", "a.yaml", "b.yaml"], id="multi-value"),
        pytest.param(["-o", "a.yaml", "-o", "b.yaml"], id="repeated"),
        pytest.param(["--overrides", "a.yaml", "-e", "hard_tests", "--overrides", "b.yaml"],
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
    assert main.parse_args(["-e", "hard_tests"]).suites == ["hard_tests"]


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
    assert out.strip().endswith("root cause: ROW_ALL_NULL")


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
    assert result.stdout.startswith("Loaded suites: ['base', 'hard_tests', 'soft_tests']")
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
    result = run_cli("examples/main.py", "-e", "hard_tests",
                     "-o", "examples/rules/split_by_topic/01_age_rules.yaml")
    assert result.returncode == 0, result.stderr
    assert "AGE_NEGATIVE" in result.stdout
    assert "EMAIL_MISSING_AT" not in result.stdout


def test_narrowing_suites_without_narrowing_rules_exits_one() -> None:
    """The default rule file names soft_tests codes, so loading only hard_tests
    is a load-time error rather than a silent skip."""

    result = run_cli("examples/main.py", "-e", "hard_tests")
    assert result.returncode == 1
    assert "unknown code 'EMAIL_MISSING_AT'" in result.stderr


def test_main_hard_only_registers_no_email_checks() -> None:
    out = run_cli("examples/main_hard_only.py").stdout
    assert out.startswith("Loaded suites: ['base', 'hard_tests']")
    assert "EMAIL" not in out


def test_main_hard_only_rejects_an_unknown_flag() -> None:
    """It takes no options, but still parses, so a mistyped flag is not ignored."""

    result = run_cli("examples/main_hard_only.py", "-v")
    assert result.returncode == 2
    assert "unrecognized arguments: -v" in result.stderr


def test_main_hard_only_has_help() -> None:
    result = run_cli("examples/main_hard_only.py", "--help")
    assert result.returncode == 0
    assert "loading only the hard_tests suite" in result.stdout
