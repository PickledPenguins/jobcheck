"""The demo entry point, driven in this process rather than through a shell.

`tests/test_interface_cli.py` runs the entry points as subprocesses, which is
what pins the contract a user meets. These call `main()` directly instead, which
is what reaches the branches a subprocess run cannot report on -- and makes the
report path, the explain path and every error exit measurable by coverage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import main
import main_hard_only
from conftest import PROJECT_ROOT

pytestmark = pytest.mark.fast

SMALL = "examples/data/customers.csv"
CLEAN = "examples/data/customers_clean.csv"


@pytest.fixture(autouse=True)
def in_the_project_root(monkeypatch: Any) -> None:
    """Every path in the entry point's defaults is relative to the project root."""

    monkeypatch.chdir(PROJECT_ROOT)


def run(capsys: Any, *argv: str) -> str:
    """Run the entry point and return stdout, discarding stderr.

    Tests that care about stderr call ``main.main`` themselves: one
    ``readouterr()`` consumes both streams, so a second call sees nothing.
    """

    main.main(list(argv))
    return capsys.readouterr().out


def test_the_default_run_prints_both_registry_tables(fresh_registry: None,
                                                     capsys: Any) -> None:
    out = run(capsys)
    assert "== Registry ==" in out
    assert "== Registry vs overrides ==" in out
    assert "== Failures ==" in out


def test_the_loaded_line_counts_the_rules_it_read(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys)
    assert "Loaded 3 override rule(s) from 1 file(s)" in out


def test_no_registry_prints_the_report_alone(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--no-registry")
    assert "== Registry ==" not in out
    assert "== Failures ==" in out


def test_verbosity_two_adds_the_by_rule_table(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "-vv")
    assert "== Override rules (by rule) ==" in out


def test_verbosity_one_does_not_add_the_by_rule_table(fresh_registry: None,
                                                      capsys: Any) -> None:
    assert "== Override rules (by rule) ==" not in run(capsys, "-v")


def test_summary_adds_the_per_test_counts(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--no-registry", "--summary")
    assert "== Summary ==" in out
    assert "Root cause of each failing row:" in out


def test_explain_prints_one_row_and_stops(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--explain", "1")
    assert out.startswith("Loaded suites:")
    assert "== Row 1 ==" in out
    assert "== Registry ==" not in out


def test_explain_past_the_end_exits_two(fresh_registry: None, capsys: Any) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--explain", "99"])
    assert raised.value.code == 2
    assert "outside the frame's 6 row(s)" in capsys.readouterr().err


def test_a_csv_file_is_validated_instead_of_the_demo_frame(fresh_registry: None,
                                                           capsys: Any) -> None:
    out = run(capsys, "--data", SMALL, "--no-registry")
    assert "AGE_NEGATIVE" in out
    assert "1004" in out


def test_a_clean_file_reports_no_failures(fresh_registry: None, capsys: Any) -> None:
    assert "No failures." in run(capsys, "--data", CLEAN, "--no-registry")


def test_a_missing_data_file_exits_two(fresh_registry: None, capsys: Any) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", "no/such/file.csv"])
    assert raised.value.code == 2
    assert "no such data file" in capsys.readouterr().err


def test_a_data_directory_exits_two_saying_so(fresh_registry: None, capsys: Any) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", "examples/data"])
    assert raised.value.code == 2
    assert "is a directory; name the CSV file inside it" in capsys.readouterr().err


def test_an_empty_data_file_exits_two(fresh_registry: None, capsys: Any,
                                      tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", str(empty)])
    assert raised.value.code == 2
    assert "holds no columns to read" in capsys.readouterr().err


def test_an_unreadable_data_file_exits_two_with_the_reason(fresh_registry: None,
                                                           capsys: Any,
                                                           tmp_path: Path) -> None:
    import os

    if os.geteuid() == 0:
        pytest.skip("root ignores the permission bits this test sets")
    locked = tmp_path / "locked.csv"
    locked.write_text("id\n1\n")
    locked.chmod(0)
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", str(locked)])
    assert raised.value.code == 2
    assert "cannot read" in capsys.readouterr().err


def test_a_file_that_is_not_csv_exits_two(fresh_registry: None, capsys: Any,
                                          tmp_path: Path) -> None:
    ragged = tmp_path / "ragged.csv"
    ragged.write_text('id,age\n1,2\n"unclosed,3,4,5\n6,7,8,9,10\n')
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", str(ragged)])
    assert raised.value.code == 2
    assert "not readable as CSV" in capsys.readouterr().err


def test_an_unknown_key_column_exits_two_listing_the_columns(fresh_registry: None,
                                                             capsys: Any) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", SMALL, "--key-column", "nope"])
    assert raised.value.code == 2
    assert "available: id, name, age" in capsys.readouterr().err


def test_a_report_file_is_written_and_announced(fresh_registry: None, capsys: Any,
                                                tmp_path: Path) -> None:
    target = tmp_path / "report.csv"
    out = run(capsys, "--data", SMALL, "--no-registry", "--report", "csv",
              "--report-file", str(target))
    assert f"wrote {target}" in out
    assert "== Failures ==" not in out
    assert target.read_text().startswith("row,code,status")


def test_a_report_file_takes_the_format_the_report_flag_names(fresh_registry: None,
                                                              capsys: Any,
                                                              tmp_path: Path) -> None:
    """--report-file does not infer the format from the extension.

    A file named .csv holding a rendered table is a surprise, but the flag that
    decides it is --report and there is only one of it: the format is the same
    whether the report is printed or written.
    """

    target = tmp_path / "report.csv"
    run(capsys, "--data", SMALL, "--no-registry", "--report-file", str(target))
    written = target.read_text()
    assert written.startswith("row      | code")  # the table, in a file named .csv
    assert "," not in written.splitlines()[0]


def test_a_report_file_that_cannot_be_written_exits_two(fresh_registry: None,
                                                        capsys: Any,
                                                        tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", CLEAN, "--no-registry",
                   "--report-file", str(tmp_path / "missing" / "report.csv")])
    assert raised.value.code == 2
    assert "cannot write" in capsys.readouterr().err


def test_a_rule_naming_a_column_the_data_lacks_warns_on_stderr(fresh_registry: None,
                                                               capsys: Any,
                                                               tmp_path: Path) -> None:
    """The rule still loads: it simply cannot fire, which is a warning, not an error."""

    rules = tmp_path / "rules.yaml"
    rules.write_text("- name: needs_a_missing_column\n  action: disable\n"
                     "  codes: [AGE_NEGATIVE]\n  match:\n"
                     "    - column: not_a_column\n      pattern: 'x'\n")
    main.main(["--data", SMALL, "--no-registry", "-o", str(rules)])
    captured = capsys.readouterr()
    assert "AGE_NEGATIVE" in captured.out
    assert "not_a_column" in captured.err


def test_data_columns_appear_next_to_the_row_key(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--data", SMALL, "--no-registry", "--data-columns", "name", "region")
    assert "name" in out and "region" in out
    assert "Alan Turing" in out


def test_include_skipped_names_the_prerequisite(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--data", SMALL, "--no-registry", "--include-skipped")
    assert "prerequisite did not pass" in out


def test_the_csv_report_format_is_comma_separated(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--data", SMALL, "--no-registry", "--report", "csv")
    assert "row,code,status,layer,suite,outcome,message,comments,is_root_cause" in out


def test_the_second_entry_point_loads_only_its_own_suite(fresh_registry: None,
                                                         capsys: Any) -> None:
    main_hard_only.main([])
    out = capsys.readouterr().out
    assert "hard_tests" in out
    assert "EMAIL_" not in out
