"""Override rules: the YAML format that switches checks on and off per row.

The file format, its parser, and the matching it drives. Nothing here knows how a
check is registered or evaluated -- the loaders are handed the set of codes that
exist, so this module never reaches back into the registry.

A rule file is a flat list of rules. Precedence is positional: for a given row,
the last matching rule wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .tables import is_null




# Every key a rule may carry. Anything else is a typo, and rejected as one.
RULE_KEYS = {"name", "action", "codes", "match", "description"}


@dataclass
class MatchCriterion:
    """One ``{column, pattern}`` filter inside an override rule's ``match``."""

    column: str
    pattern: str
    regex: re.Pattern[str]


@dataclass
class OverrideRule:
    """A non-developer instruction to enable or disable codes for matching rows.

    ``match_all`` records that the YAML said ``match: all`` -- an explicit
    opt-in wildcard.  It is a separate flag rather than "empty criteria list"
    so that an accidentally empty list can never be mistaken for a deliberate
    match-everything rule.
    """

    name: str
    action: str
    codes: list[str]
    criteria: list[MatchCriterion]
    match_all: bool
    description: str = ""
    source_file: str = ""


def parse_match(raw: Any, rule_name: str, source_file: str) -> tuple[list[MatchCriterion], bool]:
    """Parse a rule's ``match`` value into criteria plus a match-everything flag.

    ``match: all`` is the only accepted wildcard.  A bare ``match: []`` is
    rejected rather than treated as "every row": an empty list is far more
    likely to be an accidental omission (a criterion deleted, a template left
    unfilled) than an intentional global rule, and getting that wrong silently
    disables checks across a whole dataset.  A missing ``match`` key is
    rejected for the same reason -- it defaults to nothing at all.
    """

    where = f"rule {rule_name!r} in {source_file}"
    if raw is None:
        raise ValueError(f"{where}: missing 'match'. Use 'match: all' to apply the rule to every row.")
    if isinstance(raw, str):
        if raw != "all":
            raise ValueError(f"{where}: 'match' must be a list of criteria or the literal 'all', got {raw!r}.")
        return [], True
    if not isinstance(raw, list):
        raise ValueError(f"{where}: 'match' must be a list of criteria or the literal 'all', got {type(raw).__name__}.")
    if not raw:
        raise ValueError(f"{where}: 'match' is an empty list. Use 'match: all' if you really mean every row.")

    criteria: list[MatchCriterion] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: each 'match' entry must be a mapping with 'column' and 'pattern'.")
        if "column" not in entry or "pattern" not in entry:
            raise ValueError(f"{where}: 'match' entry {entry!r} needs both 'column' and 'pattern'.")
        column = entry["column"]
        pattern = entry["pattern"]
        if not isinstance(column, str) or not isinstance(pattern, str):
            raise ValueError(f"{where}: 'column' and 'pattern' must both be strings in {entry!r}.")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"{where}: invalid regex {pattern!r} for column {column!r}: {exc}") from exc
        criteria.append(MatchCriterion(column=column, pattern=pattern, regex=regex))
    return criteria, False


def parse_rule(raw: Any, source_file: str, known_codes: set[str]) -> OverrideRule:
    """Validate and build one rule, failing loudly at load time.

    Every problem is raised here rather than when the rule is first applied to
    a row, so a malformed YAML file is reported once at start-up instead of
    part-way through a long pipeline run. That includes an unrecognised key: in
    a file edited by hand, a misspelled key is a setting that silently does
    nothing, which is worse than being told about it.
    """

    if not isinstance(raw, dict):
        raise ValueError(f"{source_file}: each rule must be a mapping, got {type(raw).__name__}.")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{source_file}: every rule needs a non-empty string 'name'.")

    unknown = sorted(set(raw) - RULE_KEYS)
    if unknown:
        raise ValueError(
            f"rule {name!r} in {source_file}: unknown key(s) {', '.join(unknown)}. "
            f"Allowed: {', '.join(sorted(RULE_KEYS))}."
        )

    action = raw.get("action")
    if action not in ("enable", "disable"):
        raise ValueError(f"rule {name!r} in {source_file}: 'action' must be exactly 'enable' or 'disable', got {action!r}.")

    codes = raw.get("codes")
    if not isinstance(codes, list) or not codes or not all(isinstance(c, str) for c in codes):
        raise ValueError(f"rule {name!r} in {source_file}: 'codes' must be a non-empty list of code strings.")

    for code in codes:
        if code not in known_codes:
            raise ValueError(
                f"rule {name!r} in {source_file}: unknown code {code!r}. "
                "Load the suite that defines it before loading overrides, or fix the code."
            )

    criteria, match_all = parse_match(raw.get("match"), name, source_file)
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise ValueError(f"rule {name!r} in {source_file}: 'description' must be a string.")

    return OverrideRule(
        name=name,
        action=action,
        codes=list(codes),
        criteria=criteria,
        match_all=match_all,
        description=description,
        source_file=source_file,
    )


def parse_file(path: str, known_codes: set[str]) -> list[OverrideRule]:
    """Parse one YAML file into rules. The file is a flat top-level list."""

    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(
            f"{path}: override files must contain a flat top-level list of rules "
            f"(no 'rules:' key), got {type(raw).__name__}."
        )
    return [parse_rule(entry, path, known_codes) for entry in raw]


def combine(paths: list[str], known_codes: set[str]) -> list[OverrideRule]:
    """Parse several files, rejecting duplicate rule names across all of them.

    Duplicate names are caught across the whole load, not per file: the name is
    how a person refers to a rule in :func:`list_rule_codes` and in error
    messages, so two rules sharing one is ambiguous even when they came from
    different directories.  Precedence follows the order of *paths*.
    """

    seen: dict[str, str] = {}
    rules: list[OverrideRule] = []
    for path in paths:
        for rule in parse_file(path, known_codes):
            if rule.name in seen:
                raise ValueError(
                    f"Duplicate override rule name {rule.name!r}: defined in {seen[rule.name]} and again in {rule.source_file}."
                )
            seen[rule.name] = rule.source_file
            rules.append(rule)
    return rules


def load_overrides(path: str, known_codes: set[str]) -> list[OverrideRule]:
    """Load override rules from a single YAML file."""

    return combine([path], known_codes)


def load_overrides_from_dir(
    directory: str, known_codes: set[str], pattern: str = "*.yaml"
) -> list[OverrideRule]:
    """Load every matching file in one directory, sorted alphabetically.

    Alphabetical order is the load order, and load order decides "last rule
    wins", so filenames carry precedence: name files ``01_x.yaml``,
    ``02_y.yaml`` when the ordering between them matters.
    """

    paths = sorted(str(p) for p in Path(directory).glob(pattern))
    return combine(paths, known_codes)


def load_overrides_from_files(paths: list[str], known_codes: set[str]) -> list[OverrideRule]:
    """Load an explicit list of files, which need not share a directory.

    Precedence follows the order given on the command line, not alphabetical or
    filesystem order.
    """

    return combine(list(paths), known_codes)


def cell_text(row: "pd.Series[Any]", column: str) -> str | None:
    """Row value as text for regex matching; ``None`` when absent or null."""

    if column not in row.index:
        return None
    value = row[column]
    if value is None or is_null(value):
        return None
    return str(value)


def rule_matches(rule: OverrideRule, row: "pd.Series[Any]") -> bool:
    """Whether every criterion of *rule* matches *row* (AND semantics).

    A criterion naming a column the row does not have, or whose value is null,
    does not match: an absent value cannot satisfy a pattern.
    """

    if rule.match_all:
        return True
    for criterion in rule.criteria:
        text = cell_text(row, criterion.column)
        if text is None or not criterion.regex.search(text):
            return False
    return True


def check_rule_columns(df: pd.DataFrame, overrides: list[OverrideRule]) -> list[str]:
    """Warn about columns an override rule matches on that the data lacks.

    A criterion naming a column that is not there never matches, so the rule
    silently never applies -- the one rule mistake nothing else catches, since
    the loader validates codes and patterns but has no data to compare against.

    Returns one human-readable line per problem, empty when every criterion
    column is present. It warns rather than raises: a rule file may deliberately
    cover several data shapes, only some of which carry the column.

    Checks are not checked here. They read the row themselves, so a missing field
    raises from the check and is recorded as a :data:`Status.ERROR` outcome
    naming the column, rather than passing silently.
    """

    present = set(df.columns)
    warnings: list[str] = []
    for rule in overrides:
        for criterion in rule.criteria:
            if criterion.column not in present:
                warnings.append(
                    f"rule {rule.name!r} matches on column {criterion.column!r}, which is not "
                    "in the data: the rule will never apply"
                )
    return warnings
