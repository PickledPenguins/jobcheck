"""The registry, the rules, and the relationship between them, as tables -- and
the one rule warning that needs the registry to give.

Kept apart from registering and evaluating because it is the job that grows:
every question about the configuration becomes another column rather than
another engine feature. Each table carries the columns a reader always wants and
takes `add_columns` for the ones only some readers do, and each carries its own
title in `attrs["title"]`.
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
    # Read once per check, so a generator is made a list first.
    rules = list(rules or [])

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


def warn_blocking_rules(rules: list[Rule]) -> list[str]:
    """Warn about disable rules that switch off more than they name.

    A check runs only once its prerequisites passed, so disabling one skips
    everything that depends on it, directly or not, on every row the rule
    matches -- and a skipped check reports nothing. One line per rule and
    disabled code, naming the dependents the rule does not itself disable:
    listing them in the rule says the silence is meant, and ends the warning.
    Needs the registry, which is why it lives here rather than beside
    `warn_shadowed_rules`.
    """

    order = _get_topo_order()
    dependents: dict[str, list[str]] = {check.code: [] for check in order}
    for check in order:
        for prerequisite in check.depends_on:
            dependents[prerequisite].append(check.code)
    rank = {check.code: (check.layer, check.code) for check in order}

    def below(code: str) -> set[str]:
        """Every check depending on *code*, directly or through others."""

        found: set[str] = set()
        waiting = list(dependents.get(code, []))
        while waiting:
            dependent = waiting.pop()
            if dependent not in found:
                found.add(dependent)
                waiting.extend(dependents[dependent])
        return found

    warnings: list[str] = []
    for rule in list(rules):
        if rule.action != "disable":
            continue
        reach = {code: below(code) for code in rule.codes}
        for code in rule.codes:
            # A code below another one the rule disables is silent either way;
            # naming it again would repeat that code's warning.
            if any(code in reach[other] for other in rule.codes if other != code):
                continue
            blocked = sorted(reach[code] - set(rule.codes), key=rank.__getitem__)
            if blocked:
                warnings.append(
                    f"rule {rule.name!r} disables {code}, which also stops "
                    f"{', '.join(blocked)} on the rows it matches: a check whose "
                    "prerequisite is off is skipped, and reports nothing"
                )
    return warnings


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
