"""Regenerate the expected output of every catalog case.

A tool, not a gate: run it after an intended behavior change, then read the
diff before committing. A blind regeneration defeats the point of the catalog.

Usage: python3 scripts/regen_catalog.py [case-name-substring ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "tests"))

from catalog import CASE_FILES, case_dirs, run_case, stderr_tail  # noqa: E402


def main(argv: list[str]) -> int:
    written = 0
    for kind in ("examples", "failures"):
        for case in case_dirs(kind):
            name = str(case.relative_to(ROOT / "tests" / kind))
            if argv and not any(a in name for a in argv):
                continue
            result = run_case(case)
            stdout_file, stderr_file, exit_file = (case / f for f in CASE_FILES)
            if kind == "examples":
                stdout_file.write_text(result.stdout, encoding="utf-8")
                # An example only carries an expected_stderr.txt when it actually
                # writes to stderr; the check requires stderr to be empty otherwise.
                if result.stderr:
                    stderr_file.write_text(result.stderr, encoding="utf-8")
                elif stderr_file.exists():
                    stderr_file.unlink()
            else:
                stderr_file.write_text(stderr_tail(result.stderr), encoding="utf-8")
                if stdout_file.exists():
                    stdout_file.unlink()
            exit_file.write_text(f"{result.returncode}\n", encoding="utf-8")
            print(f"{kind}/{name}: exit {result.returncode}")
            written += 1
    print(f"{written} case(s) regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
