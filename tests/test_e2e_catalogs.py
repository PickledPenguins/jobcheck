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
    # Most examples write nothing to stderr. The ones that do -- a rule naming a
    # column the data lacks -- carry the warning as a file, so the wording is
    # pinned rather than merely tolerated.
    expected_stderr = case / "expected_stderr.txt"
    if expected_stderr.exists():
        assert result.stderr == expected_stderr.read_text(encoding="utf-8")
    else:
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


@pytest.mark.parametrize("case", case_dirs("examples"), ids=case_id)
def test_every_example_states_its_level(case: Path) -> None:
    """A reader picks a case by how much it does; the level is how they pick."""

    readme = (case / "README.md").read_text(encoding="utf-8")
    levels = [level for level in ("simple", "moderate", "complex")
              if f"Level:    {level}" in readme]
    assert levels, f"{case.name}: README has no 'Level:' line"
    assert len(levels) == 1


def test_the_catalog_has_enough_of_each_level() -> None:
    """Floors on variety, not volume: the catalog is a reference, not a suite.

    A reader looking for something close to their own case should find it, which
    needs breadth at every level -- and the complex cases are the ones no unit
    test replaces, because nothing there is under test on its own.
    """

    counts = {"simple": 0, "moderate": 0, "complex": 0}
    for case in case_dirs("examples"):
        readme = (case / "README.md").read_text(encoding="utf-8")
        for level in counts:
            if f"Level:    {level}" in readme:
                counts[level] += 1
    assert counts["simple"] >= 15, counts
    assert counts["moderate"] >= 15, counts
    assert counts["complex"] >= 10, counts


def test_the_failure_catalog_covers_the_common_mistakes() -> None:
    """Each of these is a message a user will meet; the count keeps them coming."""

    assert len(case_dirs("failures")) >= 15
