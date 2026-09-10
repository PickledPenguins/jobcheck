#!/usr/bin/env python3
"""Profile the work the example catalog does, and print where the time went.

Timing says a run got slower; this says where. It runs the entry point in this
process, over the same data files the catalog uses, and reports the project's
own functions by cumulative time -- the standard library's are noise here, since
nothing in this repository can change how ``csv`` spends its time.

**What this cannot see:** the catalog itself runs every case as a subprocess, and
a profiler does not follow one. What is profiled here is the same code path
driven in-process, which is the closest honest measurement. Interpreter start-up,
imports and argument parsing per case are outside it entirely.

Not a gate. The assertions about time live in ``tests/test_perf.py``, which
compares against a baseline; a profile is a description, and turning one into a
threshold produces a flaky test and a number nobody trusts.

Usage: scripts/profile_examples.py [--rows N] [--save PATH]
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))

import main  # noqa: E402

DEFAULT_SAVE = ROOT / ".build" / "examples.prof"
# The runs worth profiling: the ones a user actually waits for.
RUNS = [
    ["--data", "examples/data/customers.csv", "--no-registry", "--summary"],
    ["--data", "examples/data/customers.csv", "-vv", "--include-skipped", "--summary"],
    ["--data", "examples/data/customers_large.csv", "--no-registry", "--summary"],
]


def project_rows(stats: pstats.Stats, limit: int = 15) -> list[tuple[str, int, float, float]]:
    """The project's own functions by cumulative time, biggest first."""

    rows = []
    for (filename, line, name), (_calls, primitive, total, cumulative, _callers) in \
            stats.stats.items():  # type: ignore[attr-defined]
        path = Path(filename)
        if not str(path).startswith(str(ROOT)) or "site-packages" in str(path):
            continue
        try:
            shown = path.relative_to(ROOT)
        except ValueError:  # pragma: no cover - defensive
            shown = path
        rows.append((f"{shown}:{line} {name}", primitive, total, cumulative))
    rows.sort(key=lambda row: row[3], reverse=True)
    return rows[:limit]


def run(argv: list[str], quiet: bool) -> None:
    """One entry-point run, with its output swallowed unless asked for."""

    stream = sys.stdout if not quiet else io.StringIO()
    saved, sys.stdout = sys.stdout, stream
    try:
        main.main(argv)
    finally:
        sys.stdout = saved


def main_(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile the example runs.")
    parser.add_argument("--save", default=str(DEFAULT_SAVE),
                        help=f"where to write the full profile (default {DEFAULT_SAVE})")
    parser.add_argument("--limit", type=int, default=15, help="rows to print (default 15)")
    args = parser.parse_args(argv)

    profiler = cProfile.Profile()
    for run_argv in RUNS:
        # Each run loads suites into the same registry; clearing between them
        # keeps the profile honest about what one run costs.
        from pandas_row_validation import clear_registry
        clear_registry()
        profiler.enable()
        run(run_argv, quiet=True)
        profiler.disable()

    stats = pstats.Stats(profiler)
    save = Path(args.save)
    save.parent.mkdir(parents=True, exist_ok=True)
    stats.dump_stats(str(save))

    print("== profile: the example runs, this project's functions by cumulative time ==")
    print(f"{'function':<66} {'calls':>8} {'tottime':>9} {'cumtime':>9}")
    for label, calls, total, cumulative in project_rows(stats, args.limit):
        print(f"{label:<66} {calls:>8} {total:>9.3f} {cumulative:>9.3f}")
    print(f"\nfull profile: {save.relative_to(ROOT)}  "
          f"(python3 -m pstats {save.relative_to(ROOT)})")
    print("not measured: the catalog's own subprocesses -- interpreter start-up, imports "
          "and\n              argument parsing per case are outside this profile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_())
