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

from .paths import _key_names, _read_yaml, _resolve_input_file
from .tables import _format_cell, is_null


# Every key a rule may carry. Anything else is a typo, and rejected as one.
_RULE_KEYS = {"name", "action", "codes", "match", "message"}
# The same for one criterion in a rule's `match`.
_CRITERION_KEYS = {"column", "pattern"}


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


def _parse_match(raw: Any, rule_name: str, source_file: str) -> tuple[list[_MatchCriterion], bool]:
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
        # Refused like a rule's unknown key: `negate: true` read as nothing would
        # disable the checks on exactly the rows the author meant to exempt.
        unknown = set(entry) - _CRITERION_KEYS
        if unknown:
            raise ValueError(
                f"{where}: 'match' entry {entry!r} has unknown key(s) {_key_names(unknown)}. "
                "A criterion holds only 'column' and 'pattern'.")
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


def _parse_rule(raw: Any, source_file: str, known_codes: set[str], position: int) -> Rule:
    """Validate and build one rule, failing at load time rather than part-way
    through a long run.

    An unrecognized key is refused too: in a hand-edited file, a misspelled key
    is a setting that silently does nothing. *position* is the rule's place in
    its file, counted from 1.
    """

    if not isinstance(raw, dict):
        raise ValueError(f"{source_file}: each rule must be a mapping, got {type(raw).__name__}.")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        # No name to show, so the rule's place in the file identifies it.
        raise ValueError(
            f"{source_file}: rule {position}: every rule needs a non-empty string 'name', "
            f"got {name!r}.")

    unknown = set(raw) - _RULE_KEYS
    if unknown:
        raise ValueError(
            f"rule {name!r} in {source_file}: unknown key(s) {_key_names(unknown)}. "
            f"Allowed: {_key_names(_RULE_KEYS)}."
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
            f"code strings, got {codes!r}.")

    for code in codes:
        if code not in known_codes:
            raise ValueError(
                f"rule {name!r} in {source_file}: unknown code {code!r}. "
                "Load the check file that defines it before loading rules, or fix the code."
            )

    criteria, match_all = _parse_match(raw.get("match"), name, source_file)
    message = raw.get("message")
    if not isinstance(message, str) or not message:
        raise ValueError(
            f"rule {name!r} in {source_file}: 'message' must be the text saying why the "
            f"rule exists, got {message!r}. It is printed beside the rule wherever the "
            "rules are listed."
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


def _parse_file(path: str, known_codes: set[str],
               base_dir: str | Path | None = None) -> list[Rule]:
    """Parse one YAML file into rules. The file is a flat top-level list.

    The rules record the path as the caller wrote it, relative or not: it is
    printed beside a rule wherever the rules are listed, and an absolute path
    there would be this machine's, not the one the caller would recognize.
    """

    raw = _read_yaml(_resolve_input_file(path, "rule file", "load_rules()", base_dir), path)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(
            f"{path}: rule files must contain a flat top-level list of rules "
            f"(no 'rules:' key), got {type(raw).__name__}."
        )
    return [_parse_rule(entry, path, known_codes, position)
            for position, entry in enumerate(raw, start=1)]


def _load_rule_files(paths: list[str], known_codes: set[str],
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
        for rule in _parse_file(path, known_codes, base_dir):
            if rule.name in seen:
                raise ValueError(
                    f"Duplicate rule name {rule.name!r}: defined in "
                    f"{seen[rule.name]} and again in {rule.source_file}."
                )
            seen[rule.name] = rule.source_file
            loaded.append(rule)
    return loaded


def _cell_text(row: "pd.Series[Any]", column: str) -> str | None:
    """Row value as text for regex matching, rendered as the report prints it;
    ``None`` when absent or null."""

    if column not in row.index:
        return None
    value = row[column]
    if value is None or is_null(value):
        return None
    return _format_cell(value)


def _rule_matches(rule: Rule, row: "pd.Series[Any]") -> bool:
    """Whether every criterion of *rule* matches *row* (AND semantics).

    An absent or null value cannot satisfy a pattern, so it does not match.
    """

    if rule.match_all:
        return True
    for criterion in rule.criteria:
        text = _cell_text(row, criterion.column)
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
    for rule in list(rules):
        for criterion in rule.criteria:
            if criterion.column not in present:
                warnings.append(
                    f"rule {rule.name!r} matches on column {criterion.column!r}, which is not "
                    "in the data: the rule will never apply"
                )
    return warnings


def warn_shadowed_rules(rules: list[Rule]) -> list[str]:
    """Warn about rules a later rule overrules for every row.

    The last matching rule wins, so a rule touching a code can never apply to it
    once a *later* rule touches the same code with `match: all`. Only that case:
    whether two conditional rules overlap depends on their patterns, and is not
    guessed. Reported per code, since a rule with several codes can be overruled
    for one and decisive for another. Warns rather than raises, because a
    shadowed rule can be deliberate (`examples/rules/error_rules.yaml` has one).
    """

    # Read more than once below, so a generator is made a list first.
    rules = list(rules)
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
