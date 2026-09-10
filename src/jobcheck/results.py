"""What a check returns, and what the engine records about one check on one row.

Two value types live here:

* :class:`CheckResult` -- what a check function hands back: a status code and any
  comments it wants carried into the report.
* :class:`CheckOutcome` -- what the engine recorded for one check on one row,
  including the checks that never ran and why.

The status vocabulary is deliberately small. Values 0-9 are reserved for the
built-in :class:`Status` members; a project adds its own kinds from 10 upwards
with :func:`register_status`.
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


RESERVED_STATUS_MAX = 9
_EXTRA_STATUSES: dict[int, str] = {}

# Outcome of one check on one row, as recorded by the engine.
PASSED = "passed"
FAILED = "failed"
DISABLED = "disabled"
SKIPPED = "skipped"
ERRORED = "errored"


def register_status(name: str, value: int) -> int:
    """Add a project-specific failure kind, and return its value.

    Values are permanent identifiers like check codes: reports, saved output and
    downstream tooling refer to them, so a reused value silently changes the
    meaning of data already written. Registration fails loudly on anything
    ambiguous -- a value below 10, a duplicate value, or a duplicate name --
    rather than letting two kinds share an identifier.
    """

    if not isinstance(name, str) or not name.isidentifier() or not name.isupper():
        raise ValueError(f"Status name {name!r} must be an UPPER_CASE identifier.")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Status value for {name!r} must be an integer, got {value!r}.")
    if value <= RESERVED_STATUS_MAX:
        raise ValueError(
            f"Status value {value} for {name!r} is reserved: 0-{RESERVED_STATUS_MAX} belong to "
            "the built-in Status members. Project codes start at 10."
        )
    known = all_statuses()
    if value in known:
        raise ValueError(f"Status value {value} is already registered as {known[value]!r}.")
    if name in known.values():
        raise ValueError(f"Status name {name!r} is already registered.")
    _EXTRA_STATUSES[value] = name
    return value


def clear_extra_statuses() -> None:
    """Forget every project-registered status. For checks of the framework itself."""

    _EXTRA_STATUSES.clear()


def all_statuses() -> dict[int, str]:
    """Every known status value mapped to its name, built-in and registered."""

    return {**{int(member): member.name for member in Status}, **_EXTRA_STATUSES}


def status_name(code: int) -> str:
    """The name of a status value, or ``UNKNOWN`` for one never registered."""

    return all_statuses().get(int(code), "UNKNOWN")


def render_status(code: int) -> str:
    """A status as it appears in a report: ``INVALID (3)``."""

    return f"{status_name(code)} ({int(code)})"


@dataclass(frozen=True)
class CheckResult:
    """What a check function returns: a status code, plus comments for the report.

    ``code`` is 0 (:data:`Status.PASS`) for a pass and any registered non-zero
    value for a failure. ``comments`` is free-form detail the report renders as
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
        if int(self.code) not in all_statuses():
            raise ValueError(
                f"Unknown status {self.code!r}. Use a Status member, or register the value "
                "with register_status() before returning it."
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

        return status_name(self.code)


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
    suite: str = ""
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
