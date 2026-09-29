"""Saving the registry and putting it back, for tests that must not disturb
each other.

The library does not offer this and deliberately does not: outside a test there
is no use for it. A production caller loads its check files once at start-up, or
clears the registry and loads a different set between runs, or -- the shape
`architecture.md` recommends -- runs a second entry point in a second process. A
failed load already leaves the registry consistent without any help from here,
because `load_checks` rolls back per file. So this lives with the suite that
needs it rather than in a package a user installs.

What it buys the suite is nesting: an inner scope that loads check files and
must hand back exactly what it found, which `clear_registry` alone cannot do
because it hands back nothing.
"""

from __future__ import annotations

from typing import Any

from jobcheck import registry as reg


class SavedRegistry:
    """Every registry global `clear_registry` clears, copied.

    The in-progress load stack (`registry._LOADING`) is not copied. It belongs
    to the `load_checks` call that is running rather than to the registry: a
    frame put back from a load that has since finished would take the blame for
    the next file's checks, and that file's rollback would then drop checks
    belonging to somebody else. Capturing from inside a load is unsupported.
    """

    __slots__ = ("checks", "loaded_files", "topo_order")

    def __init__(self) -> None:
        self.checks: list[Any] = list(reg._CHECKS)
        self.loaded_files: list[str] = list(reg._LOADED_FILES)

        self.topo_order: list[Any] | None = reg._TOPO_ORDER

    def restore(self) -> None:
        """Put this registry back, dropping whatever is there now.

        The check-file modules `clear_registry` dropped from `sys.modules` are
        not re-imported: a restore is a state swap, not a load, and re-running a
        user's check file here would double-register. The checks still run --
        their runners are closures over the author's functions -- and
        `source_file` still names where each came from.
        """

        reg.clear_registry()
        reg._CHECKS.extend(self.checks)
        reg._LOADED_FILES.extend(self.loaded_files)

        reg._TOPO_ORDER = self.topo_order
