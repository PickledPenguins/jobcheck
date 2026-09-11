"""The demo entry point, driven in this process rather than through a shell.

`tests/test_interface_cli.py` runs the entry point as a subprocess, which is
what pins the contract a user meets. These call `main()` directly instead, which
is what reaches the branches a subprocess run cannot report on -- and makes the
report path, the explain path and every error exit measurable by coverage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import main
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

    Checks that care about stderr call ``main.main`` themselves: one
    ``readouterr()`` consumes both streams, so a second call sees nothing.
    """

    main.main(list(argv))
    return capsys.readouterr().out


def test_the_default_run_prints_the_registry_and_the_report(fresh_registry: None,
                                                            capsys: Any) -> None:
    out = run(capsys)
    assert "== Registry ==" in out
    assert "== Failures ==" in out


def test_the_loaded_line_counts_the_rules_it_read(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys)
    assert "Loaded 3 override rule(s) from 1 file(s)" in out


def test_summary_adds_the_per_check_counts(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--summary")
    assert "== Summary ==" in out
    assert "Root cause of each failing row:" in out


def test_explain_prints_one_row_and_stops(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--explain", "1")
    assert "== Row 1 ==" in out
    assert "== Registry ==" not in out


def test_explain_past_the_end_exits_two(fresh_registry: None, capsys: Any) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--explain", "99"])
    assert raised.value.code == 2
    assert "outside the frame's 6 row(s)" in capsys.readouterr().err


def test_a_csv_file_is_validated_instead_of_the_demo_frame(fresh_registry: None,
                                                           capsys: Any) -> None:
    out = run(capsys, "--data", SMALL)
    assert "AGE_NEGATIVE" in out
    assert "1004" in out


def test_a_clean_file_reports_no_failures(fresh_registry: None, capsys: Any) -> None:
    assert "No failures." in run(capsys, "--data", CLEAN)


def test_a_missing_data_file_exits_two(fresh_registry: None, capsys: Any) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", "no/such/file.csv"])
    assert raised.value.code == 2
    assert "cannot read no/such/file.csv" in capsys.readouterr().err


def test_a_data_directory_exits_two(fresh_registry: None, capsys: Any) -> None:
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", "examples/data"])
    assert raised.value.code == 2
    assert "cannot read examples/data" in capsys.readouterr().err


def test_an_empty_data_file_exits_two(fresh_registry: None, capsys: Any,
                                      tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", str(empty)])
    assert raised.value.code == 2
    assert "cannot read" in capsys.readouterr().err


def test_a_file_that_is_not_csv_exits_two(fresh_registry: None, capsys: Any,
                                          tmp_path: Path) -> None:
    ragged = tmp_path / "ragged.csv"
    ragged.write_text('id,age\n1,2\n"unclosed,3,4,5\n6,7,8,9,10\n')
    with pytest.raises(SystemExit) as raised:
        main.main(["--data", str(ragged)])
    assert raised.value.code == 2
    assert "cannot read" in capsys.readouterr().err


def test_a_rule_naming_a_column_the_data_lacks_warns_on_stderr(fresh_registry: None,
                                                               capsys: Any,
                                                               tmp_path: Path) -> None:
    """The rule still loads: it simply cannot fire, which is a warning, not an error."""

    rules = tmp_path / "rules.yaml"
    rules.write_text("- name: needs_a_missing_column\n  action: disable\n"
                     "  codes: [AGE_NEGATIVE]\n  match:\n"
                     "    - column: not_a_column\n      pattern: 'x'\n")
    main.main(["--data", SMALL, "--rules", str(rules)])
    captured = capsys.readouterr()
    assert "AGE_NEGATIVE" in captured.out
    assert "not_a_column" in captured.err


def test_the_csv_report_format_is_comma_separated(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--data", SMALL, "--report", "csv")
    assert "row,code,status,layer,outcome,message,comments,is_root_cause" in out
