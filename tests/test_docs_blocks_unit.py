"""Every ```python block under `docs/`, run in the world it assumes.

Binding a call catches a renamed keyword (`test_docs_api_unit.py`); running the
block catches what binding cannot -- a decorator that is gone, a return form the
engine refuses. Each block is a fragment leaning on a `df`, its `outcomes`, a rule
file and check files at illustrative paths, and the world below supplies them.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

import jobcheck as prv
from doc_files import DOCS, PUBLIC, ROOT

pytestmark = pytest.mark.fast

# --- the blocks, executed -----------------------------------------------------
#
# Binding a call against its signature catches a renamed keyword; it does not
# catch a decorator that no longer exists, or a return form the engine refuses.
# So every block is also run. The blocks are fragments -- they lean on a `df`,
# an `outcomes`, a rule file, a check file at an illustrative path -- and the
# test supplies that world rather than excusing the block: a name a block uses
# that neither it nor the world defines is exactly the drift being looked for.

#: Check files the documents load from paths that do not exist in the repository.
#: Each is a copy of a shipped example check, written into the working directory
#: the block runs in.
ILLUSTRATIVE_CHECK_FILES = {
    "my_checks/check_age.py": "examples/checks/check_age.py",
    "my_checks/check_email.py": "examples/checks/check_email.py",
    "runs/2026-09-10/inputs/checks.py": "examples/checks/check_age.py",
}


def docs_blocks() -> list[tuple[str, int, str]]:
    """Every ```python block under docs/, as (document, line, source)."""

    found = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"```python\n(.*?)```", text, re.S):
            line = text[: match.start()].count("\n") + 2
            found.append((path.name, line, match.group(1)))
    return found


def documented_world(cwd: Path) -> dict[str, Any]:
    """The names a fragment may assume, built from the shipped demo.

    `df` is the entry point's demo frame, `outcomes` is that frame validated
    against the shipped checks and rules, `row` is one of its rows, and every
    public name is present. Files the blocks name are laid down under *cwd*.
    """

    sys.path.insert(0, str(ROOT / "examples"))
    try:
        from main import demo_frame
    finally:
        sys.path.pop(0)

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


@pytest.mark.parametrize(
    "document, line, source", docs_blocks(), ids=lambda value: str(value)[:40])
def test_every_docs_block_runs_in_the_world_it_assumes(
    document: str, line: int, source: str, fresh_registry: None, tmp_path: Path,
    monkeypatch: Any, capsys: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    namespace = documented_world(tmp_path)
    try:
        exec(compile(source, f"{document}:{line}", "exec"), namespace)
    except Exception as exc:  # noqa: BLE001 -- the point is to name the block
        pytest.fail(f"{document}:{line} does not run: {type(exc).__name__}: {exc}")
    finally:
        sys.modules.pop(namespace["__name__"], None)
