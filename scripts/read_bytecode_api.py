#!/usr/bin/env python3
"""Read the public surface of the check-era modules out of their bytecode.

The pre-2026-09-09 sources are gone; ``recovery/bytecode/`` holds the only copy
of them, as ``.pyc``. A ``.pyc`` still carries every code object, so class and
function names, their parameters, their annotations and their docstrings survive
even though the statements do not. This script reads those out with ``marshal``
and prints them as Markdown, which is how ``recovery/recovered-api.md`` is
produced.

It deliberately does not decompile: no decompiler here supports 3.12 bytecode,
and the interface is the part worth recovering by hand. Run it with any Python
that can unmarshal the file -- 3.14 reads the 3.12 generation fine, though
``dis`` on the same object does not, the opcodes having moved.

Usage: scripts/read_bytecode_api.py [directory] [> recovery/recovered-api.md]
"""

from __future__ import annotations

import marshal
import struct
import sys
from pathlib import Path
from types import CodeType

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "recovery" / "bytecode" / "jobcheck"

# Bytes 8..16 of a .pyc header are the source mtime and the source size, both
# written by the compiler. The size is what makes a lost file measurable.
HEADER = 16


def source_size(data: bytes) -> int:
    """The byte size of the source file that produced this bytecode."""

    _mtime, size = struct.unpack("<II", data[8:HEADER])
    return size


def docstring(code: CodeType) -> str:
    """The object's docstring, or the empty string when it had none."""

    first = code.co_consts[0] if code.co_consts else None
    return first if isinstance(first, str) else ""


def children(code: CodeType) -> list[CodeType]:
    """The code objects defined directly inside *code*, in source order."""

    return [c for c in code.co_consts if isinstance(c, CodeType)]


def describe(code: CodeType, depth: int, out: list[str]) -> None:
    """Append one Markdown bullet per nested definition, deepest last."""

    for child in children(code):
        # A comprehension or a lambda is an implementation detail, not surface.
        if child.co_name.startswith("<"):
            continue
        args = ", ".join(child.co_varnames[: child.co_argcount])
        out.append(f"{'  ' * depth}- `{child.co_name}({args})`")
        doc = docstring(child)
        if doc:
            summary = doc.strip().splitlines()[0]
            out.append(f"{'  ' * depth}  - {summary}")
        describe(child, depth + 1, out)


def report(directory: Path) -> str:
    """Markdown for every ``.pyc`` in *directory*, newest generation last."""

    out: list[str] = [f"# Recovered interface: `{directory.name}`", ""]
    for path in sorted(directory.glob("*.pyc")):
        data = path.read_bytes()
        code = marshal.loads(data[HEADER:])
        out.append(f"## `{path.name}` (source was {source_size(data):,} bytes)")
        out.append("")
        doc = docstring(code)
        if doc:
            out.append("> " + doc.strip().replace("\n", "\n> "))
            out.append("")
        describe(code, 0, out)
        out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    directory = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    if not directory.is_dir():
        print(f"No such directory: {directory}", file=sys.stderr)
        return 2
    print(report(directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
