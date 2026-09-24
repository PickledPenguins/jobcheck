"""The registry, the rules, and the relationship between them, as tables.

Printing is kept apart from registering and evaluating because it is the job
that grows: every question about the configuration becomes another column rather
than another engine feature. Each table carries the columns a reader always
wants and takes `add_columns` for the ones only some readers do.

Every function here returns the DataFrame it prints, so a caller can take the data
without printing it twice. That is the package-wide rule, and it is about who owns
the frame rather than about the `print_` prefix: a function that *builds* a frame
returns it, and a function *handed* one returns nothing, or the artifact it made
instead. `report.py` holds the other side -- `print_report` and `write_report` take
a built report and return `None`, `render_report` returns its text.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .registry import _CHECKS
from .rules import Rule
from .tables import _keep_columns, _print_title, _reject_unknown_columns, format_table

#: The columns each table always has, before `add_columns` adds to them and after
#: `drop_columns` takes from them. Named rather than inline so both arguments are
#: validated against the same list a reader can find.
REGISTRY_BASE_COLUMNS = ["code", "layer", "default", "message", "depends_on"]
RULES_BASE_COLUMNS = ["name", "action", "codes_hit_count", "match", "message"]

#: Optional columns the check tables offer. ``source_file`` is where the check was
#: registered; ``could_be_overridden_by`` and ``effective_state`` read the loaded
#: rules, so only :func:`print_registry`, which is given them, offers those two.
CHECK_OPTIONAL_COLUMNS = ["source_file"]
REGISTRY_OPTIONAL_COLUMNS = ["source_file", "could_be_overridden_by", "effective_state"]
RULE_OPTIONAL_COLUMNS = ["source_file"]


def _rules_for_code(code: str, rules: list[Rule]) -> list[Rule]:
    """Rules that reference *code*, in load order."""

    return [rule for rule in rules if code in rule.codes]


def _render_match(rule: Rule) -> str:
    """Compact one-cell rendering of a rule's match criteria."""

    if rule.match_all:
        return "all"
    return "; ".join(f"{criterion.column}~=/{criterion.pattern}/"
                     for criterion in rule.criteria)


def get_registry_table(add_columns: list[str] | None = None,
                       drop_columns: list[str] | None = None) -> pd.DataFrame:
    """One row per registered check, ordered layer then code, so the fundamental
    checks read first.

    `layer` and `depends_on` are base columns rather than optional ones: what a
    check requires, and how deep it sits, decide whether it runs at all. They can
    still be dropped -- `drop_columns` is a caller's choice about their own
    output, not a judgement about which columns matter.
    """

    add_columns = list(add_columns or [])
    _reject_unknown_columns(add_columns, CHECK_OPTIONAL_COLUMNS, "the registry table")
    columns = [*_keep_columns(REGISTRY_BASE_COLUMNS, drop_columns, "the registry table"),
               *add_columns]

    rows: list[dict[str, Any]] = []
    for check in _CHECKS:
        rows.append({
            "code": check.code,
            "layer": check.layer,
            "default": "ON" if check.default_enabled else "OFF",
            "message": check.message,
            "depends_on": "; ".join(check.depends_on) if check.depends_on else "-",
            "source_file": check.source_file,
        })

    # Built with every column, sorted, and only then narrowed to the ones asked
    # for: `layer` and `code` are what the sort reads, and `drop_columns` is
    # allowed to take either out. Columns are passed explicitly so an empty
    # registry still yields a frame with columns to sort by; pd.DataFrame([])
    # has none and sort_values raises.
    return (
        pd.DataFrame(rows, columns=[*REGISTRY_BASE_COLUMNS, *CHECK_OPTIONAL_COLUMNS])
        .sort_values(["layer", "code"])
        .reset_index(drop=True)[columns]
    )


def print_registry(
    rules: list[Rule] | None = None, add_columns: list[str] | None = None,
    title: bool = True, drop_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Print the registry table, under its own heading, and return the frame.

    `could_be_overridden_by` and `effective_state` are the two added columns that
    read the rules, and `rules` feeds nothing else -- passing rules without
    asking for either prints the same table as passing none.

    Neither is "was overridden by": whether a rule fires depends on the row it is
    matched against, and this table has no row.
    """

    add_columns = list(add_columns or [])
    _reject_unknown_columns(add_columns, REGISTRY_OPTIONAL_COLUMNS, "the registry table")
    # Dropped at the end rather than passed down: the two rules-derived columns are
    # computed from this table's own `code` and `default`, so a caller dropping
    # either would otherwise take them out from under it.
    kept = _keep_columns(REGISTRY_BASE_COLUMNS, drop_columns, "the registry table")
    table = get_registry_table(
        add_columns=[name for name in add_columns if name in CHECK_OPTIONAL_COLUMNS])
    rules = rules or []
    if title:
        _print_title("Registry", f"{len(table)} check(s)",
                     f"{len(rules)} rule(s) considered" if rules else "")
    if table.empty:
        print("No checks registered.")
        return table
    matching = {code: _rules_for_code(code, rules) for code in table["code"]}
    if "could_be_overridden_by" in add_columns:
        table["could_be_overridden_by"] = [
            "; ".join(f"{rule.name} ({rule.action})" for rule in matching[code]) or "-"
            for code in table["code"]
        ]
    if "effective_state" in add_columns:
        table["effective_state"] = [
            f"depends on row (default {state} unless a rule above matches)"
            if matching[code] else f"DEFAULT ({state})"
            for code, state in zip(table["code"], table["default"])
        ]

    table = table[[name for name in table.columns if name in kept or name in add_columns]]
    print(format_table(table, wrap_columns={"message": 40, "could_be_overridden_by": 34,
                                            "effective_state": 34}))
    return table


def get_rules_table(rules: list[Rule], add_columns: list[str] | None = None,
                    drop_columns: list[str] | None = None) -> pd.DataFrame:
    """One row per rule, rather than per code.

    The data behind `print_rules`, so a caller can have the frame without the
    output -- every other table here and in `report.py` offers that, and this one
    did not.

    `codes_hit_count` is a count rather than the code list, so a rule touching
    many codes does not blow the table apart; `list_rule_codes` gives the detail.
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
            "match": _render_match(rule),
            "message": rule.message,
            "source_file": rule.source_file,
        })

    return pd.DataFrame(rows, columns=columns)


def print_rules(
    rules: list[Rule], add_columns: list[str] | None = None, title: bool = True,
    drop_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Print the rules table, under its own heading, and return the frame."""

    if title:
        _print_title("Rules", f"{len(rules)} loaded")
    table = get_rules_table(rules, add_columns=add_columns, drop_columns=drop_columns)
    if table.empty:
        print("No rules loaded.")
        return table
    print(format_table(table, wrap_columns={"match": 44, "message": 40}))
    return table


def list_rule_codes(rule_name: str, rules: list[Rule]) -> list[str]:
    """Print and return the exact codes one named rule touches."""

    for rule in rules:
        if rule.name == rule_name:
            print(f"{rule.name} ({rule.action}) -> " + ", ".join(rule.codes))
            return list(rule.codes)
    known = ", ".join(rule.name for rule in rules) or "(none loaded)"
    raise ValueError(f"No rule named {rule_name!r}. Loaded rules: {known}")
