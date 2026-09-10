"""End-to-end: run every catalog case through the real entry point.

These double as the project's worked examples and troubleshooting reference, so
a behaviour change fails here before it reaches a user.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from catalog import ROOT, case_dirs, run_case, stderr_tail

pytestmark = pytest.mark.long


def case_id(case: Path) -> str:
    return str(case.relative_to(ROOT / "tests"))


@pytest.mark.parametrize("case", case_dirs("examples"), ids=case_id)
def test_example_case_matches_its_expected_output(case: Path) -> None:
    result = run_case(case)
    assert result.returncode == int((case / "exit_code").read_text().strip())
    assert result.stdout == (case / "expected_stdout.txt").read_text(encoding="utf-8")
    assert result.stderr == ""


@pytest.mark.parametrize("case", case_dirs("failures"), ids=case_id)
def test_failure_case_matches_its_expected_message(case: Path) -> None:
    result = run_case(case)
    assert result.returncode == int((case / "exit_code").read_text().strip())
    assert stderr_tail(result.stderr) == (case / "expected_stderr.txt").read_text(encoding="utf-8")
    assert result.stdout == "" or "== Registry ==" not in result.stdout


@pytest.mark.parametrize("case", case_dirs("examples") + case_dirs("failures"), ids=case_id)
def test_every_case_documents_itself(case: Path) -> None:
    readme = (case / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# ")
    assert "Input:" in readme
    assert "Expected:" in readme
