"""The documents every docs check reads, and the world their examples run in.

`test_docs_api_unit.py`, `test_docs_blocks_unit.py`, `test_docs_cli_unit.py`,
`test_docs_messages_unit.py`, `test_docs_references_unit.py` and
`test_docs_structure_unit.py` split the documentation checks by concern; the paths and
the public-name table they share live here so the six cannot disagree about which
documents exist. The Python blocks, the output each shows, and the world they are run
in live here too, because `scripts/regen_docs.py` runs them exactly as the test does;
so does the README's worked session, for `test_readme.py`.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from typing import Any, NamedTuple

import jobcheck as prv

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / "docs").glob("*.md"))
README = ROOT / "README.md"

#: Every exported name, as the package binds it.
PUBLIC = {name: getattr(prv, name) for name in prv.__all__}

#: Check files the documents load from paths that do not exist in the repository.
#: Each is a copy of a shipped example check, written into the working directory
#: the block runs in.
ILLUSTRATIVE_CHECK_FILES = {
    "my_checks/check_age.py": "examples/checks/check_age.py",
    "my_checks/check_email.py": "examples/checks/check_email.py",
    "runs/2026-09-10/inputs/checks.py": "examples/checks/check_age.py",
}


#: A fenced block: the fences start a line, the opening one may carry an info string
#: after the language, and the closing one is alone on its line. The same pattern as
#: skills `bin/doc-examples`, so the two read the same blocks.
FENCE = re.compile(r"^```([\w+-]*)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)


class DocsBlock(NamedTuple):
    """One ```python block of a document, and the output the document shows after it."""

    path: Path
    line: int
    source: str
    shown_output: str | None  # the bare block that follows, if one does
    output_span: tuple[int, int] | None  # where shown_output sits in the document's text

    @property
    def label(self) -> str:
        return f"{self.path.name}:{self.line}"


def docs_blocks(documents: list[Path] | None = None) -> list[DocsBlock]:
    """Every ```python block in *documents*, all of docs/ by default, each with its
    shown output: a bare block straight after it, with nothing but blank lines
    between. A bare block anywhere else is a listing, not output."""

    found = []
    for path in DOCS if documents is None else documents:
        text = path.read_text(encoding="utf-8")
        blocks = list(FENCE.finditer(text))
        for index, block in enumerate(blocks):
            if block.group(1) != "python":
                continue
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            shown, span = None, None
            if (following is not None and following.group(1) == ""
                    and not text[block.end():following.start()].strip()):
                shown, span = following.group(2), following.span(2)
            line = text[: block.start()].count("\n") + 2
            found.append(DocsBlock(path, line, block.group(2), shown, span))
    return found


def is_template(source: str) -> bool:
    """The README's "writing a check" block is a template, not part of its worked session."""

    return "AGE_ABOVE_LIMIT" in source


def readme_session() -> list[DocsBlock]:
    """The README's Python blocks that read as one continuous session, in order:
    every one but the template, which `test_readme.py` checks on its own."""

    return [block for block in docs_blocks([README]) if not is_template(block.source)]


def documented_world(cwd: Path) -> dict[str, Any]:
    """The names a fragment may assume, built from the shipped demo.

    `df` is the entry point's demo frame, `outcomes` is that frame validated
    against the shipped checks and rules, `row` is one of its rows, and every
    public name is present. Files the blocks name are laid down under *cwd*. The
    registry is empty before and after, whoever calls: the test, the regenerator,
    or a runner with no fixture to clear it.
    """

    sys.path.insert(0, str(ROOT / "examples"))
    try:
        from main import demo_frame
    finally:
        sys.path.pop(0)

    prv.clear_registry()
    (cwd / "examples").symlink_to(ROOT / "examples")
    for target, source in ILLUSTRATIVE_CHECK_FILES.items():
        (cwd / target).parent.mkdir(parents=True, exist_ok=True)
        (cwd / target).write_text((ROOT / source).read_text(encoding="utf-8"), encoding="utf-8")

    prv.load_checks([str(ROOT / "examples" / "checks" / name)
                     for name in ("check_age.py", "check_email.py")])
    world: dict[str, Any] = {name: PUBLIC[name] for name in PUBLIC}
    # A @dataclass in a block looks its module up in sys.modules, so the
    # namespace has to belong to a module that is there.
    module = types.ModuleType("documented_example")
    sys.modules[module.__name__] = module
    world["__name__"] = module.__name__
    world["df"] = demo_frame()
    world["rules"] = prv.load_rules([str(ROOT / "examples/rules/error_rules.yaml")])
    world["outcomes"] = prv.validate(world["df"], rules=world["rules"])
    world["row"] = world["df"].iloc[4]
    world["report"] = prv.build_report(world["outcomes"], df=world["df"], key_column="id")
    prv.clear_registry()
    return world
