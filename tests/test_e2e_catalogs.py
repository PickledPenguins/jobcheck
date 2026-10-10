"""End-to-end: run every catalog case through the real entry point.

These double as the project's worked examples and troubleshooting reference, so
a behavior change fails here before it reaches a user.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from catalog import CASE_FILES, ROOT, case_dirs, run_case, stderr_tail

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
    # The exit code is part of what a case promises, and the one part a reader
    # cannot see in expected_stdout.txt. Enforced rather than asked for: 30 of
    # the 42 example READMEs had drifted without it.
    expected = readme.split("Expected:", 1)[1]
    assert f"exit {(case / 'exit_code').read_text().strip()}" in expected, (
        f"{case.name}: README's Expected: block does not name the exit code")
    # An example states its level, since that is how a reader picks one.
    if case.parent.parent.name == "examples":
        levels = [level for level in ("simple", "moderate", "complex")
                  if f"Level:    {level}" in readme]
        assert len(levels) == 1, f"{case.name}: README needs one 'Level:' line"


#: Cases whose recorded output is allowed to match another's, with the reason.
#: A clean row explained from a 2,000-row export prints exactly what a clean row
#: of the small file prints -- that sameness is what the large case demonstrates,
#: and since 2026-09-25 no heading names the row number to tell them apart.
DUPLICATE_OUTPUT_ALLOWED = {
    frozenset({"data/explain-a-clean-row", "data/large-export-explained"}),
}


def test_no_two_cases_record_the_same_output() -> None:
    """Two cases printing the same bytes are one case filed twice, whatever their
    commands say. `new_catalog_case.py` refuses a duplicate *command*, which
    misses a case that spells the same run differently -- passing the rule file
    `--rules` already defaults to, say, which is how one such pair got in.
    """
    seen: dict[str, str] = {}
    duplicates: list[frozenset[str]] = []
    for kind in ("examples", "failures"):
        for case in case_dirs(kind):
            name = f"{case.parent.name}/{case.name}"
            recorded = "".join(
                (case / file).read_text(encoding="utf-8") if (case / file).exists() else ""
                for file in CASE_FILES
            )
            if recorded in seen:
                duplicates.append(frozenset({seen[recorded], name}))
            else:
                seen[recorded] = name
    unexpected = [sorted(pair) for pair in duplicates if pair not in DUPLICATE_OUTPUT_ALLOWED]
    assert unexpected == [], f"cases recording identical output: {unexpected}"


def test_the_catalogs_keep_their_floors() -> None:
    """Floors on variety, not volume: the catalog is a reference, not a suite.

    A reader looking for something close to their own case should find it, which
    needs breadth at every level -- and the complex cases are the ones no unit
    check replaces, because nothing there is under check on its own. Each failure
    case is a message a user will meet; its count keeps them coming.
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
    assert len(case_dirs("failures")) >= 15


def test_cases_run_through_a_root_of_a_fixed_length() -> None:
    """The catalog must not depend on where the repository was cloned.

    A table's column widths are computed from the absolute path *before*
    `<project>` replaces it, so without a fixed-length root the expected output
    only matches on a clone whose path is the same length as the one that
    generated it -- which is a failure nobody can act on. Proved by comparison:
    the stable root is the same length everywhere, the real one is not.
    """
    from catalog import STABLE_ROOT, stable_root

    root = stable_root()
    if root == ROOT:
        pytest.skip("this filesystem refuses symlinks")
    assert root == STABLE_ROOT
    assert root.readlink() == ROOT
    # The name is fixed-width: a different user id or a different clone path is
    # the same number of characters, so two accounts, or two clones of one
    # account, on one machine still agree.
    assert len(STABLE_ROOT.name) == len("prv-catalog-root-") + 8 + 1 + 8


def test_a_link_pointing_somewhere_else_is_replaced() -> None:
    """A clone that moved, or a link left by another checkout that shared the
    name, must not send this run's cases at the wrong tree."""
    from catalog import STABLE_ROOT, stable_root

    if stable_root() == ROOT:
        pytest.skip("this filesystem refuses symlinks")
    STABLE_ROOT.unlink()
    STABLE_ROOT.symlink_to(ROOT.parent, target_is_directory=True)

    assert stable_root() == STABLE_ROOT
    assert STABLE_ROOT.readlink() == ROOT


def test_two_runs_racing_for_the_link_both_get_it() -> None:
    """Regression: the link was unlinked and re-created, so two runs of one clone
    both saw it missing, both unlinked, and the loser of the symlink call took the
    no-symlinks fallback -- rendering every path at a different width and failing
    the whole catalog on padding, with a comment blaming the filesystem.

    Threads rather than processes: the failure needs two callers between the
    unlink and the create, and threads reach that window in-process. It is also
    why the temporary name cannot just carry the pid.
    """

    from catalog import STABLE_ROOT, stable_root

    if stable_root() == ROOT:
        pytest.skip("this filesystem refuses symlinks")
    # What is already there stays out of the comparison: /tmp is shared, and a
    # run that was killed between creating its link and moving it into place
    # leaves one behind. This asserts that *these* calls clean up after
    # themselves, not that nobody ever failed to.
    pending_before = set(STABLE_ROOT.parent.glob(f"{STABLE_ROOT.name}.*"))
    STABLE_ROOT.unlink()

    roots: list[Path] = []
    threads = [threading.Thread(target=lambda: roots.append(stable_root()))
               for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert roots == [STABLE_ROOT] * 8
    # And none of them left its own link behind in a directory every clone and
    # every user on the machine shares.
    assert set(STABLE_ROOT.parent.glob(f"{STABLE_ROOT.name}.*")) == pending_before
