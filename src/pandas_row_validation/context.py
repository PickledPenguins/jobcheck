"""Per-row metadata that deliberately does not live in the DataFrame.

Real pipelines carry per-row state that is not tabular data: feature flags,
computed filesystem paths, pipeline bookkeeping.  Putting that into extra
DataFrame columns causes dtype churn (object columns holding dicts), bloats
exports, and mixes computation context into a data table.  It is kept in a
separate :class:`RowContext` object instead, handed to every test function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class RowContext:
    """Metadata for a single row, kept out of the DataFrame itself.

    The four buckets are intentionally loose ``dict`` fields rather than a
    fixed schema: every adopting pipeline carries different metadata, and a
    rigid schema here would force edits to this file for each new key.
    """

    flags: dict[str, Any] = field(default_factory=dict)
    paths: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


def build_context(row: "pd.Series[Any]") -> RowContext:
    """Build the :class:`RowContext` for one row.

    This is the integration point for the person adopting the framework: it is
    a deliberate stub.  Replace the body with whatever logic already produces
    per-row metadata in the surrounding pipeline (path resolution, lookups
    against other systems, flags derived from upstream state).  It is called
    once per row, so keep it cheap or memoise inside it.
    """

    flags: dict[str, Any] = {}
    if "source_system" in row.index:
        source = row["source_system"]
        flags["legacy"] = isinstance(source, str) and source.startswith("LEGACY_")
    return RowContext(flags=flags)
