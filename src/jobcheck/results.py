"""What a check returns (`Verdict`), and what the engine records about one
check on one row (`CheckOutcome`), plus the fixed status vocabulary both use.

A recorded outcome answers three separate questions, and they are easy to read as
one. `outcome` says what happened to the *check*, as an `Outcome`: it ran and was
happy (`PASSED`), ran and was not (`FAILED`), raised (`ERRORED`), was switched off
by a rule (`DISABLED`), or never ran because a prerequisite did not pass (`SKIPPED`).
`status` says what is wrong with the *value*, from the `Status` vocabulary --
missing, malformed, invalid -- and is `Status.PASS` for everything that did not
fail, which is why a report shows `passed | PASS (0)` in one row and why the
column is only informative beside a failure. `layer` says how deep the check sits
in the dependency graph, and only orders things: a root cause is a failure at the
shallowest failing layer.

Three names for "fine", one per question: a check returns `OK`, the engine
records `Outcome.PASSED`, and the status is `Status.PASS`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Mapping

import pandas as pd


class Status(IntEnum):
    """What is wrong with a value: the fixed status vocabulary. ``PASS`` is 0;
    every other value is a failure."""

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


class Outcome(str, Enum):
    """What happened to one check on one row, as recorded by the engine.

    A `str` as well, so `outcome == "failed"` holds; write `.value` where the text
    is wanted. Formatting a member depends on the Python version, because
    `Enum.__format__` changed: `f"{outcome}"` gives `failed` on 3.10 and
    `Outcome.FAILED` on later versions (seen on 3.12 and 3.14). `StrEnum` would
    settle it, but needs 3.11.
    """

    PASSED = "passed"
    FAILED = "failed"
    DISABLED = "disabled"
    SKIPPED = "skipped"
    ERRORED = "errored"
    SHARED = "shared"


def _render_status(status: int) -> str:
    """A status as it appears in a report: ``INVALID (3)``."""

    return f"{Status(status).name} ({int(status)})"


@dataclass(frozen=True)
class Verdict:
    """What a check function returns: a status, plus comments for the report.

    Truthy when the check **passed**, so `if result:` reads as "if the check was
    happy" -- unlike the raw status, where 0 is a pass and falsy.

    The comments are kept as given, not copied: never mutate them afterwards.
    `OK`'s one dict is shared by every passing outcome.
    """

    status: int = Status.PASS
    comments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # A bool is resolved here, before anything reads it as an integer:
        # True == 1 == Status.MISSING and False == 0 == Status.PASS, so reading
        # Verdict(row["age"] > 0) as an integer would invert its meaning.
        # pandas hands back np.bool_ from a comparison, which counts as a bool.
        if pd.api.types.is_bool(self.status):
            object.__setattr__(self, "status", Status.PASS if self.status else Status.INVALID)
        try:
            status = Status(self.status)
        except ValueError:
            raise ValueError(
                f"Unknown status {self.status!r}. Use one of: "
                + ", ".join(f"Status.{member.name}" for member in Status)
                + "."
            ) from None
        if status is Status.ERROR:
            raise ValueError(
                "Status.ERROR is the engine's, not a check's: it marks a check that raised. "
                "Raise the exception, or return a failure kind that describes the data."
            )
        if not isinstance(self.comments, Mapping):
            raise TypeError(f"Verdict comments must be a mapping, got {self.comments!r}.")
        object.__setattr__(self, "status", int(status))

    def __bool__(self) -> bool:
        return int(self.status) == Status.PASS

    @property
    def failed(self) -> bool:
        """Whether the check rejected the row."""

        return not bool(self)


OK = Verdict()
"""The result of a check that is happy with the row, shared by every check."""


def _normalize_verdict(returned: Any, check_code: str) -> Verdict:
    """Confirm a check returned a result, and hand it back.

    A check falling off the end, or handing back a bare bool or status, is an
    authoring bug: it must not be quietly read as a pass.
    """

    if isinstance(returned, Verdict):
        return returned
    raise TypeError(
        f"Check {check_code!r} returned {returned!r}. A check must return OK or a "
        "Verdict; Verdict(condition) wraps a bare comparison."
    )


@dataclass
class CheckOutcome:
    """What one check did on one row -- including the ones that never ran, where
    `detail` says why: the rule that disabled it, the prerequisites that blocked
    it, or what it raised. `rule` names the rule that switched the check on or
    off for this row, whatever the outcome, and is "" where the default stood."""

    code: str
    outcome: Outcome
    status: int = Status.PASS
    layer: int = 0
    message: str = ""
    detail: str = ""
    comments: Mapping[str, Any] = field(default_factory=dict)
    rule: str = ""

    def __post_init__(self) -> None:
        # A plain string is accepted and checked, so a misspelled outcome fails here.
        self.outcome = Outcome(self.outcome)

    @property
    def failed(self) -> bool:
        """Whether this outcome is a reportable failure, error included."""

        return self.outcome in (Outcome.FAILED, Outcome.ERRORED)

    @property
    def status_label(self) -> str:
        """The status as a report renders it: `INVALID (3)`."""

        return _render_status(self.status)
