"""The documents every docs check reads, named once for the three test files.

`test_docs_api_unit.py`, `test_docs_blocks_unit.py` and `test_docs_structure_unit.py`
split what was one module by concern; the paths and the public-name table they share
live here so the three cannot disagree about which documents exist.
"""

from __future__ import annotations

from pathlib import Path

import jobcheck as prv

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / "docs").glob("*.md"))
README = ROOT / "README.md"

#: Every exported name, as the package binds it.
PUBLIC = {name: getattr(prv, name) for name in prv.__all__}
