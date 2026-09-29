"""The run-file entry point, driven in this process.

`tests/examples/run_file/` runs it as a subprocess and compares its output byte
for byte; these reach every rejection of a malformed run file, the path
resolution, and the promise that a refused table prints nothing at all.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

import run_from_config
from conftest import PROJECT_ROOT

pytestmark = pytest.mark.fast

EXAMPLES = Path(PROJECT_ROOT) / "examples"


def write_run(tmp_path: Path, body: str) -> str:
    """A run file in *tmp_path* beside a setup file naming the shipped checks and
    rules by absolute path, so *body* can say `setup: setup.yaml`."""

    (tmp_path / "setup.yaml").write_text(
        f"checks: [{EXAMPLES / 'checks/all_checks.py'}]\n"
        f"rules: [{EXAMPLES / 'rules/error_rules.yaml'}]\n")
    (tmp_path / "data.csv").write_text(
        "id,name,age,email,start_date,end_date,source_system,record_type\n"
        "1,Ada,36,ada@example.com,2024-01-05,2024-06-30,MODERN,STREAM\n"
        "2,Bob,-4,bob@example.com,2024-01-05,2024-06-30,MODERN,STREAM\n")
    path = tmp_path / "run.yaml"
    path.write_text(body)
    return str(path)


BASE = "setup: setup.yaml\ndata: data.csv\n"


def refused(capsys: Any, run_file: str) -> str:
    """Run *run_file*, assert it exits 2 having printed nothing, return stderr."""

    with pytest.raises(SystemExit) as excinfo:
        run_from_config.main([run_file])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    return str(captured.err)


def test_the_shipped_run_prints_its_four_tables_in_order(fresh_registry: None,
                                                         capsys: Any) -> None:
    run_from_config.main([])
    out = capsys.readouterr().out
    headings = [line for line in out.splitlines() if line.startswith("== ")]
    assert headings == ["== Rules ==", "== Registry ==", "== Report ==", "== Summary =="]
    # The shipped file's column choices reached the report.
    report = out.split("== Report")[1].split("== Summary")[0]
    assert " name " in report.splitlines()[1]
    assert "comments" not in report and "detail" not in report
    assert "could_be_overridden_by" in out


def test_the_default_run_file_is_the_shipped_one() -> None:
    assert run_from_config.DEFAULT_RUN == os.path.join(PROJECT_ROOT, "examples/run.yaml")
    assert run_from_config.build_parser().parse_args([]).run_file == run_from_config.DEFAULT_RUN


def test_paths_resolve_against_the_run_file_not_the_working_directory(
    fresh_registry: None, capsys: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    run_file = write_run(tmp_path, BASE + "tables:\n  - table: report\n    key_column: id\n")
    monkeypatch.chdir(PROJECT_ROOT)
    run_from_config.main([os.path.relpath(run_file)])
    out = capsys.readouterr().out
    assert out.startswith("== Report ==")
    assert "AGE_NEGATIVE" in out


def test_a_table_may_repeat_with_different_options(fresh_registry: None, capsys: Any,
                                                   tmp_path: Path) -> None:
    run_file = write_run(tmp_path, BASE + (
        "tables:\n"
        "  - table: report\n"
        "  - table: report\n"
        "    format: csv\n"
        "    include: all\n"
        "    drop_columns: [comments]\n"))
    run_from_config.main([run_file])
    out = capsys.readouterr().out
    table, csv = out.split("\n\n", 1)
    assert table.startswith("== Report ==")
    # CSV gets no heading, and the second report's include reached build_report.
    assert csv.startswith("row,code,status,layer,outcome,message,detail,is_root_cause\n")
    assert csv.count("\n") > 3


def test_the_rules_table_carries_the_shadowed_rule_warning(fresh_registry: None,
                                                           capsys: Any, tmp_path: Path) -> None:
    run_from_config.main([write_run(tmp_path, BASE + "tables: [{table: rules}]\n")])
    out = capsys.readouterr().out
    assert out.startswith("== Rules ==")
    assert "warning: rule 'enable_legacy_integer_check' is overruled" in out


def test_a_rule_column_the_data_lacks_is_warned_on_stderr(fresh_registry: None,
                                                          capsys: Any, tmp_path: Path) -> None:
    run_file = write_run(tmp_path, BASE + "tables: [{table: summary}]\n")
    (tmp_path / "data.csv").write_text("id,age,email,start_date,end_date\n1,3,a@b.co,,\n")
    run_from_config.main([run_file])
    captured = capsys.readouterr()
    assert captured.out.startswith("== Summary")
    assert "warning:" in captured.err and "source_system" in captured.err


@pytest.mark.parametrize("body, message", [
    ("- setup\n", "a run file is a mapping of 'data', 'setup', 'tables', got list."),
    (BASE + "tables: [{table: summary}]\nextra: 1\n",
     "unknown key(s) 'extra'. A run file holds 'data', 'setup', 'tables'."),
    ("setup: setup.yaml\ntables: [{table: summary}]\n", "'data' is required."),
    ("setup: [setup.yaml]\ndata: data.csv\ntables: [{table: summary}]\n",
     "'setup' must be a path, got list."),
    (BASE + "tables: []\n", "'tables' must be a non-empty list: a run prints at least one."),
    (BASE + "tables: report\n", "'tables' must be a non-empty list: a run prints at least one."),
    (BASE + "tables: [report]\n",
     "table 1 must be a mapping with a 'table' key naming one of "
     "registry, rules, report, summary."),
    (BASE + "tables: [{table: summary}, {table: bogus}]\n",
     "table 2: unknown table 'bogus'. The tables are registry, rules, report, summary."),
    (BASE + "tables: [{table: summary, key_column: id}]\n",
     "table 1 (summary): unknown option(s) 'key_column'. It takes no options."),
    (BASE + "tables: [{table: rules, key_column: id}]\n",
     "table 1 (rules): unknown option(s) 'key_column'. "
     "It takes 'add_columns', 'drop_columns'."),
    (BASE + "tables: [{table: report, add_columns: name}]\n",
     "table 1 (report): 'add_columns' must be a list of column names. "
     "Write it as a list even for one column."),
    (BASE + "tables: [{table: report, key_column: [id]}]\n",
     "table 1 (report): 'key_column' must be a string, got list."),
    # Regression: a key YAML reads as a bool or an int beside a text key, and a
    # table name that is a list, raised TypeError -- a traceback and exit 1.
    (BASE + "tables: [{table: summary}]\non: 1\nextra: 2\n",
     "unknown key(s) True, 'extra'. A run file holds 'data', 'setup', 'tables'."),
    (BASE + "tables: [{table: [report]}]\n",
     "table 1: unknown table ['report']. The tables are registry, rules, report, summary."),
    (BASE + "tables: [{table: report, 1: x, bogus: y}]\n",
     "table 1 (report): unknown option(s) 1, 'bogus'. "
     "It takes 'add_columns', 'drop_columns', 'format', 'include', 'key_column'."),
])
def test_a_malformed_run_file_is_refused_before_anything_loads(
    fresh_registry: None, capsys: Any, tmp_path: Path, body: str, message: str
) -> None:
    run_file = write_run(tmp_path, body)
    assert refused(capsys, run_file) == f"error: {run_file}: {message}\n"


def test_a_missing_run_file_names_itself(capsys: Any, tmp_path: Path) -> None:
    run_file = str(tmp_path / "absent.yaml")
    err = refused(capsys, run_file)
    assert err == f"error: {run_file}: cannot read it: No such file or directory\n"


def test_a_key_given_twice_is_refused_rather_than_the_last_winning(
    capsys: Any, tmp_path: Path
) -> None:
    """A second `tables:` would otherwise drop every table the first one listed."""

    run_file = write_run(tmp_path, BASE + "tables: [{table: summary}]\n"
                                          "tables: [{table: registry}]\n")
    err = refused(capsys, run_file)
    assert err.startswith(
        f"error: {run_file}: not valid YAML: key 'tables' appears twice in one mapping, "
        "on lines 3 and 4; YAML would keep only the last")
    assert err.count("\n") == 1


def test_a_merge_key_and_an_unhashable_key_are_left_to_yaml(
    fresh_registry: None, capsys: Any, tmp_path: Path
) -> None:
    """`<<` may restate a key on purpose; a list as a key is refused by YAML itself."""

    merged = write_run(tmp_path, BASE + "tables:\n  - &t {table: summary}\n"
                                        "  - {<<: *t, table: summary}\n")
    run_from_config.main([merged])
    assert capsys.readouterr().out.count("== Summary ==") == 2
    err = refused(capsys, write_run(tmp_path, BASE + "? [a, b]\n: 1\ntables: []\n"))
    assert "found unhashable key" in err


def test_invalid_yaml_is_one_line(capsys: Any, tmp_path: Path) -> None:
    err = refused(capsys, write_run(tmp_path, "tables: [ {\n"))
    assert ": not valid YAML: " in err
    assert err.count("\n") == 1


@pytest.mark.parametrize("table, message", [
    ("{table: report, add_columns: [nope]}", "add_columns ['nope'] cannot be used for the report."),
    ("{table: report, format: xml}", "fmt must be 'table' or 'csv', got 'xml'."),
    ("{table: registry, add_columns: [bogus]}",
     "add_columns ['bogus'] cannot be used for the registry table."),
])
def test_an_option_the_library_refuses_prints_none_of_the_run(
    fresh_registry: None, capsys: Any, tmp_path: Path, table: str, message: str
) -> None:
    """The first table is fine and would print; the second is refused, and the
    run prints neither, naming the table by position."""

    run_file = write_run(tmp_path, BASE + f"tables: [{{table: summary}}, {table}]\n")
    err = refused(capsys, run_file)
    name = table.split(",")[0].split(": ")[1]
    assert err.startswith(f"error: {run_file}: table 2 ({name}): {message}")


def test_a_setup_file_the_library_refuses_raises_its_own_error(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The setup file is `load_setup`'s to judge, and its message is the one a
    reader of `docs/configuration.md` has seen, so it is not rewrapped."""

    run_file = write_run(tmp_path, "setup: absent.yaml\ndata: data.csv\n"
                                   "tables: [{table: summary}]\n")
    with pytest.raises(ValueError, match="No setup file at"):
        run_from_config.main([run_file])


def test_help_answers_and_a_second_argument_is_an_error(capsys: Any) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_from_config.main(["--help"])
    assert excinfo.value.code == 0
    assert "the run file" in capsys.readouterr().out

    with pytest.raises(SystemExit) as excinfo:
        run_from_config.main(["a.yaml", "b.yaml"])
    assert excinfo.value.code == 2
    assert "unrecognized arguments: b.yaml" in capsys.readouterr().err
