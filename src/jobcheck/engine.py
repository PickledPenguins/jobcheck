"""What happens to one row: which checks run, in what order, and why.

The registry says what checks *exist*; this module says what they *did*.
`explain_row` is the one algorithm -- everything else here is a view over its
result, because a second implementation could disagree with it.
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from .context import RowContext
from .registry import CHECKS, _get_topo_order
from .results import (
    DISABLED,
    ERRORED,
    FAILED,
    PASSED,
    SKIPPED,
    CheckOutcome,
    Status,
    normalize_result,
)
from .rules import OverrideRule, rule_matches

ContextBuilder = Callable[["pd.Series[Any]"], RowContext | None]


def resolve_enabled_state(
    row: "pd.Series[Any]", overrides: list[OverrideRule]
) -> dict[str, tuple[bool, str]]:
    """Effective on/off state of every registered code, for one row, and why.

    Precedence is positional -- there is no priority field -- so the last
    matching rule wins, which is why the order rule files load in matters.
    """

    state = {
        t.code: (t.default_enabled, "default" if t.default_enabled else "off by default")
        for t in CHECKS
    }
    for rule in overrides:
        if not rule_matches(rule, row):
            continue
        enabled = rule.action == "enable"
        for code in rule.codes:
            if code in state:
                state[code] = (enabled, f"rule {rule.name!r}")
    return state


def explain_row(
    row: "pd.Series[Any]",
    context: RowContext | None = None,
    overrides: list[OverrideRule] | None = None,
    on_error: str = "record",
) -> list[CheckOutcome]:
    """Run the checks against one row and report what *every* check did.

    The root-cause tool, and the single implementation of the per-row algorithm.
    Outcomes come back in evaluation order, so the first failure is the most
    fundamental: a check runs only once every check it depends on has passed.

    "Did not pass" covers a prerequisite that was *disabled* or *errored* as well
    as one that failed -- a check that never ran confirmed nothing about the row,
    so it must not unlock a dependent.
    """

    if on_error not in ("record", "raise"):
        raise ValueError(f"on_error must be 'record' or 'raise', got {on_error!r}.")
    if row.index.has_duplicates:
        duplicated = sorted({str(label) for label in row.index[row.index.duplicated()]})
        raise ValueError(
            f"Row has duplicate column labels {duplicated}: a check reading one of them "
            "would be handed a Series instead of a value. Rename or drop the duplicate "
            "columns before validating."
        )

    state = resolve_enabled_state(row, overrides or [])
    passed: dict[str, bool] = {}
    disabled: set[str] = set()
    outcomes: list[CheckOutcome] = []

    for check in _get_topo_order():
        enabled, reason = state.get(check.code, (check.default_enabled, "default"))
        if not enabled:
            passed[check.code] = False
            disabled.add(check.code)
            outcomes.append(
                CheckOutcome(check.code, DISABLED, layer=check.layer,
                            detail=f"disabled by {reason}")
            )
            continue

        blocking = [code for code in check.depends_on if not passed.get(code, False)]
        if blocking:
            passed[check.code] = False
            # Naming *why* the prerequisite did not pass saves the reader a
            # second lookup: "did not pass" reads as a failure, and a chain
            # switched off at its root looks like a chain that failed.
            reason = ("prerequisite disabled: "
                      if all(code in disabled for code in blocking)
                      else "prerequisite did not pass: ")
            outcomes.append(
                CheckOutcome(check.code, SKIPPED, layer=check.layer,
                            detail=reason + ", ".join(blocking))
            )
            continue

        try:
            returned = check.fn(row, context)
        except Exception as exc:
            if on_error == "raise":
                raise
            passed[check.code] = False
            outcomes.append(
                CheckOutcome(
                    check.code, ERRORED, status=Status.ERROR, layer=check.layer,
                    message=check.message,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        result = normalize_result(returned, check.code)
        passed[check.code] = bool(result)
        outcomes.append(
            CheckOutcome(
                check.code,
                PASSED if result else FAILED,
                status=result.status,
                layer=check.layer,
                message="" if result else check.message,
                comments=result.comments,
            )
        )
    return outcomes


def validate_row(
    row: "pd.Series[Any]",
    context: RowContext | None = None,
    overrides: list[OverrideRule] | None = None,
    on_error: str = "record",
) -> list[CheckOutcome]:
    """Run every enabled check against one row and return only the failures.

    Dropping the checks that did not run is what keeps one broken field from
    producing a page of cascading errors; `explain_row` shows them.
    """

    return [
        outcome
        for outcome in explain_row(row, context=context, overrides=overrides, on_error=on_error)
        if outcome.failed
    ]


def root_causes(row_outcomes: list[CheckOutcome]) -> list[str]:
    """Every failure at the shallowest failing layer, in evaluation order.

    Every one, not the first: two failures at the same depth are two causes.
    Deeper failures are downstream of these, so they are left out.
    """

    failures = [outcome for outcome in row_outcomes if outcome.failed]
    if not failures:
        return []
    shallowest = min(outcome.layer for outcome in failures)
    return [outcome.code for outcome in failures if outcome.layer == shallowest]



def validate(
    df: pd.DataFrame,
    overrides: list[OverrideRule] | None = None,
    context_builder: ContextBuilder | None = None,
    on_error: str = "record",
) -> list[list[CheckOutcome]]:
    """Run every check against every row: one list of outcomes per row, in frame
    order.

    Keeps the checks that did not run too, since the explanation and summary
    views are built from them -- one outcome per check per row. For a frame large
    enough that those objects matter, call `validate_row` per row instead.
    """

    # Built once, not per row: without a builder every row is handed this same
    # empty context, since the base class carries no fields to fill in.
    empty = RowContext()

    frame_outcomes = []
    for _, row in df.iterrows():
        context = empty if context_builder is None else context_builder(row)
        frame_outcomes.append(
            explain_row(row, context=context, overrides=overrides, on_error=on_error))
    return frame_outcomes
