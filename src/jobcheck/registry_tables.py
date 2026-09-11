"""The registry, the rules, and the relationship between them, as tables.

Printing is a separate job from registering and from evaluating, and it is the
job that grows: every question a person asks about the configuration ("what is
off by default?", "which rules could touch this code?", "where is this check
defined?") becomes another column rather than another engine feature.

Every function here returns the DataFrame it prints, so a caller can take the
data without the output. :mod:`jobcheck.tables` does the rendering; this module
decides what goes in the table.

Each table has the columns a reader always wants, and takes ``extra_columns``
for the ones only some readers do -- the same argument, with the same meaning,
as :func:`jobcheck.build_report` takes for columns of the data.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .registry import CHECKS
from .rules import OverrideRule
from .tables import _check_extra_columns, format_table

#: Extra columns the check tables offer. ``source_file`` is where the check was
#: registered; ``could_be_overridden_by`` needs the loaded rules, so only the
#: tables that are given them offer it.
CHECK_EXTRA_COLUMNS = ["source_file"]
REGISTRY_EXTRA_COLUMNS = ["source_file", "could_be_overridden_by"]
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
    """One row per registered check.

    ``layer`` and ``depends_on`` are base columns, not optional: what a check
    requires, and how deep it sits in the dependency graph, change whether it
    runs at all. Rows are ordered layer, then code, so the fundamental checks
    read first. ``extra_columns`` accepts ``source_file``, which is long enough
    to be worth asking for rather than always printing.

    What a check is *for* is its message, printed wherever it fails; there is no
    second description field to keep in step with it.
    """

    extra_columns = list(extra_columns or [])
    _check_extra_columns(extra_columns, CHECK_EXTRA_COLUMNS, "the registry table")
    columns = ["code", "layer", "default_state", "message", "depends_on", *extra_columns]

    rows: list[dict[str, Any]] = []
    for check in CHECKS:
        rows.append({
            "code": check.code,
            "layer": check.layer,
            "default_state": "ON" if check.default_enabled else "OFF",
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

    ``extra_columns`` adds ``source_file`` or ``could_be_overridden_by``, which
    lists the rules that *reference* each code. That column deliberately is not
    called "was overridden by": whether a rule actually fires depends on the row
    it is matched against, and this table has no row. Only
    :func:`resolve_enabled_state` can answer that.
    """

    extra_columns = list(extra_columns or [])
    _check_extra_columns(extra_columns, REGISTRY_EXTRA_COLUMNS, "the registry table")
    table = get_registry_table(
        extra_columns=[c for c in extra_columns if c in CHECK_EXTRA_COLUMNS])
    if table.empty:
        print("No checks registered.")
        return table

    if "could_be_overridden_by" in extra_columns:
        rules = overrides or []
        table["could_be_overridden_by"] = [
            "; ".join(r.name for r in _rules_for_code(code, rules)) or "-" for code in table["code"]
        ]

    print(format_table(table, wrap_columns={"message": 40, "could_be_overridden_by": 30}))
    return table


def print_registry_with_overrides(
    overrides: list[OverrideRule], extra_columns: list[str] | None = None
) -> pd.DataFrame:
    """Print the registry cross-referenced against the loaded override rules.

    ``effective_state`` states a plain "DEFAULT (ON/OFF)" for any code no rule
    references, so a reader never has to infer that from an empty cell.  When
    rules do reference a code the honest answer is row-dependent, and the cell
    says so rather than inventing one.
    """

    extra_columns = list(extra_columns or [])
    _check_extra_columns(extra_columns, CHECK_EXTRA_COLUMNS, "the registry table")
    base = get_registry_table(extra_columns=extra_columns)
    if base.empty:
        print("No checks registered.")
        return base

    columns = ["code", "layer", "default_state", "override_rules", "effective_state",
               *extra_columns]

    rows: list[dict[str, Any]] = []
    for _, entry in base.iterrows():
        code = str(entry["code"])
        matching = _rules_for_code(code, overrides)
        default_state = str(entry["default_state"])
        if matching:
            effective = f"depends on row (default {default_state} unless a rule above matches)"
        else:
            effective = f"DEFAULT ({default_state})"
        row: dict[str, Any] = {
            "code": code,
            "layer": entry["layer"],
            "default_state": default_state,
            "override_rules": "; ".join(f"{r.name} ({r.action})" for r in matching) or "-",
            "effective_state": effective,
        }
        for column in extra_columns:
            row[column] = entry[column]
        rows.append(row)

    table = pd.DataFrame(rows, columns=columns)
    print(format_table(table, wrap_columns={"override_rules": 34, "effective_state": 34}))
    return table


def print_override_rules(
    overrides: list[OverrideRule], extra_columns: list[str] | None = None
) -> pd.DataFrame:
    """Print one row per override rule (rather than per code).

    ``message`` is the rule author's line about why the rule exists, and is a
    base column for the same reason a check's message is printed on failure: a
    rule nobody can justify is a rule nobody dares delete. ``codes_hit_count``
    is a count, not the code list, so a rule touching many codes does not blow
    the table apart; :func:`list_rule_codes` gives the detail when it is wanted.
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
