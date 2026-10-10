"""What happens to one row: which checks run, in what order, and why.

The registry says what checks *exist*, this module says what they *did*.
`_explain` is the one algorithm, run once per row by `validate`.
"""

from __future__ import annotations

import inspect
import traceback
from pathlib import Path
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
from .tables import _format_cell, _require_one_column, is_null

# A builder takes `(row)` or `(row, context_args)`, the way a check takes
# `(row)` or `(row, context)`, and returns the row's context.
ContextBuilder = Callable[..., RowContext | None]

# Default empty context for checks that require one. One shared object: the base
# class has no fields, and its empty __slots__ refuses a new attribute, so no
# check adds anything to it.
_EMPTY_CONTEXT = RowContext()


def _resolve_enabled_state(
    row: "pd.Series[Any]", rules: list[Rule]
) -> dict[str, tuple[bool, str]]:
    """Whether each registered code is on or off for the row, and the name of
    the rule that decided it, or "" where the default stands.

    Precedence is positional (there is no priority field) so the last
    matching rule wins, which is why the order rule files load in matters.
    """
    enabled_by_code = {check.code: (check.default_enabled, "") for check in _CHECKS}
    for rule in rules:
        if not _rule_matches(rule, row):
            continue
        enabled = rule.action == "enable"
        for code in rule.codes:
            if code in enabled_by_code:
                enabled_by_code[code] = (enabled, rule.name)
    return enabled_by_code


# What the copies of one row have settled so far. For each check that does not
# repeat, the `shared` detail a later copy records (built by `_settle`) and the outcome.
_Settled = dict[str, tuple[str, CheckOutcome]]


def _explain(
    row: "pd.Series[Any]",
    context: RowContext | None,
    rules: list[Rule] | None,
    on_error: str,
    settled: _Settled,
) -> tuple[list[CheckOutcome], set[str]]:
    """Run the checks against one row and report what *every* check did, plus the
    codes that were off on the row (disabled on it, or below a check that is).

    Outcomes come back in evaluation order. A check runs only once every check it
    depends on has passed. The first failure is not necessarily the shallowest (an
    independent chain registered earlier can fail deeper).

    "Did not pass" includes a prerequisite that was *disabled* or *errored* as well
    as one that failed (a check that never ran confirmed nothing about the row).
    A check that did not pass will block a dependent check from running.

    Under `repeat_key`, a check that does not repeat and that an earlier copy
    settled (it is in *settled*) is not run. That copy's result is recorded as
    `shared` (unless a rule disables the check on this copy, which wins). A row
    with no earlier copy passes an empty *settled*.

    A `context` of `None` becomes an empty `RowContext`.
    """

    if context is None:
        context = _EMPTY_CONTEXT

    enabled_by_code = _resolve_enabled_state(row, rules or [])
    passed: dict[str, bool] = {}
    disabled: set[str] = set()
    # Disabled on this row, or below a check that is: never shared, never settled.
    off_on_row: set[str] = set()
    outcomes: list[CheckOutcome] = []

    for check in _get_topo_order():
        enabled, rule = enabled_by_code[check.code]
        if not enabled or any(code in off_on_row for code in check.depends_on):
            off_on_row.add(check.code)
        elif not check.repeats and check.code in settled:
            detail, original = settled[check.code]
            # A dependent that repeats reads the settled result. The status
            # stays PASS: a copy is not a failure, and detail says where.
            passed[check.code] = original.outcome is Outcome.PASSED
            outcomes.append(
                CheckOutcome(check.code, Outcome.SHARED, layer=check.layer,
                             detail=detail, rule=rule)
            )
            continue
        if not enabled:
            passed[check.code] = False
            disabled.add(check.code)
            outcomes.append(
                CheckOutcome(check.code, Outcome.DISABLED, layer=check.layer,
                             detail=f"disabled by rule {rule!r}" if rule
                             else "disabled by default", rule=rule)
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
                             detail=reason + ", ".join(blocking), rule=rule)
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
                    # Not check.message: that is a verdict on data the check never
                    # finished reading.
                    message="check raised; see detail",
                    detail=_describe_error(exc),
                    rule=rule,
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
                rule=rule,
            )
        )
    return outcomes, off_on_row


def _context_caller(
    builder: ContextBuilder,
) -> Callable[["pd.Series[Any]", Any], RowContext | None]:
    """Settle how a context builder is called, once per `validate` rather than
    per row: `(row)` or `(row, context_args)`, with `*args` counting as the
    second. The same rule as `registry._make_runner` applies to a check, change
    the two together.
    """

    # A functools.partial has no __name__, so it is shown as itself
    name = getattr(builder, "__name__", builder)
    parameters = list(inspect.signature(builder).parameters.values())
    positional = [p for p in parameters
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    needed = [p.name for p in parameters
              if p.kind is p.KEYWORD_ONLY and p.default is p.empty]
    if needed:
        raise ValueError(
            f"context_builder {name!r} needs keyword argument(s) {', '.join(needed)} "
            "that validate cannot supply. Give them defaults, or read them from "
            "context_args.")
    defaulted = _defaulted_second(positional)
    if defaulted is not None:
        raise ValueError(
            f"context_builder {name!r} has a default on its second parameter, "
            f"{defaulted.name!r}, which would be handed context_args. Read the value "
            "from context_args, or make it keyword-only by putting it after a *.")
    if any(p.kind is p.VAR_POSITIONAL for p in parameters) or len(positional) == 2:
        return lambda row, context_args: builder(row, context_args)
    if len(positional) == 1:
        return lambda row, context_args: builder(row)
    raise ValueError(
        f"context_builder {name!r} must take (row) or (row, context_args), "
        f"not {len(positional)} positional argument(s)."
    )


def validate(
    df: pd.DataFrame,
    rules: list[Rule] | None = None,
    context_builder: ContextBuilder | None = None,
    on_error: str = "record",
    context_args: Any = None,
    repeat_key: Any = None,
) -> list[list[CheckOutcome]]:
    """Run every check against every row: one list of outcomes per row, in frame order.

    Keeps every check's outcome on every row, including the ones that did not run.
    The views in `views.py` pick what to show.

    `context_builder` takes `(row)` or `(row, context_args)` and is called once
    per row. `context_args` is whatever every row's context is built from (the
    parsed command line, a configuration) passed through untouched.

    `repeat_key` names the column that marks copies of one row (as `explode`
    makes them). The first row for each value runs every check: a later one runs
    only the checks that repeat and records the others as `shared`. Rules are
    matched on every copy: a copy that disables a check records `disabled`, and
    a check disabled on the first copy runs on the first copy that enables it.
    """

    if on_error not in ("record", "raise"):
        raise ValueError(f"on_error must be 'record' or 'raise', got {on_error!r}.")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"validate takes a DataFrame, got {type(df).__name__}.")

    if repeat_key is not None:
        _require_one_column(df, "repeat_key", repeat_key)
    if df.columns.has_duplicates:
        duplicated = sorted({str(label) for label in df.columns[df.columns.duplicated()]})
        raise ValueError(
            f"Data has duplicate column labels {duplicated}. Rename or drop the duplicate "
            "columns before validating.")
    # Validate the registry before the row loop: a registry mistake (E.g., a prerequisite
    # no check registered) would raise inside the loop then carry a row's note.
    _get_topo_order()
    run_once = {check.code for check in _CHECKS if not check.repeats}

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
                frame_outcomes.append(_explain(row, context, rules, on_error, {})[0])
                continue
            is_first_copy = value not in settled_by_value
            settled = settled_by_value.setdefault(value, {})
            row_outcomes, off_on_row = _explain(row, context, rules, on_error, settled)
        except Exception as exc:
            # Whatever escapes (the builder, on_error="raise", a check returning
            # something that is not a Verdict) keeps its type, and gains the row.
            # add_note is Python 3.11+; on 3.10 the stand-in drops the note.
            add_note = getattr(exc, "add_note", lambda note: None)
            add_note(f"validate: raised on the row at position {position} (index label {label!r}).")
            raise
        _settle(row_outcomes, off_on_row, run_once, settled, is_first_copy, position,
                repeat_key, value)
        frame_outcomes.append(row_outcomes)
    return frame_outcomes


def _describe_error(exc: Exception) -> str:
    """`Type: message (file.py:line)` for an exception a check raised.

    The line is the innermost one in the file the check was called in (through a
    helper in another file, the check's line that called it) so a reader can open
    the check where it broke without re-running with `on_error="raise"`. Frames in
    this package (the engine's call, the runner `register_check` may wrap a
    one-argument check in) are left out. A message that is empty drops its colon.
    """
    text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    package = Path(__file__).parent
    frames = [frame for frame in traceback.extract_tb(exc.__traceback__)
              if Path(frame.filename).parent != package]
    if not frames:
        return text
    own = frames[0].filename
    line = [frame for frame in frames if frame.filename == own][-1].lineno
    return f"{text} ({Path(own).name}:{line})"


def _settle(
    row_outcomes: list[CheckOutcome], off_on_row: set[str], run_once: set[str],
    settled: _Settled, is_first_copy: bool, position: int, repeat_key: Any, value: Any
) -> None:
    """Add to *settled* what this copy settled: each check in *run_once* (those that
    do not repeat) that had no result yet, unless it was off on the row (*off_on_row*,
    from `_explain`). A later copy whose rules enable that chain runs it instead.

    Each settled check carries the `detail` every later copy records for it, built
    here and nowhere else: `failed at position 0, the first row with id J1`, ending
    ` to enable it` when this is not the first copy, so the earlier copies had the
    check off.
    """
    detail_part = f"at position {position}, the first row with {repeat_key} {_format_cell(value)}"
    if not is_first_copy:
        detail_part += " to enable it"
    for outcome in row_outcomes:
        if (outcome.code in run_once and outcome.code not in off_on_row
                and outcome.code not in settled):
            settled[outcome.code] = (f"{outcome.outcome.value} {detail_part}", outcome)


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
