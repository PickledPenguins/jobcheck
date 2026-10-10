"""The superscript cross-references and each document's References table agree.

A term used in one document and explained in another carries a superscript number
linking straight to the explanation, `<sup>[2](concepts.md#rows)</sup>`, and the
document ends with a `## References` table listing every number: where it points
and what is there. The number is out of the reader's way; the table is where a
reader sees at a glance what else to read. `contributing.md` states the convention.

Whether each link's target exists is `test_no_internal_link_or_anchor_is_dead`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from doc_files import DOCS, README

pytestmark = pytest.mark.fast

CITATION = re.compile(r"<sup>\[(\d+)\]\(([^)\s]+)\)</sup>")
ROW = re.compile(r"^\| (\d+) \| \[[^\]]+\]\(([^)\s]+)\) \| [^|]+ \|$", re.M)
HEADING = "## References"


def _parts(path: Path) -> tuple[str, str | None]:
    """The document's body, and its References section if it has one."""
    # A fenced block shows the convention rather than using it, as contributing.md does.
    text = re.sub(r"^```.*?^```", "", path.read_text(encoding="utf-8"), flags=re.S | re.M)
    body, found, table = text.partition(f"\n{HEADING}\n")
    return body, (table if found else None)


@pytest.mark.parametrize("path", DOCS + [README], ids=lambda p: p.name)
def test_every_citation_is_a_row_of_the_references_table(path: Path) -> None:
    body, table = _parts(path)
    cited = CITATION.findall(body)
    if table is None:
        assert cited == [], f"{path.name} cites {len(cited)} reference(s) but has no {HEADING}"
        return
    rows = ROW.findall(table)
    numbers = [int(number) for number, _ in rows]
    assert numbers == list(range(1, len(rows) + 1)), (
        f"{path.name}: the References table must number its rows 1, 2, 3...")
    targets = dict((int(number), target) for number, target in rows)
    assert len(set(targets.values())) == len(targets), (
        f"{path.name}: two rows point to the same place; cite one number twice instead")
    for number, target in cited:
        assert int(number) in targets, f"{path.name}: cites {number}, which the table lacks"
        assert targets[int(number)] == target, (
            f"{path.name}: citation {number} points to {target}, "
            f"its table row to {targets[int(number)]}")
    unused = set(targets) - {int(number) for number, _ in cited}
    assert unused == set(), f"{path.name}: table rows never cited: {sorted(unused)}"


@pytest.mark.parametrize("path", DOCS + [README], ids=lambda p: p.name)
def test_the_references_table_is_the_last_section(path: Path) -> None:
    """At the foot, where a reader looks for it; nothing hides below it."""
    _, table = _parts(path)
    if table is not None:
        assert not re.search(r"^#{1,6} ", table, re.M), (
            f"{path.name}: a heading follows {HEADING}")
        assert CITATION.search(table) is None, f"{path.name}: {HEADING} cites itself"


def test_the_convention_is_written_down_where_contributors_read() -> None:
    text = (README.parent / "docs" / "contributing.md").read_text(encoding="utf-8")
    assert "<sup>[" in text and HEADING in text


def test_a_mismatched_citation_is_caught() -> None:
    """Pinned so a pattern that matches nothing cannot pass the tests above."""
    body = "A term<sup>[1](concepts.md#rows)</sup> and<sup>[2](cli.md)</sup>."
    table = "| # | Section | What it covers |\n|---|---|---|\n| 1 | [Rows](concepts.md#rows) | x |\n"
    assert CITATION.findall(body) == [("1", "concepts.md#rows"), ("2", "cli.md")]
    assert ROW.findall(table) == [("1", "concepts.md#rows")]
