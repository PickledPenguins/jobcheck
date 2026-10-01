"""`docs/cli.md` against the three demo entry points, in both directions.

Each entry point's section has a heading for every flag and argument its parser
takes and for nothing else; the usage line it shows is the one argparse prints;
the exit-code table lists what the scripts can return and nothing more; the
run-file table is the script's own; and the null markers `--data` lists are the
ones pandas applies.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import bundle_main
import main
import run_from_config
from doc_files import ROOT

pytestmark = pytest.mark.fast

CLI = ROOT / "docs" / "cli.md"
ENTRY_POINTS: dict[str, ModuleType] = {
    "main": main, "bundle_main": bundle_main, "run_from_config": run_from_config,
}


def sections() -> dict[str, str]:
    """Each entry point's part of cli.md, from its `## examples/<name>.py` heading
    to the next `## ` heading, keyed by name."""

    parts = re.split(r"^## `examples/(\w+)\.py`\n", CLI.read_text(encoding="utf-8"),
                     flags=re.M)
    return {name: re.split(r"^## ", body, flags=re.M)[0]
            for name, body in zip(parts[1::2], parts[2::2])}


def parser_for(name: str, monkeypatch: Any) -> argparse.ArgumentParser:
    """The entry point's parser, named and sized as it is on an 80-column terminal.

    argparse wraps usage to the terminal's width, and from Python 3.14 colors it
    when asked to, so both are pinned rather than inherited from the test run.
    """

    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setenv("NO_COLOR", "1")
    parser: argparse.ArgumentParser = ENTRY_POINTS[name].build_parser()
    parser.prog = f"{name}.py"
    return parser


def real_arguments(parser: argparse.ArgumentParser) -> set[str]:
    """Every option string, and each positional argument's metavar."""

    names: set[str] = set()
    for action in parser._actions:  # the parser's only view of its own arguments
        names.update(action.option_strings or [str(action.metavar or action.dest)])
    return names


def documented_arguments(section: str) -> set[str]:
    """The first word of every backticked name in the section's `###` headings."""

    names: set[str] = set()
    for heading in re.findall(r"^### (.+)$", section, re.M):
        names.update(token.split()[0] for token in re.findall(r"`([^`]+)`", heading))
    return names


def test_cli_md_has_a_section_per_entry_point() -> None:
    assert sorted(sections()) == sorted(ENTRY_POINTS)


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_every_argument_has_a_section_and_every_section_an_argument(
    name: str, monkeypatch: Any,
) -> None:
    """Regression: only `examples/main.py` was compared, so the other two
    sections could document anything."""

    real = real_arguments(parser_for(name, monkeypatch))
    documented = documented_arguments(sections()[name])
    assert sorted(real - documented) == [], f"{name}.py: not documented in docs/cli.md"
    assert sorted(documented - real) == [], f"{name}.py: documented but not real"


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_the_usage_shown_is_the_usage_argparse_prints(name: str, monkeypatch: Any) -> None:
    """Regression: cli.md showed `[--rules PATH [PATH ...]]` for a flag argparse
    prints as `[--rules [PATH ...]]`, and wrapped where argparse does not."""

    usage = parser_for(name, monkeypatch).format_usage()
    blocks = re.findall(r"^```\n(.*?)^```", sections()[name], re.M | re.S)
    assert usage in blocks, f"docs/cli.md has no block holding exactly:\n{usage}"


def raised_exit_codes(path: Path) -> set[int]:
    """Every `raise SystemExit(<int>)` in one script."""

    source = ast.parse(path.read_text(encoding="utf-8"))
    return {
        int(node.exc.args[0].value)
        for node in ast.walk(source)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and getattr(node.exc.func, "id", None) == "SystemExit"
        and node.exc.args
        and isinstance(node.exc.args[0], ast.Constant)
        and isinstance(node.exc.args[0].value, int)
    }


def exit_code_section() -> str:
    """`## Exit codes` alone: the References table below it numbers its rows too."""

    text = CLI.read_text(encoding="utf-8")
    return text.split("\n## Exit codes\n", 1)[1].split("\n## ", 1)[0]


def test_every_exit_code_an_entry_point_can_return_is_documented() -> None:
    """The exit codes are the contract a scheduled job is written against, and all
    three entry points share one table; a code added without a row is invisible."""

    raised = set().union(*(raised_exit_codes(ROOT / "examples" / f"{name}.py")
                           for name in ENTRY_POINTS))
    # 0 for a clean run, 1 for an uncaught exception and 2 for a command line
    # argparse refuses belong to the interpreter and argparse, and are never
    # raised in the scripts' own source.
    expected = raised | {0, 1, 2}
    documented = {int(value) for value in
                  re.findall(r"^\| (\d+) \| ", exit_code_section(), re.M)}
    assert sorted(expected - documented) == [], "undocumented exit code(s)"
    assert sorted(documented - expected) == [], "documented exit code(s) that cannot happen"


def test_the_run_file_table_is_the_script_s_own() -> None:
    """Every table a run file can print, with exactly the options the script takes."""

    section = sections()["run_from_config"]
    rows = re.findall(r"^\| `(\w+)` \| ((?:`\w+`(?:, )?)+|none) \|", section, re.M)
    documented = {table: tuple(re.findall(r"`(\w+)`", options)) for table, options in rows}
    assert documented == run_from_config.TABLE_OPTIONS
    for key in run_from_config.RUN_KEYS:
        assert f"`{key}`" in section, f"the run-file key {key!r} is not documented"


def test_the_null_markers_listed_are_the_ones_pandas_reads_as_missing(tmp_path: Path) -> None:
    """`--data` turns pandas' own null markers into missing values; the list in
    cli.md is that set, each one really reads as missing, and the spellings the
    document says stay text do stay text."""

    from pandas._libs.parsers import STR_NA_VALUES

    section = sections()["main"]
    listed_sentence = re.search(r"null markers: (.*?)\.\s", section, re.S)
    text_sentence = re.search(r"Any other spelling \((.*?)\)\s+stays text", section, re.S)
    assert listed_sentence and text_sentence, "cli.md no longer lists the null markers"
    listed = re.findall(r"`([^`]+)`", listed_sentence.group(1))
    stays_text = re.findall(r"`([^`]+)`", text_sentence.group(1))
    assert set(listed) == set(STR_NA_VALUES) - {""}

    data = tmp_path / "markers.csv"
    values = [*listed, *stays_text]
    data.write_text("id,value\n" + "".join(f"{row},{value}\n" for row, value in enumerate(values)),
                    encoding="utf-8")
    read = main.load_frame(str(data))["value"].tolist()
    assert [value != value for value in read[:len(listed)]] == [True] * len(listed)
    assert read[len(listed):] == stays_text
