"""Rules: the YAML format that switches checks on and off per row.

Nothing here knows how a check is registered or evaluated -- the loaders are
handed the codes that exist, so this module never reaches into the registry.
A rule file is a flat list, and for a given row the last matching rule wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .paths import resolve_input_file
from .tables import _format_cell, is_null




# Every key a rule may carry. Anything else is a typo, and rejected as one.
RULE_KEYS = {"name", "action", "codes", "match", "message"}


@dataclass
class _MatchCriterion:
    """One ``{column, pattern}`` filter inside a rule's ``match``."""

    column: str
    pattern: str
    regex: re.Pattern[str]


@dataclass
class Rule:
    """A non-developer instruction to enable or disable codes for matching rows.

    `match_all` is a flag rather than "empty criteria list" so an accidentally
    empty list can never be mistaken for a deliberate match-everything rule.
    `message` is required, and printed, because a rule nobody can justify is a
    rule nobody dares delete.
    """

    name: str
    action: str
    codes: list[str]
    criteria: list[_MatchCriterion]
    match_all: bool
    message: str
    source_file: str = ""


def parse_match(raw: Any, rule_name: str, source_file: str) -> tuple[list[_MatchCriterion], bool]:
    """Parse a rule's `match` value into criteria plus a match-everything flag.

    `match: all` is the only wildcard: an empty or missing `match` is rejected
    rather than read as "every row", since it is far likelier to be an omission,
    and getting that wrong disables checks across a whole dataset silently.
    """

    where = f"rule {rule_name!r} in {source_file}"
    if raw is None:
        raise ValueError(
            f"{where}: missing 'match'. Use 'match: all' to apply the rule to every row.")
    if isinstance(raw, str):
        if raw != "all":
            raise ValueError(
                f"{where}: 'match' must be a list of criteria or the literal 'all', "
                f"got {raw!r}.")
        return [], True
    if not isinstance(raw, list):
        raise ValueError(
            f"{where}: 'match' must be a list of criteria or the literal 'all', "
            f"got {type(raw).__name__}.")
    if not raw:
        raise ValueError(
            f"{where}: 'match' is an empty list. Use 'match: all' if you really mean "
            "every row.")

    criteria: list[_MatchCriterion] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(
                f"{where}: each 'match' entry must be a mapping with 'column' and "
                "'pattern'.")
        if "column" not in entry or "pattern" not in entry:
            raise ValueError(
                f"{where}: 'match' entry {entry!r} needs both 'column' and 'pattern'.")
        column = entry["column"]
        pattern = entry["pattern"]
        if not isinstance(column, str) or not isinstance(pattern, str):
            raise ValueError(f"{where}: 'column' and 'pattern' must both be strings in {entry!r}.")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ValueError(
                f"{where}: invalid regex {pattern!r} for column {column!r}: {exc}") from exc
        criteria.append(_MatchCriterion(column=column, pattern=pattern, regex=regex))
    return criteria, False


def parse_rule(raw: Any, source_file: str, known_codes: set[str]) -> Rule:
    """Validate and build one rule, failing at load time rather than part-way
    through a long run.

    An unrecognized key is refused too: in a hand-edited file, a misspelled key
    is a setting that silently does nothing.
    """

    if not isinstance(raw, dict):
        raise ValueError(f"{source_file}: each rule must be a mapping, got {type(raw).__name__}.")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{source_file}: every rule needs a non-empty string 'name'.")

    # str(): YAML reads `on:` or `1:` as a bool or an int, which cannot be joined.
    unknown = sorted(str(key) for key in set(raw) - RULE_KEYS)
    if unknown:
        raise ValueError(
            f"rule {name!r} in {source_file}: unknown key(s) {', '.join(unknown)}. "
            f"Allowed: {', '.join(sorted(RULE_KEYS))}."
        )

    action = raw.get("action")
    if action not in ("enable", "disable"):
        raise ValueError(
            f"rule {name!r} in {source_file}: 'action' must be exactly 'enable' or "
            f"'disable', got {action!r}.")

    codes = raw.get("codes")
    if not isinstance(codes, list) or not codes or not all(isinstance(c, str) for c in codes):
        raise ValueError(
            f"rule {name!r} in {source_file}: 'codes' must be a non-empty list of "
            "code strings.")

    for code in codes:
        if code not in known_codes:
            raise ValueError(
                f"rule {name!r} in {source_file}: unknown code {code!r}. "
                "Load the check file that defines it before loading rules, or fix the code."
            )

    criteria, match_all = parse_match(raw.get("match"), name, source_file)
    message = raw.get("message")
    if not isinstance(message, str) or not message:
        raise ValueError(
            f"rule {name!r} in {source_file}: 'message' must be the text saying why the "
            "rule exists. It is printed beside the rule wherever the rules are listed."
        )

    return Rule(
        name=name,
        action=action,
        codes=list(codes),
        criteria=criteria,
        match_all=match_all,
        message=message,
        source_file=source_file,
    )


def parse_file(path: str, known_codes: set[str],
               base_dir: str | Path | None = None) -> list[Rule]:
    """Parse one YAML file into rules. The file is a flat top-level list.

    The rules record the path as the caller wrote it, relative or not: it is
    printed beside a rule wherever the rules are listed, and an absolute path
    there would be this machine's, not the one the caller would recognize.
    """

    with open(resolve_input_file(path, "rule file", "load_rules()", base_dir),
              "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(
            f"{path}: rule files must contain a flat top-level list of rules "
            f"(no 'rules:' key), got {type(raw).__name__}."
        )
    return [parse_rule(entry, path, known_codes) for entry in raw]


def load_rules(paths: list[str], known_codes: set[str],
                   base_dir: str | Path | None = None) -> list[Rule]:
    """Parse the named YAML files into rules, in the order given, which is also
    their precedence: for a given row, the last matching rule wins.

    Duplicate names are caught across the whole load, not per file -- the name is
    how a person refers to a rule, so two sharing one is ambiguous wherever they
    came from. *base_dir* anchors relative paths, as in `registry.load_checks`.
    """

    if isinstance(paths, str):
        raise TypeError(
            f"load_rules takes a list of paths, not one string: pass [{paths!r}]. "
            "A bare string would be read as a list of its characters."
        )
    seen: dict[str, str] = {}
    loaded: list[Rule] = []
    for path in list(paths):
        for rule in parse_file(path, known_codes, base_dir):
            if rule.name in seen:
                raise ValueError(
                    f"Duplicate rule name {rule.name!r}: defined in "
                    f"{seen[rule.name]} and again in {rule.source_file}."
                )
            seen[rule.name] = rule.source_file
            loaded.append(rule)
    return loaded


def cell_text(row: "pd.Series[Any]", column: str) -> str | None:
    """Row value as text for regex matching, rendered as the report prints it;
    ``None`` when absent or null."""

    if column not in row.index:
        return None
    value = row[column]
    if value is None or is_null(value):
        return None
    return _format_cell(value)


def rule_matches(rule: Rule, row: "pd.Series[Any]") -> bool:
    """Whether every criterion of *rule* matches *row* (AND semantics).

    An absent or null value cannot satisfy a pattern, so it does not match.
    """

    if rule.match_all:
        return True
    for criterion in rule.criteria:
        text = cell_text(row, criterion.column)
        if text is None or not criterion.regex.search(text):
            return False
    return True


def warn_missing_rule_columns(df: pd.DataFrame, rules: list[Rule]) -> list[str]:
    """Warn about columns a rule matches on that the data lacks.

    A criterion naming a column that is not there never matches, so the rule
    silently never applies, and the loader cannot catch it because it has no data
    to compare against. It warns rather than raises: one rule file may
    deliberately cover several data shapes. `warn_shadowed_rules` is the other
    half -- a rule that can never apply whatever the data says.
    """

    present = set(df.columns)
    warnings: list[str] = []
    for rule in rules:
        for criterion in rule.criteria:
            if criterion.column not in present:
                warnings.append(
                    f"rule {rule.name!r} matches on column {criterion.column!r}, which is not "
                    "in the data: the rule will never apply"
                )
    return warnings


def warn_shadowed_rules(rules: list[Rule]) -> list[str]:
    """Warn about rules a later rule overrules for every row.

    Precedence is positional and the last matching rule wins, so a rule that
    touches a code is dead for that code as soon as a *later* rule touches it
    with `match: all`: the later one matches every row, so the earlier one can
    never be the last match. Nothing else reports this. The registry table's
    `could_be_overridden_by` column lists both rules, and `effective_state` says
    "depends on row" -- correct in general, because whether a rule fires is a
    property of the row, but this is the one case where the answer is the same for
    every row and can be given.

    Only that case. Two conditional rules may overlap for some rows and not
    others, which needs the patterns compared rather than read, and a wrong answer
    there would be worse than no answer.

    Per code rather than per rule, because a rule carrying several codes can be
    overruled for one and decisive for another. Warns rather than raises: shipping
    a shadowed rule can be deliberate, and `examples/rules/error_rules.yaml`
    does it on purpose to demonstrate precedence.
    """

    warnings: list[str] = []
    seen: list[str] = []
    for rule in rules:
        for code in rule.codes:
            if code not in seen:
                seen.append(code)
    for code in seen:
        touching = [rule for rule in rules if code in rule.codes]
        unconditional = [index for index, rule in enumerate(touching) if rule.match_all]
        if not unconditional:
            continue
        winner = touching[unconditional[-1]]
        for rule in touching[:unconditional[-1]]:
            warnings.append(
                f"rule {rule.name!r} is overruled for {code} by the later rule "
                f"{winner.name!r}, which matches every row: it can never apply to {code}"
            )
    return warnings
