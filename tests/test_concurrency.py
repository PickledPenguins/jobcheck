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

import pandas as pd
import pytest

from conftest import first_cause, PROJECT_ROOT
from jobcheck import validate, validate_row

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
    df = frame(ROWS)
    rows = [row for _, row in df.iterrows()]
    expected = [[outcome.code for outcome in validate_row(row)] for row in rows]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        concurrent = list(pool.map(lambda row: [o.code for o in validate_row(row)], rows))

    assert concurrent == expected


def test_threads_do_not_disturb_each_others_root_causes(example_checks: None) -> None:
    df = frame(ROWS)
    rows = [row for _, row in df.iterrows()]
    expected = [first_cause(validate_row(row)) for row in rows]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        concurrent = list(pool.map(lambda row: first_cause(validate_row(row)), rows))

    assert concurrent == expected
    # Not all None: a check that only proves two empty lists are equal proves
    # nothing about the engine.
    assert any(cause is not None for cause in expected)


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


def test_two_processes_loading_the_same_file_do_not_share_a_registry(tmp_path: Path) -> None:
    """Each process registers the file itself; neither sees the other's checks."""

    src = str(Path(PROJECT_ROOT) / "src")
    left = tmp_path / "left.py"
    right = tmp_path / "right.py"
    left.write_text(CHECK_FILE.format(code="LEFT_ONLY"))
    right.write_text(CHECK_FILE.format(code="RIGHT_ONLY"))

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
    shared.write_text(CHECK_FILE.format(code="SHARED"))
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
    good.write_text(CHECK_FILE.format(code="GOOD"))

    failed = run_child(CHILD.format(src=src, path=str(broken)))
    survived = run_child(CHILD.format(src=src, path=str(good)))

    assert failed.returncode == 1
    assert "RuntimeError: boom" in failed.stderr
    assert survived.returncode == 0
    assert survived.stdout.splitlines() == ["GOOD", "1"]


def test_two_threads_loading_take_turns(fresh_registry: None, tmp_path: Path) -> None:
    """Thread A loads a file naming an unregistered prerequisite; thread B starts
    loading a good file while A's is still importing. Without a lock A saw B's
    load in progress, left validation to it and returned normally -- a broken
    load passing -- and bytecode writing stayed off for the process."""

    import threading
    import types

    from jobcheck import registry as reg

    sync = types.SimpleNamespace(a_started=threading.Event(), a_release=threading.Event(),
                                 b_started=threading.Event())
    sys.modules["_jobcheck_load_race"] = sync  # type: ignore[assignment]
    (tmp_path / "check_a.py").write_text(textwrap.dedent("""
        import _jobcheck_load_race as sync
        from jobcheck import OK, register_check
        sync.a_started.set()
        sync.a_release.wait(10)

        @register_check("A_BAD", "m", depends_on=["NOT_REGISTERED"])
        def a(row):
            return OK
        """), encoding="utf-8")
    (tmp_path / "check_b.py").write_text(textwrap.dedent("""
        import _jobcheck_load_race as sync
        from jobcheck import OK, register_check
        sync.b_started.set()

        @register_check("B_GOOD", "m")
        def b(row):
            return OK
        """), encoding="utf-8")

    writing_bytecode = sys.dont_write_bytecode
    results: dict[str, BaseException | None] = {}

    def load(label: str, name: str) -> None:
        try:
            reg.load_checks([str(tmp_path / name)])
            results[label] = None
        except BaseException as exc:  # recorded for the assertions below
            results[label] = exc

    try:
        first = threading.Thread(target=load, args=("a", "check_a.py"))
        first.start()
        assert sync.a_started.wait(10)
        second = threading.Thread(target=load, args=("b", "check_b.py"))
        second.start()
        # B must wait for A's call to finish, not start importing beside it.
        assert not sync.b_started.wait(0.3)
        sync.a_release.set()
        first.join(10)
        second.join(10)
    finally:
        sync.a_release.set()
        sys.modules.pop("_jobcheck_load_race", None)

    assert isinstance(results["a"], ValueError)
    assert "depends on 'NOT_REGISTERED'" in str(results["a"])
    assert sys.dont_write_bytecode == writing_bytecode
