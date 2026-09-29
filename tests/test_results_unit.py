"""Unit checks: the status vocabulary and the value a check returns."""

from __future__ import annotations

import pytest

from jobcheck import results as res
from jobcheck.results import OK, Status, Verdict

pytestmark = pytest.mark.fast


def test_pass_is_zero_and_every_other_builtin_is_not() -> None:
    assert Status.PASS == 0
    assert [int(m) for m in Status if m is not Status.PASS] == [1, 2, 3, 9]


def test_a_passing_result_is_truthy() -> None:
    result = Verdict()
    assert bool(result) is True
    assert result.failed is False


def test_a_failing_result_is_falsy() -> None:
    result = Verdict(Status.MISSING)
    assert bool(result) is False
    assert result.failed is True
    assert result.status == Status.MISSING


def test_the_shared_pass_singleton_passes_and_carries_no_comments() -> None:
    assert bool(OK) is True
    assert dict(OK.comments) == {}


def test_a_check_cannot_return_status_error() -> None:
    """Regression: it recorded as a failure carrying ERROR (9), which broke the
    summary's split between broken checks and bad data."""

    with pytest.raises(ValueError, match="Status.ERROR is the engine's, not a check's"):
        Verdict(Status.ERROR)
    with pytest.raises(TypeError, match="Check 'CODE' returned"):
        res._normalize_verdict(Status.ERROR, "CODE")


def test_the_engine_can_still_record_an_error_outcome() -> None:
    """The status stays usable where it belongs -- on an outcome, not a result."""

    outcome = res.CheckOutcome("CODE", res.Outcome.ERRORED, status=Status.ERROR)
    assert outcome.status_label == "ERROR (9)"
    assert outcome.failed is True


def test_a_non_integer_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown status 'MISSING'"):
        Verdict("MISSING")  # type: ignore[arg-type]


def test_non_mapping_comments_are_rejected() -> None:
    with pytest.raises(TypeError, match="comments must be a mapping"):
        Verdict(Status.INVALID, ["actual", 7])  # type: ignore[arg-type]





# --- the fixed status vocabulary --------------------------------------------


def test_every_status_renders_as_name_and_number() -> None:
    assert res._render_status(res.Status.INVALID) == "INVALID (3)"
    assert res._render_status(0) == "PASS (0)"


@pytest.mark.parametrize("value", [4, 77, -1])
def test_a_value_outside_the_vocabulary_is_refused(value: int) -> None:
    with pytest.raises(ValueError, match=f"Unknown status {value}"):
        res.Verdict(value)


# --- normalizing what a check returned --------------------------------------


def test_a_result_passes_through() -> None:
    result = Verdict(Status.MISSING)
    assert res._normalize_verdict(result, "CODE") is result


def test_a_condition_wrapped_in_a_result_passes_or_fails_as_invalid() -> None:
    """Verdict(condition) is how a bare comparison becomes a result."""

    assert bool(Verdict(1 > 0)) is True
    assert Verdict(1 < 0).status == Status.INVALID


def test_a_bool_is_never_read_as_an_integer_status() -> None:
    """True == 1 == MISSING and False == 0 == OK: reading either as an integer
    would invert what the check said."""

    assert Verdict(True).status == Status.PASS
    assert Verdict(False).status == Status.INVALID


def test_numpy_scalars_are_accepted() -> None:
    """A comparison against a pandas value returns np.bool_, not bool."""

    import numpy

    assert bool(Verdict(numpy.bool_(True))) is True  # type: ignore[arg-type]
    assert Verdict(numpy.bool_(False)).status == Status.INVALID  # type: ignore[arg-type]
    assert Verdict(numpy.int64(2)).status == Status.MALFORMED  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "returned", [pytest.param(None, id="none"), pytest.param("ok", id="string"),
                 pytest.param([], id="list"), pytest.param(True, id="bare-bool"),
                 pytest.param(Status.MALFORMED, id="bare-status")],
)
def test_anything_else_raises_naming_the_check(returned: object) -> None:
    """A check falling off the end must not be read as a pass."""

    with pytest.raises(TypeError, match=r"Check 'CODE' returned"):
        res._normalize_verdict(returned, "CODE")

