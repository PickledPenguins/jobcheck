"""Unit checks: `scripts/regen_docs.py` rewrites a shown output with what its block prints."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from conftest import PROJECT_ROOT

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def regen() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "regen_docs", Path(PROJECT_ROOT) / "scripts" / "regen_docs.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def document(tmp_path: Path, code: str, shown: str) -> Path:
    """A document holding one Python block, its shown output, and a listing that is
    not an output because a sentence separates it from the code."""

    path = tmp_path / "doc.md"
    path.write_text(f"# A document\n\nProse.\n\n```python\n{code}```\n\n```\n{shown}```\n\n"
                    "A listing, not an output:\n\n```\nkept as it is\n```\n", encoding="utf-8")
    return path


PRINTS = 'from jobcheck import Status\n\nprint(Status.INVALID.name)\n'


def test_a_stale_output_is_rewritten_and_nothing_else_changes(
    regen: ModuleType, fresh_registry: None, tmp_path: Path, capsys: Any,
) -> None:
    path = document(tmp_path, PRINTS, "out of date\n")
    expected = path.read_text(encoding="utf-8").replace("out of date\n", "INVALID\n")
    assert regen.regenerate([path]) == 0
    assert path.read_text(encoding="utf-8") == expected
    assert capsys.readouterr().out == "doc.md:6: rewritten\n"


def test_an_output_that_is_already_right_is_left_alone(
    regen: ModuleType, fresh_registry: None, tmp_path: Path, capsys: Any,
) -> None:
    path = document(tmp_path, PRINTS, "INVALID\n")
    before = path.read_text(encoding="utf-8")
    assert regen.regenerate([path]) == 0
    assert path.read_text(encoding="utf-8") == before
    assert capsys.readouterr().out == ""


def test_a_block_that_raises_is_named_and_its_output_kept(
    regen: ModuleType, fresh_registry: None, tmp_path: Path, capsys: Any,
) -> None:
    path = document(tmp_path, 'raise ValueError("broken example")\n', "whatever it was\n")
    before = path.read_text(encoding="utf-8")
    assert regen.regenerate([path]) == 1
    assert path.read_text(encoding="utf-8") == before
    assert capsys.readouterr().err == "doc.md:6: raised ValueError: broken example\n"


def test_a_block_runs_in_the_world_the_documents_assume(
    regen: ModuleType, fresh_registry: None, tmp_path: Path,
) -> None:
    """The demo frame and its outcomes are there, as they are for the docs test."""

    path = document(tmp_path, "print(len(df), len(outcomes), len(rules))\n", "stale\n")
    assert regen.regenerate([path]) == 0
    assert "```\n6 6 3\n```" in path.read_text(encoding="utf-8")


def test_a_name_on_the_command_line_selects_the_documents(
    regen: ModuleType, monkeypatch: Any,
) -> None:
    """Against a stand-in list, not docs/: mutmut's copy of the tree has no docs/."""

    chosen: list[list[Path]] = []

    def record(documents: list[Path]) -> int:
        chosen.append(documents)
        return 0

    monkeypatch.setattr(regen, "regenerate", record)
    monkeypatch.setattr(regen, "DOCS", [Path("docs/cli.md"), Path("docs/reporting.md")])
    assert regen.main(["reporting"]) == 0
    assert chosen[0] == [Path("docs/reporting.md")]
    assert regen.main([]) == 0
    assert chosen[1] == [Path("docs/cli.md"), Path("docs/reporting.md")]


def test_a_name_matching_no_document_is_refused(
    regen: ModuleType, monkeypatch: Any, capsys: Any,
) -> None:
    """Exit 0 having done nothing is how a typo'd name passed for success."""

    monkeypatch.setattr(regen, "regenerate", lambda documents: pytest.fail("ran"))
    monkeypatch.setattr(regen, "DOCS", [Path("docs/cli.md"), Path("docs/reporting.md")])
    assert regen.main(["reporting", "nosuchdoc"]) == 2
    assert capsys.readouterr().err == (
        "regen_docs: no document under docs/ matches nosuchdoc "
        "(documents: cli.md, reporting.md)\n")
