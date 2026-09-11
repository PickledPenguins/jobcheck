"""Per-row metadata that deliberately does not live in the DataFrame.

Real pipelines carry per-row state that is not tabular data: feature flags,
computed filesystem paths, pipeline bookkeeping.  Putting that into extra
DataFrame columns causes dtype churn (object columns holding dicts), bloats
exports, and mixes computation context into a data table.  It is kept in a
separate :class:`RowContext` object instead, handed to every check function.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RowContext:
    """Metadata for a single row, kept out of the DataFrame itself.

    Bare by design. What belongs in a row's context is the adopting pipeline's
    business -- resolved paths, feature flags, a lookup against another system,
    the whole file for a cross-row check -- and this library cannot guess any of
    it, so it defines the type and nothing else.

    Subclass it, add the fields your checks read, and build it however suits the
    pipeline: a classmethod, a factory function, or one object built outside the
    loop and handed to every row. Whatever builds it is passed to
    :func:`jobcheck.validate` as ``context_builder``, a callable taking the row
    and returning a ``RowContext``::

        @dataclass
        class FileContext(RowContext):
            counts: dict[str, dict[str, int]] = field(default_factory=dict)

            @classmethod
            def build(cls, row):
                return cls(counts=counts_for(row))

        validate(df, context_builder=FileContext.build)

    Without a ``context_builder`` every row is handed the same empty
    ``RowContext``.
    """
