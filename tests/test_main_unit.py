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
    assert "== Registry" in out
    assert "== Report" in out


def test_the_loaded_line_counts_the_rules_it_read(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys)
    assert "Loaded 3 rule(s) from 1 file(s)" in out


def test_summary_adds_the_per_check_counts(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--summary")
    assert "== Summary" in out
    assert "root_cause_rows" in out


def test_explain_prints_one_row_and_stops(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--explain", "1")
    assert "== Row explanation ==" in out
    assert "== Registry" not in out


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
    assert "== Report ==\n(empty)" in run(capsys, "--data", CLEAN)


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
    rules.write_text("- name: needs_a_missing_column\n  message: \"why the rule exists\"\n  action: disable\n"
                     "  codes: [AGE_NEGATIVE]\n  match:\n"
                     "    - column: not_a_column\n      pattern: 'x'\n")
    main.main(["--data", SMALL, "--rules", str(rules)])
    captured = capsys.readouterr()
    assert "AGE_NEGATIVE" in captured.out
    assert "not_a_column" in captured.err


def test_rules_with_no_paths_loads_none(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--rules")
    assert "Loaded 0 rule(s) from 0 file(s)" in out
    # Row 4 is qa@internal.test, whose email checks the default rule file
    # switches off; with no rules the demo frame fails nothing for it either,
    # so the difference that shows is the registry's rule column being absent.
    assert "(disable)" not in out.split("== Registry")[1].split("== Report")[0]


def test_the_csv_report_format_is_comma_separated(fresh_registry: None, capsys: Any) -> None:
    out = run(capsys, "--data", SMALL, "--report", "csv")
    assert "row,code,status,layer,outcome,message,detail,comments,is_root_cause" in out


def test_the_rules_table_prints_one_row_per_rule_not_per_code(fresh_registry: None,
                                                              capsys: Any) -> None:
    """The registry table below it is one row per code, so a rule touching two
    codes is two lines there and one line here."""

    out = run(capsys, "--rules-table")
    rules = out.split("== Rules")[1].split("== Registry")[0]
    assert "codes_hit_count" in rules
    assert rules.count("suppress_email_checks_for_test_accounts") == 1
    # The same rule, twice in the registry table: once per code it can reach.
    registry = out.split("== Registry")[1].split("== Report")[0]
    assert registry.count("suppress_email_checks_for_test_accounts") == 2


def test_the_rules_table_is_empty_when_no_rules_were_loaded(fresh_registry: None,
                                                            capsys: Any) -> None:
    out = run(capsys, "--rules-table", "--rules")
    rules = out.split("== Rules")[1].split("== Registry")[0]
    assert "enable_legacy_integer_check" not in rules


def test_write_puts_the_printed_report_in_a_file(fresh_registry: None, capsys: Any,
                                                 tmp_path: Path) -> None:
    """The file and the terminal come from one report frame, so a difference
    between them would be a defect rather than a formatting choice."""

    target = tmp_path / "report.csv"
    out = run(capsys, "--data", SMALL, "--report", "csv", "--write", str(target))
    written = target.read_text(encoding="utf-8")
    assert written.startswith(
        "row,code,status,layer,outcome,message,detail,comments,is_root_cause")
    assert f"Wrote {written.count(chr(10)) - 1} report row(s) to {target}" in out


def test_write_uses_the_report_format_rather_than_the_extension(fresh_registry: None,
                                                                capsys: Any,
                                                                tmp_path: Path) -> None:
    """`--report table --write out.csv` writes the bordered table. The flag
    chooses the format; the file name is just a name."""

    target = tmp_path / "report.csv"
    run(capsys, "--data", SMALL, "--write", str(target))
    assert target.read_text(encoding="utf-8").startswith("== Report ==\nrow ")


def test_write_replaces_a_file_that_is_already_there(fresh_registry: None, capsys: Any,
                                                     tmp_path: Path) -> None:
    target = tmp_path / "report.csv"
    target.write_text("stale\n" * 200, encoding="utf-8")
    run(capsys, "--data", CLEAN, "--report", "csv", "--write", str(target))
    assert "stale" not in target.read_text(encoding="utf-8")


def test_write_into_a_missing_directory_exits_two_before_doing_the_work(
    fresh_registry: None, capsys: Any, tmp_path: Path
) -> None:
    """Checked up front: validating the frame and only then finding there is
    nowhere to put the report wastes the run and prints what the file was
    supposed to hold."""

    target = tmp_path / "nope" / "report.csv"
    with pytest.raises(SystemExit) as excinfo:
        main.main(["--write", str(target)])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert f"error: cannot write {target}: no directory {tmp_path / 'nope'}" in captured.err
    assert captured.out == ""


def test_a_write_that_fails_at_the_last_moment_still_exits_two(
    fresh_registry: None, capsys: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    """The up-front check cannot see everything -- a directory can go away, a
    disk can fill -- so the write itself stays guarded."""

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(main.Path, "write_text", refuse)
    target = tmp_path / "report.csv"
    with pytest.raises(SystemExit) as excinfo:
        main.main(["--data", CLEAN, "--write", str(target)])
    assert excinfo.value.code == 2
    assert "No space left on device" in capsys.readouterr().err
