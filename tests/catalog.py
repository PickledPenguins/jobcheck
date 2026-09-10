"""Shared machinery for the example and failure catalogs.

A case is a directory holding:

    cmd                   the command, run from the project root
    README.md             what it demonstrates
    expected_stdout.txt   examples: stdout, compared byte for byte
    expected_stderr.txt   failures: the final traceback line, compared exactly
    exit_code             the expected exit status

Failure cases compare only the last line of stderr -- the exception type and
message the user actually reads. The frames above it name absolute paths and
line numbers that change with any edit, so they are normalised away.

One more normalisation applies to both kinds: the absolute project root is
replaced by ``<project>``, so ``source_file`` columns in ``-vv`` output do not
pin the catalog to one machine.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_FILES = ("expected_stdout.txt", "expected_stderr.txt", "exit_code")


@dataclass
class CaseResult:
    stdout: str
    stderr: str
    returncode: int


def case_dirs(kind: str) -> list[Path]:
    """Every case directory under tests/<kind>, sorted for a stable test order."""

    return sorted(p.parent for p in (ROOT / "tests" / kind).rglob("cmd"))


def run_case(case: Path) -> CaseResult:
    """Run one case's command from the project root."""

    command = shlex.split((case / "cmd").read_text(encoding="utf-8").strip())
    if command and command[0] == "python3":
        command[0] = sys.executable
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    return CaseResult(
        normalise(completed.stdout), normalise(completed.stderr), completed.returncode
    )


def normalise(text: str) -> str:
    """Replace the absolute project root, which differs on every machine."""

    return text.replace(str(ROOT), "<project>")


def stderr_tail(text: str) -> str:
    """The last non-blank line of stderr: the message a user actually reads."""

    lines = [line for line in text.splitlines() if line.strip()]
    return (lines[-1] if lines else "") + "\n"
