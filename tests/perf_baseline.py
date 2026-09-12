"""The performance baseline: measured on this machine, compared against later.

A baseline from another machine means nothing, so the file is gitignored and
written by the first ``./tests/run-tests.sh perf`` on a clone. What it stores per
measurement is the median of several repeats *and* the spread between them,
because the spread is what decides an honest threshold: a machine whose repeats
move 30% cannot police a 10% regression.

The gate is therefore ``median > baseline_median * (1 + tolerance)`` where the
tolerance is the measured noise, floored so a very quiet machine does not end up
with a hair trigger, and capped so a very noisy one still catches something.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

BASELINE = Path(__file__).resolve().parent.parent / ".build" / "perf-baseline.json"

#: Never police a regression smaller than this, whatever the machine's noise.
MIN_TOLERANCE = 0.35
#: Never tolerate more than this, however noisy the machine: past here the
#: measurement is not worth keeping at all.
MAX_TOLERANCE = 1.50
#: Repeats per measurement. Enough for a median and a spread; few enough that
#: the perf run stays in the tens of seconds.
REPEATS = 5


def machine() -> dict[str, str]:
    """What the numbers are numbers *for*: a baseline is not portable."""

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
    }


def measure(work: Callable[[], Any], repeats: int = REPEATS) -> dict[str, float]:
    """Median and relative spread of *repeats* runs of *work*."""

    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        work()
        samples.append(time.perf_counter() - started)
    median = statistics.median(samples)
    spread = (max(samples) - min(samples)) / median if median else 0.0
    return {"median": median, "spread": spread, "repeats": float(repeats)}


def tolerance(entry: dict[str, float]) -> float:
    """How much slower than the baseline is still noise on this machine."""

    return min(max(entry.get("spread", 0.0) * 2, MIN_TOLERANCE), MAX_TOLERANCE)


def load() -> dict[str, Any]:
    """The stored baseline, or an empty one on a machine that has none yet."""

    if not BASELINE.exists():
        return {"machine": machine(), "measurements": {}}
    stored = json.loads(BASELINE.read_text(encoding="utf-8"))
    if stored.get("machine") != machine():
        # A changed interpreter or host makes every stored number meaningless.
        return {"machine": machine(), "measurements": {}}
    return stored


def save(data: dict[str, Any]) -> None:
    BASELINE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compare(name: str, work: Callable[[], Any]) -> tuple[str, float, float, float]:
    """Measure *name*, record it if new, and return (verdict, median, limit, ratio).

    The verdict is ``"recorded"`` the first time and ``"compared"`` afterwards,
    so a fresh clone reports what it stored rather than passing silently.
    """

    data = load()
    now = measure(work)
    stored = data["measurements"].get(name)
    if stored is None:
        data["measurements"][name] = now
        save(data)
        return "recorded", now["median"], float("inf"), 0.0
    limit = stored["median"] * (1 + tolerance(stored))
    ratio = now["median"] / stored["median"] if stored["median"] else 0.0
    return "compared", now["median"], limit, ratio
