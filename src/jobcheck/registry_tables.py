"""The registry, the rules, and the relationship between them, as tables.

Printing is kept apart from registering and evaluating because it is the job
that grows: every question about the configuration becomes another column rather
than another engine feature. Each table carries the columns a reader always
wants and takes `extra_columns` for the ones only some readers do.

Every function returns the DataFrame it prints, so a caller can take the data
without the output.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .registry import CHECKS
from .rules import OverrideRule
from .tables import _check_extra_columns, format_table

#: Extra columns the check tables offer. ``source_file`` is where the check was
#: registered; ``could_be_overridden_by`` and ``effective_state`` read the loaded
#: rules, so only :func:`print_registry`, which is given them, offers those two.
CHECK_EXTRA_COLUMNS = ["source_file"]
REGISTRY_EXTRA_COLUMNS = ["source_file", "could_be_overridden_by", "effective_state"]
RULE_EXTRA_COLUMNS = ["source_file"]


def _rules_for_code(code: str, overrides: list[OverrideRule]) -> list[OverrideRule]:
    """Rules that reference *code*, in load order."""

    return [r for r in overrides if code in r.codes]


def _render_match(rule: OverrideRule) -> str:
    """Compact one-cell rendering of a rule's match criteria."""

    if rule.match_all:
        return "all"
    return "; ".join(f"{c.column}~=/{c.pattern}/" for c in rule.criteria)


def get_registry_table(extra_columns: list[str] | None = None) -> pd.DataFrame:
    """One row per registered check, ordered layer then code, so the fundamental
    checks read first.

    `layer` and `depends_on` are base columns, not optional: what a check
    requires, and how deep it sits, decide whether it runs at all.
    """

    extra_columns = list(extra_columns or [])
    _check_extra_columns(extra_columns, CHECK_EXTRA_COLUMNS, "the registry table")
    columns = ["code", "layer", "default", "message", "depends_on", *extra_columns]

    rows: list[dict[str, Any]] = []
    for check in CHECKS:
        rows.append({
            "code": check.code,
            "layer": check.layer,
            "default": "ON" if check.default_enabled else "OFF",
            "message": check.message,
            "depends_on": "; ".join(check.depends_on) if check.depends_on else "-",
            "source_file": check.source_file,
        })

    # Columns are passed explicitly so an empty registry still yields a frame
    # with columns to sort by; pd.DataFrame([]) has none and sort_values raises.
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["layer", "code"])
        .reset_index(drop=True)
    )


def print_registry(
    overrides: list[OverrideRule] | None = None, extra_columns: list[str] | None = None
) -> pd.DataFrame:
    """Print the registry table and return the frame behind it.

    `could_be_overridden_by` and `effective_state` are the two extra columns that
    read the rules, and `overrides` feeds nothing else -- passing rules without
    asking for either prints the same table as passing none.

    Neither is "was overridden by": whether a rule fires depends on the row it is
    matched against, and this table has no row.
    """

    extra_columns = list(extra_columns or [])
    _check_extra_columns(extra_columns, REGISTRY_EXTRA_COLUMNS, "the registry table")
    table = get_registry_table(
        extra_columns=[c for c in extra_columns if c in CHECK_EXTRA_COLUMNS])
    if table.empty:
        print("No checks registered.")
        return table

    rules = overrides or []
    matching = {code: _rules_for_code(code, rules) for code in table["code"]}
    if "could_be_overridden_by" in extra_columns:
        table["could_be_overridden_by"] = [
            "; ".join(f"{r.name} ({r.action})" for r in matching[code]) or "-"
            for code in table["code"]
        ]
    if "effective_state" in extra_columns:
        table["effective_state"] = [
            f"depends on row (default {state} unless a rule above matches)"
            if matching[code] else f"DEFAULT ({state})"
            for code, state in zip(table["code"], table["default"])
        ]

    print(format_table(table, wrap_columns={"message": 40, "could_be_overridden_by": 34,
                                            "effective_state": 34}))
    return table


def print_override_rules(
    overrides: list[OverrideRule], extra_columns: list[str] | None = None
) -> pd.DataFrame:
    """Print one row per override rule, rather than per code.

    `codes_hit_count` is a count rather than the code list, so a rule touching
    many codes does not blow the table apart; `list_rule_codes` gives the detail.
    """

    extra_columns = list(extra_columns or [])
    _check_extra_columns(extra_columns, RULE_EXTRA_COLUMNS, "the override rules table")
    columns = ["name", "action", "codes_hit_count", "match", "message", *extra_columns]

    rows: list[dict[str, Any]] = []
    for rule in overrides:
        rows.append({
            "name": rule.name,
            "action": rule.action,
            "codes_hit_count": len(rule.codes),
            "match": _render_match(rule),
            "message": rule.message,
            "source_file": rule.source_file,
        })

    table = pd.DataFrame(rows, columns=columns)
    if table.empty:
        print("No override rules loaded.")
        return table
    print(format_table(table, wrap_columns={"match": 44, "message": 40}))
    return table


def list_rule_codes(rule_name: str, overrides: list[OverrideRule]) -> list[str]:
    """Print and return the exact codes one named rule touches."""

    for rule in overrides:
        if rule.name == rule_name:
            print(f"{rule.name} ({rule.action}) -> " + ", ".join(rule.codes))
            return list(rule.codes)
    known = ", ".join(r.name for r in overrides) or "(none loaded)"
    raise ValueError(f"No override rule named {rule_name!r}. Loaded rules: {known}")
