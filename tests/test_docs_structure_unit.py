"""The documents as a set: an index, reachable, linked, and saying true numbers.

The README stays an index and reaches every document; no internal link or anchor is
dead; the rule keys, statuses, outcome names and exit codes are documented where they
belong; the suite sizes, catalog counts and line-width limit the documents state are
the real ones.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

from doc_files import DOCS, README, ROOT

pytestmark = pytest.mark.fast

#: A README longer than this has stopped being an index and become a manual.
README_MAX_LINES = 300


def test_the_readme_stays_an_index() -> None:
    """New material belongs in the document that owns the subject, not here."""

    lines = README.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= README_MAX_LINES, f"README is {len(lines)} lines"


def test_every_document_is_reachable_from_the_readme() -> None:
    """A document nobody links to is a document nobody reads."""

    linked = set(re.findall(r"\]\(docs/([a-z\-]+\.md)\)", README.read_text(encoding="utf-8")))
    assert {path.name for path in DOCS} - linked == set()


@pytest.mark.parametrize("path", DOCS + [README], ids=lambda p: p.name)
def test_no_internal_link_or_anchor_is_dead(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        file_part, _, anchor = target.partition("#")
        target_path = (path.parent / file_part).resolve() if file_part else path
        assert target_path.exists(), f"{path.name}: {target} does not exist"
        if anchor:
            headings = re.findall(r"^#{1,6} (.+)$", target_path.read_text(encoding="utf-8"), re.M)
            slugs = {re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-")
                     for h in headings}
            assert anchor in slugs, f"{path.name}: {target} has no such heading"


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_every_document_says_how_to_get_back(path: Path) -> None:
    """The index links out; each document links back, or a reader is stranded."""

    assert "](../README.md)" in path.read_text(encoding="utf-8")


def test_the_shipped_rule_keys_are_all_documented() -> None:
    """Configuration is the document that owns the rule-file format."""

    from jobcheck import rules

    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    for key in rules._RULE_KEYS:
        assert f"`{key}`" in configuration or f"{key}:" in configuration, key
    # The two actions are literals in the parser rather than a constant, so they
    # are named here as well: a third one added without a document is the drift
    # this catches.
    source = (ROOT / "src" / "jobcheck" / "rules.py").read_text(encoding="utf-8")
    assert 'action not in ("enable", "disable")' in source, "the actions moved; update the doc check"
    for action in ("enable", "disable"):
        assert action in configuration, action


def test_the_status_vocabulary_is_documented() -> None:
    """Status values are permanent identifiers; a new one nobody documents is a
    value that turns up in someone's report with no explanation."""

    from jobcheck.results import Status

    writing = (ROOT / "docs" / "writing-checks.md").read_text(encoding="utf-8")
    for status in Status:
        assert status.name in writing, status.name


@pytest.mark.parametrize("outcome", ["passed", "failed", "errored", "skipped", "disabled"])
def test_every_outcome_name_is_documented(outcome: str) -> None:
    reporting = (ROOT / "docs" / "reporting.md").read_text(encoding="utf-8")
    writing = (ROOT / "docs" / "writing-checks.md").read_text(encoding="utf-8")
    assert outcome in reporting or outcome in writing



def test_every_exit_code_the_entry_point_can_return_is_documented() -> None:
    """The exit codes are the contract a scheduled job is written against, and
    they live in one table; a new one added without a row there is invisible."""

    source = ast.parse((ROOT / "examples" / "main.py").read_text(encoding="utf-8"))
    raised = {
        int(node.exc.args[0].value)
        for node in ast.walk(source)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and getattr(node.exc.func, "id", None) == "SystemExit"
        and node.exc.args
        and isinstance(node.exc.args[0], ast.Constant)
        and isinstance(node.exc.args[0].value, int)
    }
    # 0 for a clean run and 1 for an uncaught exception are the interpreter's, not
    # the entry point's, so they are never raised in the source and are added here.
    expected = raised | {0, 1}
    table = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    documented = {int(value) for value in re.findall(r"^\| (\d+) \| ", table, re.M)}
    assert expected <= documented, f"undocumented exit code(s): {sorted(expected - documented)}"
    assert documented <= expected, f"documented exit code(s) that cannot happen: {sorted(documented - expected)}"



def collected(marker: str) -> int:
    """How many tests pytest collects for one marker, asked of pytest itself.

    A subprocess, because collecting inside the running session would count this
    session's own state rather than a clean one. ``-q --collect-only`` prints one
    ``path: count`` line per file, which is what is summed here.
    """

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", marker],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    counts = re.findall(r"^\S+\.py: (\d+)$", result.stdout, re.M)
    assert counts, f"no collection counts in:\n{result.stdout}"
    return sum(int(count) for count in counts)


def test_the_documented_suite_sizes_are_the_real_ones() -> None:
    """The numbers in the suite table drifted by five, three and eight before
    anything compared them with a collection: they are the one documented
    surface nothing else gates."""

    # The long suite's size includes the three property tests, which an
    # interpreter without hypothesis does not collect at all -- so on that
    # interpreter the documented number is right and the collection is short by
    # three. The long suite refuses to run there for the same reason.
    pytest.importorskip(
        "hypothesis", reason="the long-suite size counts the property tests"
    )

    table = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    documented = {
        mode: int(size.replace(",", ""))
        for mode, size in re.findall(r"\| `\./tests/run-tests\.sh (\w+)` \| ([\d,]+) tests", table)
    }
    fast, long = collected("fast"), collected("long")
    assert documented.get("fast") == fast, f"docs say {documented.get('fast')}, pytest collects {fast}"
    assert documented.get("long") == long, f"docs say {documented.get('long')}, pytest collects {long}"
    assert documented.get("all") == fast + long, (
        f"docs say {documented.get('all')}, fast plus long is {fast + long}")


def test_the_documented_catalog_counts_are_the_real_ones() -> None:
    """The README calls the two catalogs a case total, and testing.md breaks it
    down by level; both are written by hand and neither was checked."""

    cases = sorted(p.parent for p in (ROOT / "tests" / "examples").rglob("cmd"))
    failures = sorted(p.parent for p in (ROOT / "tests" / "failures").rglob("cmd"))
    levels = {level: sum(f"Level:    {level}" in (case / "README.md").read_text(encoding="utf-8")
                         for case in cases)
              for level in ("simple", "moderate", "complex")}

    testing = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    documented = re.search(
        r"holds (\d+) cases at three levels -- (\d+) simple, (\d+) moderate, (\d+) complex --\s+"
        r"and `tests/failures/` holds (\d+),",
        testing.replace("—", "--"),
    )
    assert documented, "docs/testing.md no longer states the catalog counts in the expected shape"
    assert [int(value) for value in documented.groups()] == [
        len(cases), levels["simple"], levels["moderate"], levels["complex"], len(failures)]

    readme = README.read_text(encoding="utf-8")
    total = re.search(r"the (\d+)-case example and failure catalogs", readme)
    assert total, "the README index no longer states a case total"
    assert int(total.group(1)) == len(cases) + len(failures)



MAX_LINE_WIDTH = 100
WIDTH_GATED_DIRS = ("src", "examples", "scripts")


def test_the_gated_directories_sit_under_the_documented_line_width() -> None:
    """`contributing.md` says lines stay under 100 characters and that nothing
    enforces it. Something does now: the claim was false on 2026-09-23, when two
    lines had drifted to 101 and 103, and nothing would have stopped the next two.
    """

    too_long = [
        f"{path.relative_to(ROOT)}:{number} is {len(line)} characters"
        for directory in WIDTH_GATED_DIRS
        for path in sorted((ROOT / directory).rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if len(line) > MAX_LINE_WIDTH
    ]
    assert too_long == [], (
        f"over {MAX_LINE_WIDTH} characters, the width contributing.md claims:\n  "
        + "\n  ".join(too_long)
    )


def test_contributing_names_what_the_width_gate_covers() -> None:
    """A rule enforced for three directories out of four has to say so, or the
    document is misleading in a new way."""

    contributing = (ROOT / "docs" / "contributing.md").read_text(encoding="utf-8")
    for directory in WIDTH_GATED_DIRS:
        assert f"`{directory}/`" in contributing, (
            f"contributing.md does not say the width rule covers {directory}/")
