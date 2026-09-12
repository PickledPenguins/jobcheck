"""Per-row metadata that deliberately does not live in the DataFrame.

Feature flags, computed paths, pipeline bookkeeping: real per-row state that is
not tabular data. Extra DataFrame columns holding it cause dtype churn and leak
into exports, so it is handed to checks as a separate object instead.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RowContext:
    """Metadata for one row. Bare: subclass it and add the fields your checks read.

    What belongs in a row's context is the adopting pipeline's business, so the
    library defines the type and nothing else. See `writing-checks.md` for how a
    pipeline builds one and hands it to `validate(context_builder=...)`.
    """
