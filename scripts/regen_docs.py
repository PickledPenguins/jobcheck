"""Rewrite the output shown after each ```python block in docs/ with what it prints.

A tool, not a gate: run it after an intended change to what a documented example
prints, then read the diff -- a blind regeneration turns a failing test into a
recorded bug. `tests/test_docs_blocks_unit.py` is the gate, and this runs each block
the way that test does: from an empty registry, in a fresh working directory holding
the world `tests/doc_files.py` builds.

    python3 scripts/regen_docs.py              every document under docs/
    python3 scripts/regen_docs.py reporting    the documents whose name contains this

A block's shown output is a bare block straight after it, with nothing but blank
lines between; blocks without one are not run. A block that raises is named on
stderr and its shown output left alone.

Exit codes: 0 done; 1 a block raised.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "examples"), str(ROOT / "tests")]

from doc_files import DOCS, DocsBlock, docs_blocks, documented_world  # noqa: E402


def printed_by(block: DocsBlock) -> str:
    """What *block* prints, run as the docs test runs it."""

    home = Path.cwd()
    with tempfile.TemporaryDirectory() as scratch:
        os.chdir(scratch)
        try:
            namespace = documented_world(Path(scratch))
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                exec(compile(block.source, block.label, "exec"), namespace)
            return printed.getvalue()
        finally:
            os.chdir(home)
            sys.modules.pop("documented_example", None)


def regenerate(documents: list[Path]) -> int:
    """Rewrite each shown output in *documents* that differs from what its block
    prints. Returns 1 if a block raised, else 0."""

    status = 0
    for document in documents:
        edits = []
        for block in docs_blocks([document]):
            if block.shown_output is None or block.output_span is None:
                continue
            try:
                printed = printed_by(block)
            except Exception as exc:  # the block's own error: reported, not raised
                print(f"{block.label}: raised {type(exc).__name__}: {exc}", file=sys.stderr)
                status = 1
                continue
            if printed != block.shown_output:
                edits.append((block.output_span, printed))
                print(f"{block.label}: rewritten")
        if edits:
            text = document.read_text(encoding="utf-8")
            # Last first, so each span still points where it did in the original.
            for (start, end), printed in sorted(edits, reverse=True):
                text = text[:start] + printed + text[end:]
            document.write_text(text, encoding="utf-8")
    return status


def main(argv: list[str] | None = None) -> int:
    wanted = sys.argv[1:] if argv is None else argv
    return regenerate([path for path in DOCS
                       if not wanted or any(part in path.name for part in wanted)])


if __name__ == "__main__":
    raise SystemExit(main())
