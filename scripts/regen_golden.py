"""Regenerate the golden report files under tests/golden/.

A tool, not a gate: run it after an intended change to the report, then read the
diff before committing. A blind regeneration defeats the point of a golden file.

Usage: python3 scripts/regen_golden.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from golden_fixture import render_all, write_golden  # noqa: E402


def main() -> int:
    for name, text in render_all().items():
        write_golden(name, text)
        print(f"tests/golden/{name}: {len(text)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
