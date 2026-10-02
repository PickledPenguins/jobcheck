"""Rewrite the output shown after each ```python block in docs/ and the README with
what it prints.

A tool, not a gate: run it after an intended change to what a documented example
prints, then read the diff -- a blind regeneration turns a failing test into a
recorded bug. Each block runs the way its gate runs it:

- docs/ (`tests/test_docs_blocks_unit.py`): each block on its own, from an empty
  registry, in a fresh working directory holding the world `tests/doc_files.py`
  builds. A block without a shown output is not run.
- README.md (`tests/test_readme.py`): the worked session, every block but the
  "writing a check" template, in order and in one namespace, from the project root
  and an empty registry. Every session block runs, since later ones use the names
  earlier ones define.

    python3 scripts/regen_docs.py              every document under docs/, and the README
    python3 scripts/regen_docs.py reporting    the documents whose name contains this

A block's shown output is a bare block straight after it, with nothing but blank
lines between. A block that raises is named on stderr and its shown output left
alone; in the README it also ends the session, because the blocks after it need
what it would have defined.

Exit codes: 0 done; 1 a block raised; 2 a name matched no document.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "examples"), str(ROOT / "tests")]

from doc_files import (  # noqa: E402
    DOCS, README, DocsBlock, docs_blocks, documented_world, readme_session,
)
from jobcheck import clear_registry  # noqa: E402

#: A block, and what it printed or the exception it raised.
Printed = tuple[DocsBlock, "str | Exception"]


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


def docs_printed(document: Path) -> Iterator[Printed]:
    """What each block of a document under docs/ prints, each block on its own."""

    for block in docs_blocks([document]):
        if block.output_span is None:
            continue
        try:
            printed: str | Exception = printed_by(block)
        except Exception as exc:  # the block's own error: reported, not raised
            printed = exc
        yield block, printed


def readme_printed() -> Iterator[Printed]:
    """What each block of the README's session prints, run as `test_readme.py`
    runs them. Stops after a block that raises."""

    home = Path.cwd()
    os.chdir(ROOT)
    clear_registry()
    namespace: dict[str, object] = {}
    try:
        for block in readme_session():
            printed = io.StringIO()
            try:
                with contextlib.redirect_stdout(printed):
                    exec(compile(block.source, block.label, "exec"), namespace)
            except Exception as exc:  # the block's own error: reported, not raised
                yield block, exc
                return
            yield block, printed.getvalue()
    finally:
        os.chdir(home)
        clear_registry()


def regenerate(documents: list[Path]) -> int:
    """Rewrite each shown output in *documents* that differs from what its block
    prints. Returns 1 if a block raised, else 0."""

    status = 0
    for document in documents:
        edits = []
        results = readme_printed() if document == README else docs_printed(document)
        for block, printed in results:
            if isinstance(printed, Exception):
                print(f"{block.label}: raised {type(printed).__name__}: {printed}",
                      file=sys.stderr)
                status = 1
                continue
            if block.output_span is not None and printed != block.shown_output:
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
    documents = [*DOCS, README]
    # A name matching nothing is refused: done-with-nothing reads as success.
    unmatched = [part for part in wanted if not any(part in path.name for path in documents)]
    if unmatched:
        print(f"regen_docs: no document under docs/ or the README matches "
              f"{', '.join(unmatched)} "
              f"(documents: {', '.join(path.name for path in documents)})", file=sys.stderr)
        return 2
    return regenerate([path for path in documents
                       if not wanted or any(part in path.name for part in wanted)])


if __name__ == "__main__":
    raise SystemExit(main())
