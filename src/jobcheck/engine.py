"""What happens to one row: which checks run, in what order, and why.

The registry says what checks *exist*; this module says what they *did*. It owns
one algorithm -- resolve the per-row on/off state from the override rules, walk
the checks in dependency order, and record an outcome for every one of them --
and everything else here is a view over its result.

:func:`explain_row` is that algorithm. :func:`validate_row` filters it to the
failures, :func:`root_causes` picks the ones that are not downstream of anything
else, and :mod:`jobcheck.report` turns whole frames of it into tables. There is
no second implementation: a view that disagreed with the engine would be worse
than no view at all.
"""

from __future__ import annotations

from typing import Any

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
    normalise_result,
)
from .rules import OverrideRule, rule_matches


def resolve_enabled_state(row: "pd.Series[Any]", overrides: list[OverrideRule]) -> dict[str, bool]:
    """Effective on/off state of every registered code, for one row.

    Starts from each check's ``default_enabled`` and applies every matching rule
    in list order, so the last matching rule wins.  That precedence is
    positional only -- there is no priority field -- which is why the order
    files are loaded in is documented at each loader.
    """

    return {code: enabled for code, (enabled, _) in _resolve_state(row, overrides).items()}


def _resolve_state(
    row: "pd.Series[Any]", overrides: list[OverrideRule]
) -> dict[str, tuple[bool, str]]:
    """Per-row on/off state plus the reason for it, for explanations."""

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
    ctx: RowContext | None = None,
    overrides: list[OverrideRule] | None = None,
    on_error: str = "record",
) -> list[CheckOutcome]:
    """Run the checks against one row and report what *every* check did.

    This is the root-cause tool, and the single implementation of the per-row
    algorithm -- :func:`validate_row` is a filter over it. Outcomes come back in
    evaluation order, so the first failure is the most fundamental one: a check
    can only fail after all its prerequisites passed.

    Outcomes are ``passed``; ``failed``; ``errored`` (the check raised);
    ``disabled`` (off for this row, with the rule that decided it in ``detail``);
    ``skipped`` (a prerequisite did not pass, with every blocking code in
    ``detail``). Prerequisites are all-or-nothing: a check runs only when every
    code in its ``depends_on`` passed on this row.

    "Did not pass" deliberately covers a prerequisite that was *disabled* or
    *errored* as well as one that failed. A check that never ran confirmed
    nothing about the row, so it must not silently unlock a dependent.

    ``on_error="record"`` turns an exception raised inside a check into a
    :data:`Status.ERROR` outcome and carries on with the row; ``"raise"`` lets it
    propagate, for a run that should stop at the first broken check. A check
    returning something that is not a result at all always raises, whatever this
    is set to: that is an authoring bug, not a data problem.

    Raises ``ValueError`` when the row has duplicate column labels, before
    running anything: ``row[column]`` would then hand a check a Series instead of
    a value.
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

    state = _resolve_state(row, overrides or [])
    passed: dict[str, bool] = {}
    disabled: set[str] = set()
    outcomes: list[CheckOutcome] = []

    for check in _get_topo_order():
        enabled, reason = state.get(check.code, (check.default_enabled, "default"))
        if not enabled:
            passed[check.code] = False
            disabled.add(check.code)
            outcomes.append(
                CheckOutcome(check.code, DISABLED, layer=check.layer, suite=check.suite,
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
                CheckOutcome(check.code, SKIPPED, layer=check.layer, suite=check.suite,
                            detail=reason + ", ".join(blocking))
            )
            continue

        try:
            returned = check.fn(row, ctx)
        except Exception as exc:
            if on_error == "raise":
                raise
            passed[check.code] = False
            outcomes.append(
                CheckOutcome(
                    check.code, ERRORED, status=Status.ERROR, layer=check.layer,
                    suite=check.suite, message=check.message,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        result = normalise_result(returned, check.code)
        passed[check.code] = result.passed
        outcomes.append(
            CheckOutcome(
                check.code,
                PASSED if result.passed else FAILED,
                status=result.code,
                layer=check.layer,
                suite=check.suite,
                message="" if result.passed else check.message,
                comments=result.comments,
            )
        )
    return outcomes


def validate_row(
    row: "pd.Series[Any]",
    ctx: RowContext | None = None,
    overrides: list[OverrideRule] | None = None,
    on_error: str = "record",
) -> list[CheckOutcome]:
    """Run every enabled check against one row and return the failures.

    The failures come back in evaluation order, so the first is the most
    fundamental: ``results[0]`` is the row's root cause. Checks that were disabled
    or blocked by a failed prerequisite are absent entirely -- neither a pass nor
    a failure -- which is what keeps one broken field from producing a page of
    cascading errors. Use :func:`explain_row` to see them.

    Does not mutate ``row`` or ``ctx``.
    """

    return [
        outcome
        for outcome in explain_row(row, ctx=ctx, overrides=overrides, on_error=on_error)
        if outcome.failed
    ]


def root_cause(outcomes: list[CheckOutcome]) -> str | None:
    """The code of the most fundamental failure in a row's results.

    The shallowest failure -- the one at the lowest layer -- with evaluation
    order breaking a tie. ``None`` for a row that passed. Accepts either
    :func:`validate_row` or :func:`explain_row` output.

    When a row fails in two chains at the same depth, both are root causes and
    :func:`root_causes` returns both. This returns one of them, for the caller
    that wants a single label per row -- a summary tally, a column in a frame.
    """

    causes = root_causes(outcomes)
    return causes[0] if causes else None


def root_causes(outcomes: list[CheckOutcome]) -> list[str]:
    """Every failure at the shallowest failing layer, in evaluation order.

    A row that fails a missing email and a malformed age has failed two things,
    neither upstream of the other, and naming only the first one evaluated makes
    registration order decide what a person reads as the cause. Both are
    reported.

    Deeper failures are excluded, not because they are unimportant but because
    they are downstream: a check only runs once its prerequisites passed, so a
    failure at layer 2 sits under whatever failed at layer 0 in the same chain.
    Where nothing failed at all, this is empty.
    """

    failures = [outcome for outcome in outcomes if outcome.failed]
    if not failures:
        return []
    shallowest = min(outcome.layer for outcome in failures)
    return [outcome.code for outcome in failures if outcome.layer == shallowest]


# --------------------------------------------------------------------------
# Table rendering
