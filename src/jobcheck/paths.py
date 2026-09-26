"""Turning a path a caller named into a file on disk.

Both loaders need the same step: the file, or an error naming the absolute path
tried. It lives here because `rules.py` may not import the registry.
"""

from __future__ import annotations

from pathlib import Path


def resolve_input_file(path: str, kind: str, caller: str,
                       base_dir: str | Path | None = None) -> Path:
    """The file *path* names, resolved, or a `ValueError` saying where it was
    looked for.

    A relative path is resolved against *base_dir* when the caller named one
    and against the working directory otherwise; an absolute path ignores
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
        f"{caller} names files explicitly; nothing is discovered."
    )


def _where(named: Path, candidate: Path, anchor: Path | None) -> str:
    """What was tried, when saying so adds anything.

    An absolute path that is not there needs no explanation; a relative one
    does, because the reader cannot see what it was joined to -- neither the
    working directory nor a base_dir the call chose. A directory is the likely
    mistake and is named as itself.
    """

    if candidate.is_dir():
        return f": {candidate} is a directory, so name the file in it"
    if named.is_absolute():
        return ""
    against = "the working directory" if anchor is None else f"base_dir {anchor}"
    return f": nothing at {candidate}, where a relative path is resolved against {against}"
