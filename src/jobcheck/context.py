"""Per-row metadata that deliberately does not live in the DataFrame.

Feature flags, computed paths, pipeline bookkeeping, etc. Per-row state that
is not tabular data.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RowContext:
    """Metadata for one row

    Intentionally bare, subclass it and add the fields your checks read.
    See `writing-checks.md` for how a pipeline builds one and hands it to
    `validate(context_builder=...)`.

    The base class takes no attributes. Without a builder every row is handed
    the same instance, so a value a check cached on it would reach every later row.
    A subclass without `__slots__` of its own has a `__dict__` and takes any
    attribute.
    """

    __slots__ = ()
