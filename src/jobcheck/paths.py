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
    """Mapping keys as a message lists them: `'codez', True`, sorted as text. Each is
    shown as Python writes it, so a key YAML read as a bool or a number
    (`on:`, `1:` shows as `True` or `1`, not as the text it looked like in the file)."""
    return ", ".join(repr(key) for key in sorted(keys, key=str))


class _DuplicateKey(Exception):
    """A mapping named one key twice; `_read_yaml` adds the file to the message."""


class _StrictLoader(yaml.SafeLoader):
    """`SafeLoader`, except that a mapping holding one key twice is refused.

    PyYAML keeps the last of two identical keys and says nothing, so a second
    `codes:` appended to a rule, or a second `checks:` in a setup file, would
    quietly replace the first.
    """
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> Any:
        first_line: dict[Any, int] = {}
        for key_node, _ in node.value:
            # A `<<` merge may repeat a key on purpose: the explicit one overrides it
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            line = key_node.start_mark.line + 1
            try:
                earlier = first_line.get(key)
            except TypeError:  # unhashable: SafeLoader refuses it with its own message
                continue
            if earlier is not None:
                raise _DuplicateKey(
                    f"key {key!r} appears twice in one mapping, on lines {earlier} and {line}.")
            first_line[key] = line
        return super().construct_mapping(node, deep=deep)


def _read_yaml(file: Path, shown: str) -> Any:
    """The YAML document in *file*. A repeated key, or bytes that are not UTF-8,
    raise `ValueError`, starting with *shown*: the path as the caller should see it."""

    with open(file, encoding="utf-8") as handle:
        try:
            # The loader reads the first bytes as it is built, so a decode error
            # can come from either line.
            loader = _StrictLoader(handle)
            try:
                return loader.get_single_data()
            finally:
                loader.dispose()
        except _DuplicateKey as exc:
            raise ValueError(f"{shown}: {exc}") from None
        except UnicodeDecodeError as exc:
            raise ValueError(f"{shown}: not UTF-8 text: {exc}. Save the file as UTF-8.") from None
