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

from jobcheck import engine
from jobcheck import registry as reg
from jobcheck import report
from jobcheck import results as res
from registry_state import SavedRegistry

#: The clone this suite runs against. `src`, `examples` and the root itself are
#: on the path already: `pythonpath` in pyproject.toml puts them there before
#: this file is imported, which is why the imports above need no bootstrap under
#: them.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Hypothesis keeps its example database and its constants cache in .hypothesis
# in the working directory. There is no pyproject setting for it, only this
# environment variable, read the first time anything asks for the directory --
# so it is set here, before a test imports hypothesis. setdefault, because a
# caller who has pointed it somewhere meant it.
os.environ.setdefault(
    "HYPOTHESIS_STORAGE_DIRECTORY", os.path.join(PROJECT_ROOT, ".build", "hypothesis")
)


@pytest.fixture
def fresh_registry() -> Iterator[None]:
    """Give the check an empty registry and put the previous one back afterwards."""

    saved = SavedRegistry()
    reg.clear_registry()
    yield
    saved.restore()


#: The check files the shipped demo loads, as paths from the project root.
EXAMPLE_CHECK_FILES = [
    os.path.join(PROJECT_ROOT, "examples", "checks", name)
    for name in ("check_row_shape.py", "check_age.py", "check_dates.py", "check_email.py")
]


@pytest.fixture
def example_checks(fresh_registry: None) -> None:
    """A registry holding the shipped example checks."""

    reg.load_checks(EXAMPLE_CHECK_FILES)


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
    def _check(row: "pd.Series[Any]") -> res.CheckResult:
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

    @reg.register_check(code="CELL", message=message)
    def check(row: "pd.Series[Any]") -> res.CheckResult:
        return res.CheckResult(res.Status.INVALID, comments or {})

    frame = pd.DataFrame([{"id": 1}])
    return report.build_report(engine.validate(frame), df=frame, key_column="id")


@dataclass
class CommandResult:
    """One subprocess run: streams kept separate so routing bugs cannot hide."""

    stdout: str
    stderr: str
    returncode: int


def run_cli(*args: str, cwd: str = PROJECT_ROOT) -> CommandResult:
    """Run an entry point in a subprocess, from the project root by default.

    *cwd* is what a test uses to show that a run does not depend on where it
    was started: the entry point's own paths are anchored to its clone.
    """

    completed = subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return CommandResult(completed.stdout, completed.stderr, completed.returncode)


def first_cause(row_outcomes: list[Any]) -> str | None:
    """The first of a row's root causes, or None when it passed.

    The engine reports every failure at the shallowest failing layer, since two
    failures at one depth are two causes. Tests that want a single label per row
    take the first, which is what this says in one place rather than thirty.
    """

    causes = engine.root_causes(row_outcomes)
    return causes[0] if causes else None


def enabled_only(state: dict[str, Any]) -> dict[str, bool]:
    """Drop the reason from what resolve_enabled_state returns.

    The engine reports ``(enabled, reason)`` per code because an explanation
    prints the reason. A check that only cares which codes are on says so here
    rather than indexing ``[0]`` thirty times.
    """

    return {code: enabled for code, (enabled, _) in state.items()}
