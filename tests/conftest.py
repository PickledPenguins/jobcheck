"""Shared fixtures.

The registry is process-global, so every check that registers or loads anything
takes ``fresh_registry`` and gets it back exactly as it found it. Without that,
check order would decide results.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Iterator

import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# src layout: importable without installing, which is what the entry points and
# the catalog rely on. `pip install -e .` puts it on the path the normal way.
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "examples"))
sys.path.insert(0, PROJECT_ROOT)

from jobcheck import registry as reg  # noqa: E402
from jobcheck import results as res  # noqa: E402


@pytest.fixture
def fresh_registry() -> Iterator[None]:
    """Give the check an empty registry and restore the previous one afterwards."""

    saved_tests = list(reg.CHECKS)
    saved_suites = set(reg._LOADED_SUITES)
    saved_modules = set(reg._REGISTERING_MODULES)
    saved_files = list(reg._LOADED_FILES)
    saved_order = reg._TOPO_ORDER
    saved_statuses = dict(res._EXTRA_STATUSES)

    reg.clear_registry()
    res.clear_extra_statuses()
    yield

    reg.clear_registry()
    res.clear_extra_statuses()
    reg.CHECKS.extend(saved_tests)
    reg._LOADED_SUITES.update(saved_suites)
    reg._REGISTERING_MODULES.update(saved_modules)
    reg._LOADED_FILES.extend(saved_files)
    reg._TOPO_ORDER = saved_order
    res._EXTRA_STATUSES.update(saved_statuses)


@pytest.fixture
def example_suites(fresh_registry: None) -> None:
    """A registry holding the shipped example checks (base + hard + soft)."""

    reg.load_suites(["hard_checks", "soft_checks"], package="example_suites")


def make_check(
    code: str,
    passes: bool = True,
    default_enabled: bool = True,
    depends_on: list[str] | None = None,
    calls: list[str] | None = None,
    status: int = res.Status.INVALID,
    comments: dict[str, Any] | None = None,
    raises: BaseException | None = None,
) -> None:
    """Register a throwaway check with a fixed outcome.

    ``calls`` is appended to on every invocation, which is how the checks tell
    "ran and passed" apart from "was skipped".
    """

    @reg.register_check(
        code=code,
        message=f"{code} failed",
        default_enabled=default_enabled,
        depends_on=depends_on,
    )
    def _test(row: "pd.Series[Any]") -> res.CheckResult:
        if calls is not None:
            calls.append(code)
        if raises is not None:
            raise raises
        if passes:
            return res.PASS
        return res.CheckResult(status, comments or {})


def one_row_report(
    comments: dict[str, Any] | None = None, message: str = "it failed"
) -> "pd.DataFrame":
    """A report with a single failure carrying the given message and comments.

    The shape several suites need to ask "what does this value do to the output?"
    -- rendered, escaped, wrapped -- without each of them growing its own copy.
    """

    from jobcheck import build_report, collect_outcomes
    from jobcheck.results import Status, CheckResult

    @reg.register_check(code="CELL", message=message)
    def check(row: "pd.Series[Any]") -> res.CheckResult:
        return CheckResult(Status.INVALID, comments or {})

    frame = pd.DataFrame([{"id": 1}])
    return build_report(collect_outcomes(frame), df=frame, key_column="id")


@dataclass
class CommandResult:
    """One subprocess run: streams kept separate so routing bugs cannot hide."""

    stdout: str
    stderr: str
    returncode: int


def run_cli(*args: str) -> CommandResult:
    """Run an entry point in a subprocess from the project root."""

    completed = subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return CommandResult(completed.stdout, completed.stderr, completed.returncode)
