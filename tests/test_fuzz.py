"""Generated input, seeded so a failure reproduces.

Every example in the other suites was written by whoever wrote the code, which is
the weakness of examples. These feed the two parsers and the renderer input
nobody chose by hand, and assert the shape of the answer rather than its content:
either it works, or it fails the way the library says it fails, and never with an
unexpected exception type.

Seeded from a constant, so a failing case is reproducible; the seed appears in
the assertion message.
"""

from __future__ import annotations

import random
import string
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from conftest import first_cause, make_check
from jobcheck import (
    build_report,
    validate,
    load_rules,
    registry as reg,
)
from jobcheck.results import Outcome

pytestmark = pytest.mark.long

SEED = 20260902
CASES = 300

PIECES: list[Any] = [
    None, "", " ", "0", "-1", "1e400", "nan", "NaN", "=cmd", "@SUM(A1)", "-5",
    "a" * 200, "ü", "line\nbreak", "semi;colon", "pipe|value", '"quoted"', "tab\tsep",
    0, 1, -1, 2**63, 0.5, float("nan"), float("inf"), True, False,
    ["list"], {"dict": 1}, pd.Timestamp("2024-01-01"),
]


def random_scalar(rng: random.Random) -> Any:
    return rng.choice(PIECES)


def random_name(rng: random.Random) -> str:
    alphabet = string.ascii_letters + string.digits + "_-. "
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))


#: For each key, what the parser accepts and what it refuses. A rule is built by
#: drawing each key valid with high odds, so that whole rules come out valid
#: often enough to reach the matcher and the regex -- five keys each valid one
#: time in three would make a valid rule a one-in-two-hundred event.
VALID: dict[str, list[Any]] = {
    "name": ["r", "rule_one", "a b"],
    "action": ["enable", "disable"],
    "codes": [["A_CODE"], ["A_CODE", "B_CODE"]],
    "match": ["all", [{"column": "age", "pattern": "^1$"}],
              [{"column": "age", "pattern": "x"}, {"column": "email", "pattern": "@"}]],
    "message": ["why the rule exists", "kept for the audit"],
}
INVALID: dict[str, list[Any]] = {
    "name": ["", 7, None],
    "action": ["Enable", "toggle", 7, None],
    "codes": [["NOPE"], [], "A_CODE", [7]],
    "match": ["al", [], [{"column": "age"}], [{"column": 7, "pattern": "x"}],
              [{"column": "age", "pattern": "([unclosed"}], 7, None],
    "message": ["", 7, None],
}


def random_rule(rng: random.Random) -> Any:
    """A rule-shaped mapping: every key valid four times in five, each key
    missing one time in twenty, an unknown key added one time in ten."""
    rule: dict[str, Any] = {}
    for key in VALID:
        if rng.random() < 0.05:
            continue
        pool = VALID[key] if rng.random() < 0.8 else INVALID[key]
        rule[key] = rng.choice(pool)
    if rng.random() < 0.1:
        rule[random_name(rng) or "extra"] = 1
    return rule


def test_the_rule_parser_either_loads_or_raises_valueerror(
    fresh_registry: None, tmp_path: Path
) -> None:
    rng = random.Random(SEED)
    make_check("A_CODE")
    make_check("B_CODE")
    accepted_rules = rejected = 0

    for case in range(CASES):
        path = tmp_path / f"rules_{case}.yaml"
        rules = [random_rule(rng) for _ in range(rng.randint(0, 3))]
        path.write_text(yaml.safe_dump(rules, allow_unicode=True), encoding="utf-8")
        try:
            loaded = load_rules([str(path)])
        except ValueError as exc:
            rejected += 1
            assert str(path) in str(exc), f"seed {SEED} case {case}: error omits the file"
            continue
        accepted_rules += len(loaded)
        for rule in loaded:
            assert rule.action in ("enable", "disable")
            assert rule.codes
            assert rule.match_all or rule.criteria

    # Rules accepted, not files: an empty file loads as zero rules, so counting
    # files let a generator whose every rule was refused -- one required key
    # misspelled -- pass this for months while exercising nothing past the key
    # check. The floor is far below what the seed produces (about 40).
    assert accepted_rules >= 20, (
        f"seed {SEED}: only {accepted_rules} generated rules were accepted; "
        "the generator no longer produces valid rules")
    assert rejected, f"seed {SEED}: the generator stopped producing invalid rules"


#: Each key's value as a person types it: valid YAML text, then what
#: `yaml.safe_dump` never writes -- unquoted YAML 1.1 booleans and nulls, a date,
#: tags, an alias, quoting, and text that is not YAML at all.
VALID_TEXT: dict[str, list[str]] = {
    "action": ["enable", "disable"],
    "codes": ["[A_CODE]", "[A_CODE, B_CODE]", "\n    - A_CODE"],
    "match": ["all", "[{column: age, pattern: '^1$'}]",
              "\n    - column: age\n      pattern: x"],
    "message": ["why", '"kept: for the audit"'],
}
TYPED_TEXT = [
    "yes", "off", "No", "~", "null", "", "2024-01-01", "1e3", "0x1F", "'all'", '"A_CODE"',
    "!!binary aGk=", "!!set {A_CODE: null}", "!!python/object:os.system {}", "!!str 7",
    "*undefined", "[A_CODE", "{column: age", "@at", "%percent", "`tick",
    "\n    - column: age\n      pattern: x\n      pattern: y",
    "\n    - column: age\n      pattern: x\n      negate: true",
    "\n\t- A_CODE",
]


def random_rule_text(rng: random.Random, index: int) -> str:
    """One rule as YAML text: each key valid three times in four, else one of
    `TYPED_TEXT`; sometimes a key given twice, a key nobody defined, or the
    name left to YAML's typing. Nesting stays shallow: a deep one only
    reaches PyYAML's recursion limit, which is not this parser's to handle."""
    name = f"rule_{index}" if rng.random() < 0.9 else rng.choice(TYPED_TEXT)
    lines = [f"- name: {name}"]
    for key, valid in VALID_TEXT.items():
        if rng.random() < 0.05:
            continue
        value = rng.choice(valid) if rng.random() < 0.75 else rng.choice(TYPED_TEXT)
        lines.append(f"  {key}: {value}")
    if rng.random() < 0.05:
        lines.append(f"  action: {rng.choice(VALID_TEXT['action'])}")
    if rng.random() < 0.05:
        lines.append(f"  {random_name(rng) or 'extra'}: 1")
    return "\n".join(lines) + "\n"


def test_the_rule_parser_over_yaml_text_loads_or_says_which_file(
    fresh_registry: None, tmp_path: Path
) -> None:
    """The documented contract for a rule file: it loads, or it raises
    `ValueError` or `yaml.YAMLError` naming the file. Written as text, since only
    text holds a repeated key, an unquoted `off`, a tag, or bytes that are not
    UTF-8 -- the last is how a load error that named no file came to light."""

    rng = random.Random(SEED)
    make_check("A_CODE")
    make_check("B_CODE")
    accepted_rules = 0
    refused: dict[str, int] = {"ValueError": 0, "YAMLError": 0}

    for case in range(CASES):
        path = tmp_path / f"rules_{case}.yaml"
        text = "".join(random_rule_text(rng, index) for index in range(rng.randint(0, 3)))
        data = text.encode("utf-8")
        if data and rng.random() < 0.03:
            # One byte that cannot start a UTF-8 character, as a Latin-1 editor leaves.
            at = rng.randrange(len(data))
            data = data[:at] + b"\xe9" + data[at + 1:]
        path.write_bytes(data)
        try:
            loaded = load_rules([str(path)])
        except (ValueError, yaml.YAMLError) as exc:
            kind = "ValueError" if isinstance(exc, ValueError) else "YAMLError"
            refused[kind] += 1
            assert str(path) in str(exc), (
                f"seed {SEED} case {case}: {kind} omits the file: {exc}\n{text}")
            continue
        accepted_rules += len(loaded)
        for rule in loaded:
            assert rule.action in ("enable", "disable")
            assert rule.codes and all(isinstance(code, str) for code in rule.codes)
            assert rule.match_all or rule.criteria
            assert isinstance(rule.message, str) and rule.message

    # Floors far below what the seed produces, so a generator that stops
    # reaching either side is noticed.
    assert accepted_rules >= 20, f"seed {SEED}: only {accepted_rules} rules were accepted"
    assert all(refused.values()), f"seed {SEED}: a kind of refusal never happened: {refused}"


def random_frame(rng: random.Random) -> pd.DataFrame:
    columns = ["age", "email", "start_date", "end_date"]
    rows = [
        {column: random_scalar(rng) for column in columns}
        for _ in range(rng.randint(1, 4))
    ]
    return pd.DataFrame(rows)


def test_the_engine_holds_its_invariants_on_generated_frames(example_checks: None) -> None:
    """The three properties the whole design rests on, over input nobody chose:
    a check runs only when every prerequisite passed, the first failure is the
    lowest-layer failure, and no check appears twice in a row's outcomes."""

    rng = random.Random(SEED)
    for case in range(CASES):
        frame = random_frame(rng)
        frame_outcomes = validate(frame)
        for outcomes in frame_outcomes:
            by_code = {outcome.code: outcome for outcome in outcomes}
            assert len(by_code) == len(outcomes), f"seed {SEED} case {case}: duplicate outcome"

            for outcome in outcomes:
                if outcome.outcome in (Outcome.PASSED, Outcome.FAILED, Outcome.ERRORED):
                    check = next(t for t in reg._CHECKS if t.code == outcome.code)
                    for prerequisite in check.depends_on:
                        assert by_code[prerequisite].outcome == Outcome.PASSED, (
                            f"seed {SEED} case {case}: {outcome.code} ran with "
                            f"{prerequisite} not passing"
                        )

            failures = [o for o in outcomes if o.failed]
            if failures:
                shallowest = min(failures, key=lambda outcome: outcome.layer)
                cause = first_cause(outcomes)
                assert cause == shallowest.code, (
                    f"seed {SEED} case {case}: root cause is not the shallowest failure"
                )
                # Ties go to evaluation order, so the answer is deterministic.
                tied = [f.code for f in failures if f.layer == shallowest.layer]
                assert cause == tied[0], f"seed {SEED} case {case}: tie broken arbitrarily"


def test_the_report_survives_whatever_a_check_puts_in_its_comments(
    example_checks: None,
) -> None:
    """Comments carry data, and data is hostile: building the report must not
    raise, and its CSV must read back with every row."""
    rng = random.Random(SEED + 1)
    for case in range(100):
        reg.clear_registry()
        comments = {random_name(rng) or "k": random_scalar(rng) for _ in range(rng.randint(0, 4))}
        make_check("GENERATED", passes=False, comments=comments)
        frame = random_frame(rng)
        report = build_report(validate(frame), df=frame)

        csv = report.to_csv(index=False)
        reparsed = pd.read_csv(pd.io.common.StringIO(csv), dtype=str)
        assert list(reparsed.columns) == list(report.columns)
        assert len(reparsed) == len(report), f"seed {SEED} case {case}: csv lost a row"
