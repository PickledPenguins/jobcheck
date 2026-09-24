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
    normalize_verdict,
)
from .rules import Rule, rule_matches

ContextBuilder = Callable[["pd.Series[Any]"], RowContext | None]

# What a check is handed when the caller names no context, or a builder returns
# None. Shared rather than built per row: the base class carries no fields, so
# every empty context is the same object anyway, and a frame does not pay for
# one allocation a row.
_EMPTY_CONTEXT = RowContext()

# Why the two guards below exist, in one place so they cannot drift apart. The
# row loop walks the cached evaluation order and looks every check up in the
# enabled-by-code map built from the registry this call, so the two must hold the
# same checks in a dependency-respecting order. Every route that changes the
# registry drops the cache, so they agree -- unless a caller edits CHECKS or the
# cache itself, which is reachable because CHECKS is exported and mutable.
_STALE_ORDER_CAUSE = (
    "The cached evaluation order and the registry disagree. That happens when CHECKS "
    "or the cached order is edited directly instead of through load_checks(), "
    "register_check() or clear_registry()."
)


def _order_names_an_unregistered_check(code: str, registered: int) -> ValueError:
    """The order holds a check the registry does not.

    Without this the check runs under its declared default and the report says
    `disabled by default` -- a line a reader believes, about a check that is no
    longer registered.
    """

    return ValueError(
        f"The evaluation order names check {code!r}, which is not among the "
        f"{registered} registered check(s). {_STALE_ORDER_CAUSE}"
    )


def _prerequisite_has_not_run(code: str, prerequisite: str) -> ValueError:
    """A check reached before one it depends on.

    Without this the prerequisite counts as not passed and the report says
    `skipped -- prerequisite did not pass`, about a check that was never run.
    """

    return ValueError(
        f"Check {code!r} was reached before its prerequisite {prerequisite!r}, "
        f"which has not run. {_STALE_ORDER_CAUSE}"
    )


def resolve_enabled_state(
    row: "pd.Series[Any]", rules: list[Rule]
) -> dict[str, tuple[bool, str]]:
    """Whether every registered code is on or off for one row, and why.

    Precedence is positional -- there is no priority field -- so the last
    matching rule wins, which is why the order rule files load in matters.
    """

    enabled_by_code = {
        check.code: (check.default_enabled,
                     "default" if check.default_enabled else "off by default")
        for check in CHECKS
    }
    for rule in rules:
        if not rule_matches(rule, row):
            continue
        enabled = rule.action == "enable"
        for code in rule.codes:
            if code in enabled_by_code:
                enabled_by_code[code] = (enabled, f"rule {rule.name!r}")
    return enabled_by_code


def explain_row(
    row: "pd.Series[Any]",
    context: RowContext | None = None,
    rules: list[Rule] | None = None,
    on_error: str = "record",
) -> list[CheckOutcome]:
    """Run the checks against one row and report what *every* check did.

    The root-cause tool, and the single implementation of the per-row algorithm.
    Outcomes come back in evaluation order, so the first failure is the most
    fundamental: a check runs only once every check it depends on has passed.

    "Did not pass" covers a prerequisite that was *disabled* or *errored* as well
    as one that failed -- a check that never ran confirmed nothing about the row,
    so it must not unlock a dependent.

    A `context` of `None` becomes an empty `RowContext`, so a check taking
    `(row, context)` is handed the same type whichever entry point ran it.
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

    if context is None:
        context = _EMPTY_CONTEXT

    enabled_by_code = resolve_enabled_state(row, rules or [])
    passed: dict[str, bool] = {}
    disabled: set[str] = set()
    outcomes: list[CheckOutcome] = []

    for check in _get_topo_order():
        # try/except rather than `in`: a membership test would run once per check
        # per row, and this loop is most of the cost of a frame.
        try:
            enabled, reason = enabled_by_code[check.code]
        except KeyError:
            raise _order_names_an_unregistered_check(
                check.code, len(enabled_by_code)) from None
        if not enabled:
            passed[check.code] = False
            disabled.add(check.code)
            outcomes.append(
                CheckOutcome(check.code, DISABLED, layer=check.layer,
                            detail=f"disabled by {reason}")
            )
            continue

        try:
            blocking = [code for code in check.depends_on if not passed[code]]
        except KeyError as exc:
            raise _prerequisite_has_not_run(check.code, str(exc.args[0])) from None
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

        result = normalize_verdict(returned, check.code)
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
    rules: list[Rule] | None = None,
    on_error: str = "record",
) -> list[CheckOutcome]:
    """Run every enabled check against one row and return only the failures.

    Dropping the checks that did not run is what keeps one broken field from
    producing a page of cascading errors; `explain_row` shows them.
    """

    return [
        outcome
        for outcome in explain_row(row, context=context, rules=rules, on_error=on_error)
        if outcome.failed
    ]


def root_causes(row_outcomes: list[CheckOutcome]) -> list[str]:
    """Every failure at the shallowest failing layer, in evaluation order.

    Every one, not the first: two failures in the same layer are two causes.
    Deeper failures are downstream of these, so they are left out.
    """

    failures = [outcome for outcome in row_outcomes if outcome.failed]
    if not failures:
        return []
    shallowest = min(outcome.layer for outcome in failures)
    return [outcome.code for outcome in failures if outcome.layer == shallowest]



def validate(
    df: pd.DataFrame,
    rules: list[Rule] | None = None,
    context_builder: ContextBuilder | None = None,
    on_error: str = "record",
) -> list[list[CheckOutcome]]:
    """Run every check against every row: one list of outcomes per row, in frame
    order.

    Keeps the checks that did not run too, since the explanation and summary
    views are built from them -- one outcome per check per row. For a frame large
    enough that those objects matter, call `validate_row` per row instead.
    """

    # Checked here, not only in explain_row: an empty frame never reaches it,
    # and a mistyped mode would otherwise pass unnoticed until the first run
    # with rows in it.
    if on_error not in ("record", "raise"):
        raise ValueError(f"on_error must be 'record' or 'raise', got {on_error!r}.")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"validate takes a DataFrame, got {type(df).__name__}; for one row, call "
            "validate_row or explain_row.")

    frame_outcomes = []
    for _, row in df.iterrows():
        context = None if context_builder is None else context_builder(row)
        frame_outcomes.append(
            explain_row(row, context=context, rules=rules, on_error=on_error))
    return frame_outcomes
