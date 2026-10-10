"""Unit checks: scoring a mutmut run from the `.meta` files it leaves."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from conftest import PROJECT_ROOT

pytestmark = pytest.mark.fast


def scorer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mutation_score", Path(PROJECT_ROOT) / "scripts" / "mutation_score.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_meta(directory: Path, name: str, codes: dict[str, int | None]) -> None:
    path = directory / "src" / "pkg" / f"{name}.py.meta"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"exit_code_by_key": codes}), encoding="utf-8")


def test_the_score_is_detected_over_total_across_every_file(tmp_path: Path) -> None:
    """Killed, caught by the type check and timed out all count as detected."""
    write_meta(tmp_path, "a", {"m1": 1, "m2": 0, "m3": 37})
    write_meta(tmp_path, "b", {"m4": 36, "m5": 1, "m6": 5, "m7": 3, "m8": 1})
    module = scorer()
    counts = module.tally(module.read_exit_codes(tmp_path))
    assert counts == {"killed": 4, "survived": 1, "caught by type check": 1,
                      "timeout": 1, "other": 1}
    assert module.score(counts) == 75.0


def test_at_the_floor_passes_and_below_it_fails(tmp_path: Path,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    write_meta(tmp_path, "a", {"m1": 1, "m2": 1, "m3": 1, "m4": 0})
    module = scorer()
    assert module.main(["--mutants", str(tmp_path), "--floor", "75"]) == 0
    assert module.main(["--mutants", str(tmp_path), "--floor", "75.1"]) == 1
    assert "mutation score below 75.1%" in capsys.readouterr().err


def test_an_unfinished_run_has_no_score(tmp_path: Path,
                                        capsys: pytest.CaptureFixture[str]) -> None:
    """A mutant still unchecked is an interrupted run; any score would be a guess."""
    write_meta(tmp_path, "a", {"m1": 1, "m2": None})
    assert scorer().main(["--mutants", str(tmp_path), "--floor", "0"]) == 2
    assert "1 mutant(s) not checked" in capsys.readouterr().err


def test_no_results_is_an_error_not_a_zero(tmp_path: Path) -> None:
    assert scorer().main(["--mutants", str(tmp_path / "missing")]) == 2
