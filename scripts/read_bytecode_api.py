#!/usr/bin/env python3
"""Read the public surface of the check-era modules out of their bytecode.

The pre-2026-09-09 sources are gone. What survives them is their ``.pyc``, which
is no longer in the working tree: commit ``3fce4b4`` on this branch added it under
``recovery/bytecode/`` so the next commit could delete it without losing it, and
``main`` still carries it. A ``.pyc`` still carries every code object, so class and
function names, their parameters, their annotations and their docstrings survive
even though the statements do not. This script reads those out with ``marshal``
and prints them as Markdown, which is how ``recovery/recovered-api.md`` was
produced.

With no argument it reads the package's bytecode straight out of that commit --
nothing to restore first. A directory argument reads the ``.pyc`` files there
instead, for a restored copy (``git restore --source=3fce4b4 -- recovery``) or the
example checks' generation beside it.

It deliberately does not decompile: no decompiler here supports 3.12 bytecode,
and the interface is the part worth recovering by hand. Run it with any Python
that can unmarshal the file -- 3.14 reads the 3.12 generation fine, though
``dis`` on the same object does not, the opcodes having moved.

Usage: scripts/read_bytecode_api.py [DIRECTORY] [> recovered-api.md]
"""

from __future__ import annotations

import marshal
import struct
import subprocess
import sys
from pathlib import Path
from types import CodeType

ROOT = Path(__file__).resolve().parent.parent

#: The commit that holds the bytecode on this branch, and where in it. The next
#: commit deletes the directory, so this one is the copy history keeps.
RECOVERY_COMMIT = "3fce4b4"
RECOVERY_PATH = "recovery/bytecode/jobcheck"

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


def from_directory(directory: Path) -> dict[str, bytes]:
    """Every ``.pyc`` in *directory*, by file name."""

    return {path.name: path.read_bytes() for path in directory.glob("*.pyc")}


def from_history(commit: str = RECOVERY_COMMIT, path: str = RECOVERY_PATH) -> dict[str, bytes]:
    """Every ``.pyc`` under *path* at *commit*, read out of git by file name.

    Raises ``RuntimeError`` when git cannot give them -- a shallow clone, or a
    copy of the tree without its history.
    """

    def git(*args: str) -> bytes:
        done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True)
        if done.returncode != 0:
            raise RuntimeError(done.stderr.decode(errors="replace").strip())
        return done.stdout

    names = git("ls-tree", "--name-only", f"{commit}:{path}").decode().split()
    return {name: git("show", f"{commit}:{path}/{name}")
            for name in names if name.endswith(".pyc")}


def report(title: str, files: dict[str, bytes]) -> str:
    """Markdown for every ``.pyc`` in *files*, sorted by name."""

    out: list[str] = [f"# Recovered interface: `{title}`", ""]
    for name, data in sorted(files.items()):
        out.append(f"## `{name}` (source was {source_size(data):,} bytes)")
        try:
            code = marshal.loads(data[HEADER:])
        except ValueError:
            # A newer interpreter's marshal format; the header is still readable.
            out += ["", f"Not readable by Python {sys.version.split()[0]}: "
                        "run this with the Python that compiled it or newer.", ""]
            continue
        out.append("")
        doc = docstring(code)
        if doc:
            out.append("> " + doc.strip().replace("\n", "\n> "))
            out.append("")
        describe(code, 0, out)
        out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: read_bytecode_api.py [DIRECTORY]", file=sys.stderr)
        return 2
    if len(argv) == 2:
        directory = Path(argv[1])
        if not directory.is_dir():
            print(f"No such directory: {directory}", file=sys.stderr)
            return 2
        print(report(directory.name, from_directory(directory)))
        return 0
    try:
        files = from_history()
    except RuntimeError as exc:
        print(f"Cannot read {RECOVERY_PATH} at {RECOVERY_COMMIT} from git: {exc}\n"
              "It is also on main: git restore --source=origin/main -- recovery, "
              "then pass recovery/bytecode/jobcheck.", file=sys.stderr)
        return 2
    print(report(Path(RECOVERY_PATH).name, files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
