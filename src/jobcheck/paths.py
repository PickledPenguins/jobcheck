"""Turning a path a caller named into a file on disk.

The two loaders are the only places in the package that open a file the caller
chose, and both need the same thing: the file, or an error saying where it was
looked for. That step lives here rather than in either of them because
`rules.py` may not import the registry, and a relative path that is not there
says nothing at all unless the message prints the absolute path tried.
"""

from __future__ import annotations

from pathlib import Path


def resolve_input_file(path: str, kind: str, caller: str) -> Path:
    """The file *path* names, resolved, or a `ValueError` saying where it was
    looked for.

    A relative path is resolved against the working directory. *kind* names
    what was being loaded ("check file") and *caller* the function a reader
    should look up ("load_checks()").
    """

    given = str(path)
    candidate = Path(given).resolve()
    if candidate.is_file():
        return candidate
    raise ValueError(
        f"No {kind} at {given!r}{_where(given, candidate)}. "
        f"{caller} names files explicitly; nothing is discovered."
    )


def _where(given: str, candidate: Path) -> str:
    """What was tried, when saying so adds anything.

    An absolute path that is not there needs no explanation; a relative one
    does, because the reader cannot see the working directory it was joined to.
    A directory is the likely mistake and is named as itself.
    """

    if candidate.is_dir():
        return f": {candidate} is a directory, so name the file in it"
    if Path(given).is_absolute():
        return ""
    return (f": nothing at {candidate}, where a relative path is resolved "
            "against the working directory")
