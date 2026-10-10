"""Score a finished mutmut run, and fail below a floor.

mutmut 3 writes one `.meta` file per source file under `mutants/`, mapping each
mutant to the exit code its test run ended with. This reads them all, prints the
tally, and compares the score against `--floor`. The score is detected over
total, where a mutant is detected when the tests killed it, the type check
caught it, or it timed out.

Usage: python3 scripts/mutation_score.py [--floor PERCENT] [--mutants DIR]

Exit codes: 0 at or above the floor; 1 below it; 2 no results at all, or a mutant
still unchecked (an interrupted run has no score, and passing it would be a guess).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

# mutmut 3.5's status_by_exit_code, reduced to what the score needs. Anything not
# listed (no tests, skipped, suspicious, a segfault) counts against the score.
KILLED = {1, 3}
TYPE_CHECK = {37}
TIMEOUT = {24, -24, 36, 152, 255}
SURVIVED = {0}


def status(exit_code: int | None) -> str:
    """One mutant's result, as the score counts it."""
    if exit_code is None:
        return "not checked"
    if exit_code in KILLED:
        return "killed"
    if exit_code in TYPE_CHECK:
        return "caught by type check"
    if exit_code in TIMEOUT:
        return "timeout"
    if exit_code in SURVIVED:
        return "survived"
    return "other"


def tally(exit_codes: Iterable[int | None]) -> Counter[str]:
    return Counter(status(code) for code in exit_codes)


def detected(counts: Counter[str]) -> int:
    return counts["killed"] + counts["caught by type check"] + counts["timeout"]


def score(counts: Counter[str]) -> float:
    """Detected mutants as a percentage of all of them."""
    total = sum(counts.values())
    return 100.0 * detected(counts) / total if total else 0.0


def read_exit_codes(mutants: Path) -> list[int | None]:
    codes: list[int | None] = []
    for meta in sorted(mutants.rglob("*.meta")):
        codes.extend(json.loads(meta.read_text(encoding="utf-8"))["exit_code_by_key"].values())
    return codes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score a finished mutmut run.")
    parser.add_argument("--floor", type=float, default=0.0, metavar="PERCENT")
    parser.add_argument("--mutants", type=Path, default=Path("mutants"), metavar="DIR")
    args = parser.parse_args(argv)

    counts = tally(read_exit_codes(args.mutants))
    total = sum(counts.values())
    if not total:
        print(f"error: no mutmut results under {args.mutants}/", file=sys.stderr)
        return 2
    print(f"{total} mutants: {counts['killed']} killed, {counts['caught by type check']} "
          f"caught by type check, {counts['timeout']} timed out, "
          f"{counts['survived']} survived, {counts['other']} other")
    if counts["not checked"]:
        print(f"error: {counts['not checked']} mutant(s) not checked. The run did not "
              "finish, so there is no score", file=sys.stderr)
        return 2
    result = score(counts)
    print(f"mutation score {result:.1f}% (floor {args.floor:g}%)")
    if result < args.floor:
        print(f"mutation score below {args.floor:g}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
