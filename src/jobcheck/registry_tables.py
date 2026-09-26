"""The registry, the rules, and the relationship between them, as tables.

Kept apart from registering and evaluating because it is the job that grows:
every question about the configuration becomes another column rather than
another engine feature. Each table carries the columns a reader always wants and
takes `add_columns` for the ones only some readers do, and each carries its own
title for `render`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .registry import _CHECKS, _get_topo_order
from .rules import Rule
from .tables import _shown

# Every column each table builds; tables._DEFAULT_COLUMNS picks which are shown.
_REGISTRY_COLUMNS = ["code", "layer", "default", "message", "depends_on", "source_file",
                     "could_be_overridden_by", "effective_state"]
_RULES_COLUMNS = ["name", "action", "codes_hit_count", "codes", "match", "message",
                  "source_file"]


def _rules_for_code(code: str, rules: list[Rule]) -> list[Rule]:
    """Rules that reference *code*, in load order."""

    return [rule for rule in rules if code in rule.codes]


def _render_match(rule: Rule) -> str:
    """Compact one-cell rendering of a rule's match criteria."""

    if rule.match_all:
        return "all"
    return "; ".join(f"{criterion.column}~=/{criterion.pattern}/"
                     for criterion in rule.criteria)


def registry_table(rules: list[Rule] | None = None,
                   add_columns: list[str] | None = None) -> pd.DataFrame:
    """One row per registered check, ordered layer then code, so the fundamental
    checks read first. The columns shown are `tables._DEFAULT_COLUMNS["Registry"]`
    plus `add_columns`: `source_file`, `could_be_overridden_by`, `effective_state`.

    `could_be_overridden_by` and `effective_state` are the two columns that read
    `rules`, and `rules` feeds nothing else. Neither is "was overridden by":
    whether a rule fires depends on the row it is matched against, and this table
    has no row.
    """

    # Layers are computed with the evaluation order; a check registered outside
    # load_checks has none until something asks for it.
    _get_topo_order()
    rules = rules or []

    rows: list[dict[str, Any]] = []
    for check in _CHECKS:
        matching = _rules_for_code(check.code, rules)
        state = "ON" if check.default_enabled else "OFF"
        rows.append({
            "code": check.code,
            "layer": check.layer,
            "default": state,
            "message": check.message,
            "depends_on": "; ".join(check.depends_on) if check.depends_on else "-",
            "source_file": check.source_file,
            "could_be_overridden_by":
                "; ".join(f"{rule.name} ({rule.action})" for rule in matching) or "-",
            "effective_state":
                f"depends on row (default {state} unless a rule above matches)"
                if matching else f"DEFAULT ({state})",
        })

    # Sorted before it is narrowed, since the defaults may leave out `layer` or
    # `code`. Columns are named so an empty registry still has them to sort by.
    table = (pd.DataFrame(rows, columns=_REGISTRY_COLUMNS)
             .sort_values(["layer", "code"]).reset_index(drop=True))
    return _shown(table, "Registry", add_columns)


def rules_table(rules: list[Rule], add_columns: list[str] | None = None) -> pd.DataFrame:
    """One row per rule, rather than per code. The columns shown are
    `tables._DEFAULT_COLUMNS["Rules"]` plus `add_columns`: `codes`, `source_file`.

    `codes_hit_count` is a count rather than the code list, so a rule touching
    many codes does not blow the table apart; `add_columns=["codes"]` gives the
    detail.
    """

    rows: list[dict[str, Any]] = []
    for rule in rules:
        rows.append({
            "name": rule.name,
            "action": rule.action,
            "codes_hit_count": len(rule.codes),
            "codes": ", ".join(rule.codes),
            "match": _render_match(rule),
            "message": rule.message,
            "source_file": rule.source_file,
        })

    return _shown(pd.DataFrame(rows, columns=_RULES_COLUMNS), "Rules", add_columns)
