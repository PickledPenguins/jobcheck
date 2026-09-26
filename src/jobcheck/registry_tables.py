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
from .tables import _keep_columns, _reject_unknown_columns

#: The columns each table always has, before `add_columns` adds to them and after
#: `drop_columns` takes from them. Named rather than inline so both arguments are
#: validated against the same list a reader can find.
REGISTRY_BASE_COLUMNS = ["code", "layer", "default", "message", "depends_on"]
RULES_BASE_COLUMNS = ["name", "action", "codes_hit_count", "match", "message"]

#: Optional columns the tables offer. ``source_file`` is where the check or rule
#: came from; ``could_be_overridden_by`` and ``effective_state`` read the rules
#: :func:`registry_table` is given.
#: ``codes`` is the list behind a rule's ``codes_hit_count``, opt-in because a
#: broad rule's list makes a tall row.
REGISTRY_OPTIONAL_COLUMNS = ["source_file", "could_be_overridden_by", "effective_state"]
RULE_OPTIONAL_COLUMNS = ["codes", "source_file"]


def _rules_for_code(code: str, rules: list[Rule]) -> list[Rule]:
    """Rules that reference *code*, in load order."""

    return [rule for rule in rules if code in rule.codes]


def _render_match(rule: Rule) -> str:
    """Compact one-cell rendering of a rule's match criteria."""

    if rule.match_all:
        return "all"
    return "; ".join(f"{criterion.column}~=/{criterion.pattern}/"
                     for criterion in rule.criteria)


def registry_table(rules: list[Rule] | None = None, add_columns: list[str] | None = None,
                   drop_columns: list[str] | None = None) -> pd.DataFrame:
    """One row per registered check, ordered layer then code, so the fundamental
    checks read first.

    `could_be_overridden_by` and `effective_state` are the two added columns that
    read `rules`, and `rules` feeds nothing else. Neither is "was overridden by":
    whether a rule fires depends on the row it is matched against, and this table
    has no row.
    """

    # Layers are computed with the evaluation order; a check registered outside
    # load_checks has none until something asks for it.
    _get_topo_order()
    add_columns = list(add_columns or [])
    _reject_unknown_columns(add_columns, REGISTRY_OPTIONAL_COLUMNS, "the registry table")
    kept = _keep_columns(REGISTRY_BASE_COLUMNS, drop_columns, "the registry table")
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

    # Built with every column, sorted, and only then narrowed: `layer` and `code`
    # are what the sort reads, and `drop_columns` may take either out. Columns are
    # passed explicitly so an empty registry still has columns to sort by.
    table = (
        pd.DataFrame(rows, columns=[*REGISTRY_BASE_COLUMNS, *REGISTRY_OPTIONAL_COLUMNS])
        .sort_values(["layer", "code"])
        .reset_index(drop=True)[[*kept, *add_columns]]
    )
    table.attrs["title"] = "Registry"
    return table


def rules_table(rules: list[Rule], add_columns: list[str] | None = None,
                drop_columns: list[str] | None = None) -> pd.DataFrame:
    """One row per rule, rather than per code.

    `codes_hit_count` is a count rather than the code list, so a rule touching
    many codes does not blow the table apart; `add_columns=["codes"]` gives the
    detail.
    """

    add_columns = list(add_columns or [])
    _reject_unknown_columns(add_columns, RULE_OPTIONAL_COLUMNS, "the rules table")
    columns = [*_keep_columns(RULES_BASE_COLUMNS, drop_columns, "the rules table"),
               *add_columns]

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

    table = pd.DataFrame(rows, columns=columns)
    table.attrs["title"] = "Rules"
    return table
