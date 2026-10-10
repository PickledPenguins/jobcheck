"""Working with paths and files: Locating YAML files on disk and reading them.

Both loaders need the same two steps: the file, or an error naming the absolute
path tried. Then its YAML, read strictly enough that a hand-edited file cannot
say something other than it appears to.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml


def _resolve_input_file(
    path: str, kind: str, caller: str, base_dir: str | Path | None = None
) -> Path:
    """The file *path* names, resolved, or a `ValueError` saying where it was looked for.

    A relative path is resolved against *base_dir* when the caller named one
    and against the working directory otherwise, an absolute path ignores
    both. *kind* names what was being loaded ("check file") and *caller* the
    function a reader should look up ("load_checks()").
    """
    given = str(path)
    named = Path(given)
    anchor = None if base_dir is None or named.is_absolute() else Path(base_dir)
    candidate = (named if anchor is None else anchor / named).resolve()
    if candidate.is_file():
        return candidate
    raise ValueError(
        f"No {kind} at {given!r}{_where(named, candidate, anchor)}. "
        f"{caller} names files explicitly; nothing is discovered.")


def _where(named: Path, candidate: Path, anchor: Path | None) -> str:
    """What was tried, when saying so adds anything.

    An absolute path that is not there needs no explanation. A relative one
    does, because the reader cannot see what it was joined to (neither the
    working directory nor a base_dir the call chose).
    """
    if candidate.is_dir():
        return f": {candidate} is a directory"
    if named.is_absolute():
        return ""
    against = "the working directory" if anchor is None else f"base_dir {anchor}"
    return f": nothing at {candidate}, where a relative path is resolved against {against}"


def _key_names(keys: Iterable[Any]) -> str:
    """*keys* for an error message: each one's repr, sorted as text, joined by commas
    (`'codez', True`). repr shows what YAML read, so `on:` lists as `True`."""
    return ", ".join(repr(key) for key in sorted(keys, key=str))


class _StrictLoader(yaml.SafeLoader):
    """`SafeLoader` refusing a key written twice in one mapping (PyYAML keeps the last silently)."""
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> Any:
        # Keys as written (tag and text), before a `<<` merge adds its own
        keys = [(key.tag, key.value) for key, _ in node.value if isinstance(key, yaml.ScalarNode)]
        if len(keys) != len(set(keys)):
            raise yaml.constructor.ConstructorError(
                None, None, "a key appears twice in this mapping", node.start_mark)
        return super().construct_mapping(node, deep=deep)


def _read_yaml(file: Path, shown: str) -> Any:
    """The YAML document in *file*. Bytes that are not UTF-8 raise `ValueError`, starting
    with *shown*: the path as the caller should see it. A repeated key is invalid YAML."""
    with open(file, encoding="utf-8") as handle:
        try:
            # The loader reads the first bytes as it is built, so a decode error
            # can come from either line.
            loader = _StrictLoader(handle)
            try:
                return loader.get_single_data()
            finally:
                loader.dispose()
        except UnicodeDecodeError as exc:
            raise ValueError(f"{shown}: not UTF-8 text: {exc}. Save the file as UTF-8.") from None
