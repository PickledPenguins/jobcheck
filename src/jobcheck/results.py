"""What a check returns, and what the engine records about one check on one row.

Two value types live here:

* :class:`CheckResult` -- what a check function hands back: a status code and any
  comments it wants carried into the report.
* :class:`CheckOutcome` -- what the engine recorded for one check on one row,
  including the checks that never ran and why.

The status vocabulary is deliberately small and fixed: the four
:class:`Status` members below are the only kinds a check can report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd


class Status(IntEnum):
    """Built-in outcome codes. ``PASS`` is 0; every other value is a failure."""

    PASS = 0
    MISSING = 1
    """The field a check needs is absent or empty."""
    MALFORMED = 2
    """Present, but the wrong shape: unparseable, wrong type, bad format."""
    INVALID = 3
    """Right shape, wrong content: out of range, unknown value, inconsistent."""
    ERROR = 9
    """The check itself raised. Recorded by the engine; a check returning it is refused,
    since it would report as a failure while claiming to be a broken check."""


# Outcome of one check on one row, as recorded by the engine.
PASSED = "passed"
FAILED = "failed"
DISABLED = "disabled"
SKIPPED = "skipped"
ERRORED = "errored"


def render_status(code: int) -> str:
    """A status as it appears in a report: ``INVALID (3)``."""

    return f"{Status(code).name} ({int(code)})"


@dataclass(frozen=True)
class CheckResult:
    """What a check function returns: a status code, plus comments for the report.

    ``code`` is 0 (:data:`Status.PASS`) for a pass and any other
    :class:`Status` member for a failure. ``comments`` is free-form detail the report renders as
    ``key=value; key=value`` -- the numbers a person needs to see why the row
    was rejected, without re-running anything.

    It is truthy when the check **passed**, so ``if result:`` reads as "if the
    check was happy". Do not lean on the raw ``code`` for truthiness: 0 is a pass
    but is falsy as an integer, which is the opposite meaning.
    """

    __test__ = False  # not a pytest check class, despite the name

    code: int = Status.PASS
    comments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # pandas hands back numpy scalars, so accept anything pandas calls an
        # integer -- but never a bool, which would make CheckResult(True) a pass.
        if pd.api.types.is_bool(self.code) or not pd.api.types.is_integer(self.code):
            raise TypeError(f"CheckResult code must be an integer status, got {self.code!r}.")
        if int(self.code) not in [int(member) for member in Status]:
            raise ValueError(
                f"Unknown status {self.code!r}. Use one of: "
                + ", ".join(f"Status.{member.name}" for member in Status)
                + "."
            )
        if int(self.code) == Status.ERROR:
            raise ValueError(
                "Status.ERROR is the engine's, not a check's: it marks a check that raised. "
                "Raise the exception, or return a failure kind that describes the data."
            )
        if not isinstance(self.comments, Mapping):
            raise TypeError(f"CheckResult comments must be a mapping, got {self.comments!r}.")
        for key in self.comments:
            if not isinstance(key, str):
                raise TypeError(f"CheckResult comment keys must be strings, got {key!r}.")
        object.__setattr__(self, "code", int(self.code))
        object.__setattr__(self, "comments", MappingProxyType(dict(self.comments)))

    def __bool__(self) -> bool:
        return int(self.code) == Status.PASS

    @property
    def passed(self) -> bool:
        """Whether the check was happy with the row."""

        return bool(self)

    @property
    def failed(self) -> bool:
        """Whether the check rejected the row."""

        return not bool(self)

    @property
    def status(self) -> str:
        """The status name, e.g. ``INVALID``."""

        return Status(self.code).name


PASS = CheckResult()
"""The result of a check that is happy with the row. Shared, and immutable."""


def normalise_result(returned: Any, code: str) -> CheckResult:
    """Turn whatever a check returned into a :class:`CheckResult`.

    Accepts a ``CheckResult``, a bare bool (``True`` passes, ``False`` fails as
    :data:`Status.INVALID`), or a bare status value (``return Status.MISSING``).
    numpy's bool and integer scalars count, since a comparison against a pandas
    value hands back ``np.bool_`` rather than ``bool``.
    Anything else raises ``TypeError`` naming the check: a check returning ``None``
    by falling off the end, or returning a string, is an authoring bug and must
    not be quietly read as a pass.
    """

    if isinstance(returned, CheckResult):
        return returned
    if pd.api.types.is_bool(returned):
        return PASS if returned else CheckResult(Status.INVALID)
    if pd.api.types.is_integer(returned):
        return CheckResult(int(returned))
    raise TypeError(
        f"Check {code!r} returned {returned!r}. A check must return PASS, a CheckResult, "
        "a bool, or a Status value."
    )


@dataclass
class CheckOutcome:
    """What one check did on one row, including the checks that never ran.

    ``outcome`` is one of ``passed``, ``failed``, ``disabled``, ``skipped``,
    ``errored``. ``detail`` says why for the three that did not evaluate the
    row: which rule disabled it, which prerequisites blocked it, or what the
    check raised.
    """

    __test__ = False  # not a pytest check class, despite the name

    code: str
    outcome: str
    status: int = Status.PASS
    layer: int = 0
    message: str = ""
    detail: str = ""
    comments: Mapping[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        """Whether this outcome is a reportable failure, error included."""

        return self.outcome in (FAILED, ERRORED)

    @property
    def status_label(self) -> str:
        """The status as a report renders it: ``INVALID (3)``."""

        return render_status(self.status)
