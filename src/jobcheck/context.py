"""Per-row metadata that deliberately does not live in the DataFrame.

Real pipelines carry per-row state that is not tabular data: feature flags,
computed filesystem paths, pipeline bookkeeping.  Putting that into extra
DataFrame columns causes dtype churn (object columns holding dicts), bloats
exports, and mixes computation context into a data table.  It is kept in a
separate :class:`RowContext` object instead, handed to every check function.
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
    """The default context builder: an **empty** context, for every row.

    Deliberately empty. What belongs in a row's context is the adopting
    pipeline's business -- resolved paths, feature flags, a lookup against
    another system, the whole file for a cross-row check -- and this library
    cannot guess any of it. Inventing a field here would put a value in every
    caller's context that most of them never asked for.

    Supply your own instead, as ``context_builder=``: any callable taking the
    row and returning a :class:`RowContext` (or a subclass of it, which is how
    a cross-row check gets the whole file). It is called once per row, so keep
    it cheap, or build one object outside the loop and hand the same one back::

        shared = FileContext(counts=counts_for(df))
        collect_outcomes(df, context_builder=lambda row: shared)
    """

    return RowContext()
