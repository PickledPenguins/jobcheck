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

Replacing the text is not enough on its own, because a table's column widths are
computed from the path *before* the substitution: a clone at a longer path
produces the same words with different padding, and the byte-for-byte comparison
fails for no reason anybody can act on. So a case is run through a symlink whose
path is a fixed length on every machine (:data:`STABLE_ROOT`), which makes the
widths a property of the catalog rather than of where the repository was cloned.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_FILES = ("expected_stdout.txt", "expected_stderr.txt", "exit_code")

# A fixed-length stand-in for the project root, so rendered paths -- and the
# column widths computed from them -- are the same on every clone. The user id is
# zero-padded rather than merely included, because two users on one machine need
# different links and the length has to stay constant. Recreated per run: it
# costs nothing and a stale link from a moved clone would be worse.
STABLE_ROOT = Path(tempfile.gettempdir()) / f"prv-catalog-root-{os.getuid():08d}"


@dataclass
class CaseResult:
    stdout: str
    stderr: str
    returncode: int


def case_dirs(kind: str) -> list[Path]:
    """Every case directory under tests/<kind>, sorted for a stable test order."""

    return sorted(p.parent for p in (ROOT / "tests" / kind).rglob("cmd"))


def stable_root() -> Path:
    """The symlink the cases run through, pointed at this clone.

    Falls back to the real root if the filesystem refuses symlinks, in which case
    a case that renders absolute paths compares its padding against whatever this
    machine produces -- the old behaviour, and the reason this exists.
    """

    try:
        if STABLE_ROOT.is_symlink() or STABLE_ROOT.exists():
            if STABLE_ROOT.is_symlink() and STABLE_ROOT.readlink() == ROOT:
                return STABLE_ROOT
            STABLE_ROOT.unlink()
        STABLE_ROOT.symlink_to(ROOT, target_is_directory=True)
        return STABLE_ROOT
    except OSError:  # pragma: no cover - no symlinks on this filesystem
        return ROOT


def run_case(case: Path) -> CaseResult:
    """Run one case's command from the project root, through the stable link."""

    command = shlex.split((case / "cmd").read_text(encoding="utf-8").strip())
    if command and command[0] == "python3":
        command[0] = sys.executable
    completed = subprocess.run(
        command, cwd=stable_root(), capture_output=True, text=True, timeout=120
    )
    return CaseResult(
        normalise(completed.stdout), normalise(completed.stderr), completed.returncode
    )


def normalise(text: str) -> str:
    """Replace whichever project root the run rendered, real or stable."""

    return text.replace(str(STABLE_ROOT), "<project>").replace(str(ROOT), "<project>")


def stderr_tail(text: str) -> str:
    """The last non-blank line of stderr: the message a user actually reads."""

    lines = [line for line in text.splitlines() if line.strip()]
    return (lines[-1] if lines else "") + "\n"
