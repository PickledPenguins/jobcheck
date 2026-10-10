"""Every ```python block under `docs/`, run in the world it assumes.

Binding a call catches a renamed keyword (`test_docs_api_unit.py`); running the
block catches what binding cannot -- a decorator that is gone, a return form the
engine refuses. Each block is a fragment leaning on a `df`, its `outcomes`, a rule
file and check files at illustrative paths, and the world `doc_files.py` builds
supplies them. A bare block straight after a Python block, with nothing but blank
lines between, is that block's output, and what the block prints must equal it byte
for byte; `scripts/regen_docs.py` rewrites it after an intended change.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from doc_files import DocsBlock, docs_blocks, documented_world

pytestmark = pytest.mark.fast

# --- the blocks, executed -----------------------------------------------------
#
# Binding a call against its signature catches a renamed keyword; it does not
# catch a decorator that no longer exists, or a return form the engine refuses.
# So every block is also run. The blocks are fragments -- they lean on a `df`,
# an `outcomes`, a rule file, a check file at an illustrative path -- and the
# test supplies that world rather than excusing the block: a name a block uses
# that neither it nor the world defines is exactly the drift being looked for.


@pytest.mark.parametrize("block", docs_blocks(), ids=lambda block: block.label)
def test_every_docs_block_runs_in_the_world_it_assumes(
    block: DocsBlock, fresh_registry: None, tmp_path: Path,
    monkeypatch: Any, capsys: Any,
) -> None:
    """Regression for the output half: reporting.md showed three outputs no frame
    produces, one of them against rules its code did not pass."""
    monkeypatch.chdir(tmp_path)
    namespace = documented_world(tmp_path)
    try:
        exec(compile(block.source, block.label, "exec"), namespace)
    except Exception as exc:  # noqa: BLE001 -- the point is to name the block
        pytest.fail(f"{block.label} does not run: {type(exc).__name__}: {exc}")
    finally:
        sys.modules.pop(namespace["__name__"], None)
    if block.shown_output is not None:
        assert capsys.readouterr().out == block.shown_output, (
            f"{block.label} prints something other than the output shown after it; "
            "after an intended change, python3 scripts/regen_docs.py rewrites it")


def test_the_documents_show_output_for_their_blocks() -> None:
    """A guard on the guard: output blocks that stopped being recognized would
    turn the comparison above into a no-op."""
    assert sum(block.shown_output is not None for block in docs_blocks()) >= 6


def test_a_fence_is_read_only_at_the_start_of_a_line(tmp_path: Path) -> None:
    """The fence rule `bin/doc-examples` uses: an info string after the language is
    allowed, and three backticks inside a line of prose open nothing."""
    path = tmp_path / "doc.md"
    path.write_text("Prose quoting ```python\nis not a block.\n\n"
                    "```python title\nprint(1)\n```\n\n```\n1\n```\n", encoding="utf-8")
    (block,) = docs_blocks([path])
    assert (block.line, block.source, block.shown_output) == (5, "print(1)\n", "1\n")
