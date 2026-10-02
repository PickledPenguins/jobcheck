"""What happens to one row: which checks run, in what order, and why.

The registry says what checks *exist*; this module says what they *did*.
`_explain` is the one algorithm, run once per row by `validate`; what to show of
its result is `views.py`'s business.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

import pandas as pd

from .context import RowContext
from .registry import _CHECKS, _defaulted_second, _get_topo_order
from .results import (
    CheckOutcome,
    Outcome,
    Status,
    _normalize_verdict,
)
from .rules import Rule, _rule_matches
from .tables import _format_cell, is_null

#: A builder takes `(row)` or `(row, context_args)`, the way a check takes
#: `(row)` or `(row, context)`, and returns the row's context.
ContextBuilder = Callable[..., RowContext | None]

# What a check is handed when there is no context. One shared object: the base
# class has no fields, and its empty __slots__ refuses a new attribute, so no
# check can leave a value on it for a later row to find.
_EMPTY_CONTEXT = RowContext()


def _resolve_enabled_state(
    row: "pd.Series[Any]", rules: list[Rule]
) -> dict[str, tuple[bool, str]]:
    """Whether every registered code is on or off for one row, and why.

    Precedence is positional -- there is no priority field -- so the last
    matching rule wins, which is why the order rule files load in matters.
    """

    enabled_by_code = {
        check.code: (check.default_enabled,
                     "default" if check.default_enabled else "off by default")
        for check in _CHECKS
    }
    for rule in rules:
        if not _rule_matches(rule, row):
            continue
        enabled = rule.action == "enable"
        for code in rule.codes:
            if code in enabled_by_code:
                enabled_by_code[code] = (enabled, f"rule {rule.name!r}")
    return enabled_by_code


# What the copies of one row have settled so far: for each check that does not
# repeat, the outcome to share and where it came from.
_Settled = dict[str, tuple[str, CheckOutcome]]


def _explain(
    row: "pd.Series[Any]",
    context: RowContext | None = None,
    rules: list[Rule] | None = None,
    on_error: str = "record",
) -> list[CheckOutcome]:
    """Run the checks against one row and report what *every* check did.

    The single implementation of the per-row algorithm. Outcomes come back in
    evaluation order: a check runs only once every check it depends on has
    passed. The first failure is not necessarily the shallowest -- an
    independent chain registered earlier can fail deeper.

    "Did not pass" covers a prerequisite that was *disabled* or *errored* as well
    as one that failed -- a check that never ran confirmed nothing about the row,
    so it must not unlock a dependent.

    A `context` of `None` becomes an empty `RowContext`, the type a check taking
    `(row, context)` is always handed.
    """

    outcomes, _ = _explain_with_off_here(row, context, rules, on_error, None)
    return outcomes


def _explain_with_off_here(
    row: "pd.Series[Any]",
    context: RowContext | None,
    rules: list[Rule] | None,
    on_error: str,
    settled: _Settled | None,
) -> tuple[list[CheckOutcome], set[str]]:
    """`_explain` for a row under `repeat_key`, which also returns the codes that
    were off on the row: disabled here, or below a check that is. `_settle` needs
    that set and must not work it out a second time.

    With *settled*, the row is a copy: a check that does not repeat, and that an
    earlier copy settled, is not run, and records that copy's result as `shared`
    -- unless a rule disables it on this copy, which wins.
    """

    if row.index.has_duplicates:
        duplicated = sorted({str(label) for label in row.index[row.index.duplicated()]})
        raise ValueError(
            f"Row has duplicate column labels {duplicated}: a check reading one of them "
            "would be handed a Series instead of a value. Rename or drop the duplicate "
            "columns before validating."
        )

    if context is None:
        context = _EMPTY_CONTEXT

    enabled_by_code = _resolve_enabled_state(row, rules or [])
    passed: dict[str, bool] = {}
    disabled: set[str] = set()
    # Disabled on this row, or below a check that is: never shared, never settled.
    off_here: set[str] = set()
    outcomes: list[CheckOutcome] = []

    for check in _get_topo_order():
        enabled, reason = enabled_by_code[check.code]
        if not enabled or any(code in off_here for code in check.depends_on):
            off_here.add(check.code)
        elif settled is not None and not check.repeats and check.code in settled:
            where, original = settled[check.code]
            # A dependent that repeats reads the settled result. The status
            # stays PASS: a copy is not a failure, and detail says where.
            passed[check.code] = original.outcome is Outcome.PASSED
            outcomes.append(
                CheckOutcome(check.code, Outcome.SHARED, layer=check.layer,
                             detail=f"{original.outcome.value} {where}")
            )
            continue
        if not enabled:
            passed[check.code] = False
            disabled.add(check.code)
            outcomes.append(
                CheckOutcome(check.code, Outcome.DISABLED, layer=check.layer,
                            detail=f"disabled by {reason}")
            )
            continue

        blocking = [code for code in check.depends_on if not passed[code]]
        if blocking:
            passed[check.code] = False
            # Say whether the chain was switched off or failed; they read alike.
            reason = ("prerequisite disabled: "
                      if all(code in disabled for code in blocking)
                      else "prerequisite did not pass: ")
            outcomes.append(
                CheckOutcome(check.code, Outcome.SKIPPED, layer=check.layer,
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
                    check.code, Outcome.ERRORED, status=Status.ERROR, layer=check.layer,
                    message=check.message,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        result = _normalize_verdict(returned, check.code)
        passed[check.code] = bool(result)
        outcomes.append(
            CheckOutcome(
                check.code,
                Outcome.PASSED if result else Outcome.FAILED,
                status=result.status,
                layer=check.layer,
                message="" if result else check.message,
                comments=result.comments,
            )
        )
    return outcomes, off_here


def _context_caller(
    builder: ContextBuilder,
) -> Callable[["pd.Series[Any]", Any], RowContext | None]:
    """Settle how a context builder is called, once per `validate` rather than
    per row: `(row)` or `(row, context_args)`, with `*args` counting as the
    second. The same rule as `registry._make_runner` applies to a check; change
    the two together.
    """

    parameters = list(inspect.signature(builder).parameters.values())
    positional = [p for p in parameters
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    needed = [p.name for p in parameters
              if p.kind is p.KEYWORD_ONLY and p.default is p.empty]
    if needed:
        raise ValueError(
            f"context_builder {getattr(builder, '__name__', builder)!r} needs keyword "
            f"argument(s) {', '.join(needed)} that validate cannot supply. Give them "
            "defaults, or read them from context_args.")
    defaulted = _defaulted_second(positional)
    if defaulted is not None:
        raise ValueError(
            f"context_builder {getattr(builder, '__name__', builder)!r} has a default on "
            f"its second parameter, {defaulted.name!r}, which would be handed "
            "context_args. Read the value from context_args, or make it keyword-only "
            "by putting it after a *.")
    if any(p.kind is p.VAR_POSITIONAL for p in parameters) or len(positional) == 2:
        return lambda row, context_args: builder(row, context_args)
    if len(positional) == 1:
        return lambda row, context_args: builder(row)
    raise ValueError(
        f"context_builder {getattr(builder, '__name__', builder)!r} must take (row) or "
        f"(row, context_args), not {len(positional)} positional argument(s)."
    )


def validate(
    df: pd.DataFrame,
    rules: list[Rule] | None = None,
    context_builder: ContextBuilder | None = None,
    on_error: str = "record",
    context_args: Any = None,
    repeat_key: Any = None,
) -> list[list[CheckOutcome]]:
    """Run every check against every row: one list of outcomes per row, in frame
    order.

    Keeps every check's outcome on every row, the ones that did not run too:
    the views in `views.py` pick what to show from it.

    `context_builder` takes `(row)` or `(row, context_args)` and is called once
    per row. `context_args` is whatever every row's context is built from -- the
    parsed command line, a configuration -- passed through untouched.

    `repeat_key` names the column that marks copies of one row, as `explode`
    makes them. The first row with each value runs every check; a later one runs
    only the checks that repeat, and records the others as `shared`. Rules are
    matched on every copy: a copy that disables a check records `disabled`, and
    a check disabled on the first copy runs on the first copy that enables it.
    """

    if on_error not in ("record", "raise"):
        raise ValueError(f"on_error must be 'record' or 'raise', got {on_error!r}.")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"validate takes a DataFrame, got {type(df).__name__}; for one row, pass "
            "row.to_frame().T.")

    if repeat_key is not None:
        _check_repeat_key(df, repeat_key)

    # Read once per row: a generator would apply to the first row only.
    rules = list(rules or [])
    build = None if context_builder is None else _context_caller(context_builder)
    settled_by_value: dict[Any, _Settled] = {}
    frame_outcomes = []
    for position, (label, row) in enumerate(df.iterrows()):
        value = None if repeat_key is None else _repeat_value(row, repeat_key, position)
        try:
            context = None if build is None else build(row, context_args)
            if repeat_key is None:
                frame_outcomes.append(_explain(row, context, rules, on_error))
                continue
            settled = settled_by_value.get(value)
            row_outcomes, off_here = _explain_with_off_here(row, context, rules, on_error,
                                                            settled)
        except Exception as exc:
            # Whatever escapes -- the builder, on_error="raise", a check returning
            # something that is not a Verdict -- keeps its type, and gains the row.
            # add_note is Python 3.11+; on 3.10 the stand-in drops the note.
            add_note = getattr(exc, "add_note", lambda note: None)
            add_note(f"validate: raised on the row at position {position} "
                     f"(index label {label!r}).")
            raise
        where = f"at position {position}, the first row with {repeat_key} {_format_cell(value)}"
        if settled is not None:
            where += " to enable it"
        settled_by_value[value] = _settle(row_outcomes, off_here, settled or {}, where)
        frame_outcomes.append(row_outcomes)
    return frame_outcomes


def _settle(
    row_outcomes: list[CheckOutcome], off_here: set[str], settled: _Settled, where: str
) -> _Settled:
    """Add to *settled* what this copy settled: each check that does not repeat
    and had no result yet, unless it was off here (*off_here*, from
    `_explain_with_off_here`). A later copy whose rules enable that chain runs
    it instead.
    """

    repeats = {check.code: check.repeats for check in _CHECKS}
    for outcome in row_outcomes:
        if (outcome.code not in off_here and not repeats[outcome.code]
                and outcome.code not in settled):
            settled[outcome.code] = (where, outcome)
    return settled


def _check_repeat_key(df: pd.DataFrame, repeat_key: Any) -> None:
    """Refuse a `repeat_key` that is not exactly one column of *df*."""

    if repeat_key not in df.columns:
        raise ValueError(
            f"repeat_key {repeat_key!r} is not in the data. Available columns: "
            f"{', '.join(str(c) for c in df.columns)}.")
    repeated = list(df.columns).count(repeat_key)
    if repeated > 1:
        raise ValueError(
            f"repeat_key {repeat_key!r} appears {repeated} times in the data. "
            "Rename or drop the duplicate columns.")


def _repeat_value(row: "pd.Series[Any]", repeat_key: Any, position: int) -> Any:
    """The row's `repeat_key` value, refused when it cannot say whose copy the row is."""

    value = row[repeat_key]
    if is_null(value):
        raise ValueError(
            f"repeat_key {repeat_key!r} is blank at position {position}: every row "
            "needs a value to say which rows are its copies.")
    try:
        hash(value)
    except TypeError:
        raise TypeError(
            f"repeat_key {repeat_key!r} holds {value!r} at position {position}, which "
            "cannot be compared as a key: use a column of text or numbers.") from None
    return value
