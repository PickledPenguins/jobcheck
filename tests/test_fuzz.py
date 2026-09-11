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

from conftest import make_check
from jobcheck import (
    build_report,
    validate,
    load_overrides,
    registry as reg,
    render_report,
    root_cause,
)
from jobcheck.results import ERRORED, FAILED, PASSED

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


def random_rule(rng: random.Random) -> Any:
    """A rule-shaped mapping, valid about as often as not."""

    rule: dict[str, Any] = {}
    for key in ("name", "action", "codes", "match", "description"):
        if rng.random() < 0.15:
            continue
        if key == "name":
            rule[key] = random_name(rng) or "r"
        elif key == "action":
            rule[key] = rng.choice(["enable", "disable", "Enable", "toggle", 7, None])
        elif key == "codes":
            rule[key] = rng.choice([["A_CODE"], ["A_CODE", "B_CODE"], ["NOPE"], [], "A_CODE", [7]])
        elif key == "match":
            rule[key] = rng.choice([
                "all", "al", [], [{"column": "age", "pattern": "^1$"}],
                [{"column": "age"}], [{"column": 7, "pattern": "x"}],
                [{"column": "age", "pattern": "([unclosed"}], 7, None,
            ])
        else:
            rule[key] = rng.choice([random_name(rng), 7, None])
    if rng.random() < 0.1:
        rule[random_name(rng) or "extra"] = 1
    return rule


def test_the_rule_parser_either_loads_or_raises_valueerror(
    fresh_registry: None, tmp_path: Path
) -> None:
    rng = random.Random(SEED)
    make_check("A_CODE")
    make_check("B_CODE")
    accepted = rejected = 0

    for case in range(CASES):
        path = tmp_path / f"rules_{case}.yaml"
        rules = [random_rule(rng) for _ in range(rng.randint(0, 3))]
        path.write_text(yaml.safe_dump(rules, allow_unicode=True), encoding="utf-8")
        try:
            loaded = load_overrides(str(path))
        except ValueError as exc:
            rejected += 1
            assert str(path) in str(exc), f"seed {SEED} case {case}: error omits the file"
            continue
        accepted += 1
        for rule in loaded:
            assert rule.action in ("enable", "disable")
            assert rule.codes
            assert rule.match_all or rule.criteria

    assert accepted and rejected, f"seed {SEED}: the generator stopped covering both outcomes"


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
        outcomes_per_row = validate(frame)
        for outcomes in outcomes_per_row:
            by_code = {outcome.code: outcome for outcome in outcomes}
            assert len(by_code) == len(outcomes), f"seed {SEED} case {case}: duplicate outcome"

            for outcome in outcomes:
                if outcome.outcome in (PASSED, FAILED, ERRORED):
                    check = next(t for t in reg.CHECKS if t.code == outcome.code)
                    for prerequisite in check.depends_on:
                        assert by_code[prerequisite].outcome == PASSED, (
                            f"seed {SEED} case {case}: {outcome.code} ran with "
                            f"{prerequisite} not passing"
                        )

            failures = [o for o in outcomes if o.failed]
            if failures:
                shallowest = min(failures, key=lambda outcome: outcome.layer)
                cause = root_cause(outcomes)
                assert cause == shallowest.code, (
                    f"seed {SEED} case {case}: root cause is not the shallowest failure"
                )
                # Ties go to evaluation order, so the answer is deterministic.
                tied = [f.code for f in failures if f.layer == shallowest.layer]
                assert cause == tied[0], f"seed {SEED} case {case}: tie broken arbitrarily"


def test_rendering_survives_whatever_a_test_puts_in_its_comments(
    example_checks: None,
) -> None:
    """Comments carry data, and data is hostile: the renderer must not raise, and
    the table must stay rectangular."""

    rng = random.Random(SEED + 1)
    for case in range(100):
        reg.clear_registry()
        comments = {random_name(rng) or "k": random_scalar(rng) for _ in range(rng.randint(0, 4))}
        make_check("GENERATED", passes=False, comments=comments)
        frame = random_frame(rng)
        report = build_report(validate(frame), df=frame)

        text = render_report(report)
        widths = {len(line) for line in text.splitlines()}
        assert len(widths) == 1, f"seed {SEED} case {case}: table is ragged"

        csv = render_report(report, fmt="csv")
        reparsed = pd.read_csv(pd.io.common.StringIO(csv), dtype=str)
        assert list(reparsed.columns) == list(report.columns)
        assert len(reparsed) == len(report), f"seed {SEED} case {case}: csv lost a row"
