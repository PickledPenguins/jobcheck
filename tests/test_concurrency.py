"""Concurrency: the registry is process-global, so contention is a real state.

Two things can reach the same registry at once: threads inside one process, and
separate processes each building their own. Both are ordinary ways to use this
library -- a web handler validating rows on a thread pool, a job runner opening
several runs -- and the guarantees are different for each:

- **Threads share the registry.** Validation must not mutate it, so many threads
  validating at once must agree with the same rows validated one at a time.
- **Processes do not share it.** Each builds its own from its own suites or
  files, and one process's loading says nothing about another's.

Loading a suite while another thread validates is *not* a supported state and is
not tested as one: registration mutates a global list, and the library says so.
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

from conftest import PROJECT_ROOT
from pandas_row_validation import collect_outcomes, root_cause, validate, validate_row

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


def test_threads_validating_rows_agree_with_one_thread(example_suites: None) -> None:
    df = frame(ROWS)
    rows = [row for _, row in df.iterrows()]
    expected = [[outcome.code for outcome in validate_row(row)] for row in rows]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        concurrent = list(pool.map(lambda row: [o.code for o in validate_row(row)], rows))

    assert concurrent == expected


def test_threads_do_not_disturb_each_others_root_causes(example_suites: None) -> None:
    df = frame(ROWS)
    rows = [row for _, row in df.iterrows()]
    expected = [root_cause(validate_row(row)) for row in rows]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        concurrent = list(pool.map(lambda row: root_cause(validate_row(row)), rows))

    assert concurrent == expected
    # Not all None: a test that only proves two empty lists are equal proves
    # nothing about the engine.
    assert any(cause is not None for cause in expected)


def test_whole_frames_validated_on_threads_agree_with_one_thread(example_suites: None) -> None:
    df = frame(100)
    expected = [trace.root_cause for trace in validate(df)]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        runs = list(pool.map(lambda _: [t.root_cause for t in validate(df)], range(WORKERS)))

    assert runs == [expected] * WORKERS


def test_validation_does_not_mutate_the_registry_under_threads(example_suites: None) -> None:
    from pandas_row_validation import registry as reg

    before = [(test.code, test.layer, test.default_enabled) for test in reg.TESTS]
    df = frame(100)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(lambda _: collect_outcomes(df), range(WORKERS)))

    assert [(t.code, t.layer, t.default_enabled) for t in reg.TESTS] == before


# --- separate processes -----------------------------------------------------

CHILD = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, {src!r})
    from pandas_row_validation import load_test_files, loaded_files, TESTS

    load_test_files([{path!r}])
    print(",".join(sorted(t.code for t in TESTS)))
    print(len(loaded_files()))
    """
)

TEST_FILE = textwrap.dedent(
    """
    from pandas_row_validation import PASS, Status, TestResult, test_group

    g = test_group()

    @g("{code}", "{code} failed")
    def rule(row):
        return PASS if row.get("value") == 1 else TestResult(Status.INVALID, {{}})
    """
)


def run_child(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", source], capture_output=True,
                          text=True, timeout=120, cwd=PROJECT_ROOT)


def test_two_processes_loading_the_same_file_do_not_share_a_registry(tmp_path: Path) -> None:
    """Each process registers the file itself; neither sees the other's tests."""

    src = str(Path(PROJECT_ROOT) / "src")
    left = tmp_path / "left.py"
    right = tmp_path / "right.py"
    left.write_text(TEST_FILE.format(code="LEFT_ONLY"))
    right.write_text(TEST_FILE.format(code="RIGHT_ONLY"))

    first = run_child(CHILD.format(src=src, path=str(left)))
    second = run_child(CHILD.format(src=src, path=str(right)))

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout.splitlines() == ["LEFT_ONLY", "1"]
    assert second.stdout.splitlines() == ["RIGHT_ONLY", "1"]


def test_many_processes_loading_the_same_file_all_succeed(tmp_path: Path) -> None:
    """No lock file, no shared cache: the loader writes nothing another process reads."""

    src = str(Path(PROJECT_ROOT) / "src")
    shared = tmp_path / "shared.py"
    shared.write_text(TEST_FILE.format(code="SHARED"))
    source = CHILD.format(src=src, path=str(shared))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run_child(source), range(4)))

    assert [r.returncode for r in results] == [0, 0, 0, 0]
    assert [r.stdout.splitlines() for r in results] == [["SHARED", "1"]] * 4
    # And no bytecode was written beside the caller's file, by any of them.
    assert not (tmp_path / "__pycache__").exists()


def test_a_second_process_is_unaffected_by_a_crashing_one(tmp_path: Path) -> None:
    src = str(Path(PROJECT_ROOT) / "src")
    broken = tmp_path / "broken.py"
    broken.write_text("raise RuntimeError('boom')\n")
    good = tmp_path / "good.py"
    good.write_text(TEST_FILE.format(code="GOOD"))

    failed = run_child(CHILD.format(src=src, path=str(broken)))
    survived = run_child(CHILD.format(src=src, path=str(good)))

    assert failed.returncode == 1
    assert "RuntimeError: boom" in failed.stderr
    assert survived.returncode == 0
    assert survived.stdout.splitlines() == ["GOOD", "1"]
