"""Concurrency: the registry is process-global, so contention is a real state.

Two things can reach the same registry at once: threads inside one process, and
separate processes each building their own. Both are ordinary ways to use this
library -- a web handler validating rows on a thread pool, a job runner opening
several runs -- and the guarantees are different for each:

- **Threads share the registry.** Validation must not mutate it, so many threads
  validating at once must agree with the same rows validated one at a time.
- **Processes do not share it.** Each builds its own from its own files; the
  only thing they share is the disk, and loading writes nothing to it.

Loading from more than one thread, or while another thread validates, is *not* a
supported state and is not tested as one: registration mutates a global list and
nothing guards it, and the library says so.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import failures, first_cause, PROJECT_ROOT
from jobcheck import validate

pytestmark = pytest.mark.long

WORKERS = 8
ROWS = 400


def frame(rows: int) -> pd.DataFrame:
    """Rows whose failures differ, so a mixed-up result is visible."""

    return pd.DataFrame(
        {
            "age": [34, -5, 200, None] * (rows // 4),
            "email": ["a@b.com", "nope", "c@nodot", None] * (rows // 4),
            "start_date": ["2024-01-01"] * rows,
            "end_date": ["2024-02-01"] * rows,
        }
    )


def test_threads_validating_rows_agree_with_one_thread(example_checks: None) -> None:
    """Each row's failures and its root cause, the same whichever thread ran it."""

    def codes_and_cause(row: "pd.Series[Any]") -> tuple[list[str], str | None]:
        found = failures(row)
        return [outcome.code for outcome in found], first_cause(found)

    df = frame(ROWS)
    rows = [row for _, row in df.iterrows()]
    expected = [codes_and_cause(row) for row in rows]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        concurrent = list(pool.map(codes_and_cause, rows))

    assert concurrent == expected
    # Not all None: a check that only proves two empty lists are equal proves
    # nothing about the engine.
    assert any(cause is not None for _, cause in expected)


def test_whole_frames_validated_on_threads_agree_with_one_thread(example_checks: None) -> None:
    df = frame(100)
    expected = [first_cause(outcomes) for outcomes in validate(df)]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        runs = list(pool.map(
            lambda _: [first_cause(outcomes) for outcomes in validate(df)], range(WORKERS)))

    assert runs == [expected] * WORKERS


def test_validation_does_not_mutate_the_registry_under_threads(example_checks: None) -> None:
    from jobcheck import registry as reg

    before = [(check.code, check.layer, check.default_enabled) for check in reg._CHECKS]
    df = frame(100)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(lambda _: validate(df), range(WORKERS)))

    assert [(t.code, t.layer, t.default_enabled) for t in reg._CHECKS] == before


# --- separate processes -----------------------------------------------------

CHILD = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, {src!r})
    from jobcheck import load_checks, registry_table
    from jobcheck.registry import _LOADED_FILES

    load_checks([{path!r}])
    print(",".join(sorted(registry_table()["code"])))
    print(len(_LOADED_FILES))
    """
)

CHECK_FILE = textwrap.dedent(
    """
    from jobcheck import OK, Status, Verdict, register_check

    
    @register_check("{code}", "{code} failed")
    def rule(row):
        return OK if row.get("value") == 1 else Verdict(Status.INVALID, {{}})
    """
)


def run_child(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", source], capture_output=True,
                          text=True, timeout=120, cwd=PROJECT_ROOT)


def test_many_processes_loading_the_same_file_all_succeed(tmp_path: Path) -> None:
    """No lock file, no shared cache: the loader writes nothing another process reads."""

    src = str(Path(PROJECT_ROOT) / "src")
    shared = tmp_path / "shared.py"
    shared.write_text(CHECK_FILE.format(code="SHARED"))
    source = CHILD.format(src=src, path=str(shared))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run_child(source), range(4)))

    assert [r.returncode for r in results] == [0, 0, 0, 0]
    assert [r.stdout.splitlines() for r in results] == [["SHARED", "1"]] * 4
    # And no bytecode was written beside the caller's file, by any of them.
    assert not (tmp_path / "__pycache__").exists()

