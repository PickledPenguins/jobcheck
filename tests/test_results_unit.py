"""Unit checks: the status vocabulary and the value a check returns."""

from __future__ import annotations

import pytest

from jobcheck import results as res
from jobcheck.results import PASS, Status, CheckResult

pytestmark = pytest.mark.fast


def test_pass_is_zero_and_every_other_builtin_is_not() -> None:
    assert Status.PASS == 0
    assert [int(m) for m in Status if m is not Status.PASS] == [1, 2, 3, 9]


def test_a_passing_result_is_truthy() -> None:
    result = CheckResult()
    assert bool(result) is True
    assert bool(result) is True
    assert result.failed is False


def test_a_failing_result_is_falsy() -> None:
    result = CheckResult(Status.MISSING)
    assert bool(result) is False
    assert result.failed is True
    assert result.status == Status.MISSING


def test_the_shared_pass_singleton_passes_and_carries_no_comments() -> None:
    assert bool(PASS) is True
    assert dict(PASS.comments) == {}


def test_comments_are_copied_and_frozen() -> None:
    """A shared PASS must not be poisonable through a caller's dict."""

    original = {"actual": 7}
    result = CheckResult(Status.INVALID, original)
    original["actual"] = 8
    assert result.comments["actual"] == 7
    with pytest.raises(TypeError):
        result.comments["actual"] = 9  # type: ignore[index]


def test_an_unregistered_status_is_rejected(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="Unknown status 4"):
        CheckResult(4)


def test_a_test_cannot_return_status_error(fresh_registry: None) -> None:
    """Regression: it recorded as a failure carrying ERROR (9), which broke the
    summary's split between broken checks and bad data."""

    with pytest.raises(ValueError, match="Status.ERROR is the engine's, not a check's"):
        CheckResult(Status.ERROR)
    with pytest.raises(TypeError, match="Check 'CODE' returned"):
        res.normalize_result(Status.ERROR, "CODE")


def test_the_engine_can_still_record_an_error_outcome(fresh_registry: None) -> None:
    """The status stays usable where it belongs -- on an outcome, not a result."""

    outcome = res.CheckOutcome("CODE", res.ERRORED, status=Status.ERROR)
    assert outcome.status_label == "ERROR (9)"
    assert outcome.failed is True


def test_a_non_integer_status_is_rejected() -> None:
    with pytest.raises(TypeError, match="status must be a Status value or a bool"):
        CheckResult("MISSING")  # type: ignore[arg-type]


def test_non_mapping_comments_are_rejected() -> None:
    with pytest.raises(TypeError, match="comments must be a mapping"):
        CheckResult(Status.INVALID, ["actual", 7])  # type: ignore[arg-type]


def test_non_string_comment_keys_are_rejected() -> None:
    with pytest.raises(TypeError, match="comment keys must be strings"):
        CheckResult(Status.INVALID, {7: "actual"})  # type: ignore[dict-item]


# --- the fixed status vocabulary --------------------------------------------


def test_every_status_renders_as_name_and_number() -> None:
    assert res.render_status(res.Status.INVALID) == "INVALID (3)"
    assert res.render_status(0) == "PASS (0)"


def test_a_value_outside_the_vocabulary_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown status 77"):
        res.CheckResult(77)


# --- normalizing what a check returned --------------------------------------


def test_a_result_passes_through() -> None:
    result = CheckResult(Status.MISSING)
    assert res.normalize_result(result, "CODE") is result


def test_a_condition_wrapped_in_a_result_passes_or_fails_as_invalid() -> None:
    """CheckResult(condition) is how a bare comparison becomes a result."""

    assert bool(CheckResult(1 > 0)) is True
    assert CheckResult(1 < 0).status == Status.INVALID


def test_a_bool_is_never_read_as_an_integer_status() -> None:
    """True == 1 == MISSING and False == 0 == PASS: reading either as an integer
    would invert what the check said."""

    assert CheckResult(True).status == Status.PASS
    assert CheckResult(False).status == Status.INVALID


def test_numpy_scalars_are_accepted(fresh_registry: None) -> None:
    """A comparison against a pandas value returns np.bool_, not bool."""

    import numpy

    assert bool(CheckResult(numpy.bool_(True))) is True  # type: ignore[arg-type]
    assert CheckResult(numpy.bool_(False)).status == Status.INVALID  # type: ignore[arg-type]
    assert CheckResult(numpy.int64(2)).status == Status.MALFORMED  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "returned", [pytest.param(None, id="none"), pytest.param("ok", id="string"),
                 pytest.param([], id="list"), pytest.param(True, id="bare-bool"),
                 pytest.param(Status.MALFORMED, id="bare-status")],
)
def test_anything_else_raises_naming_the_test(returned: object) -> None:
    """A check falling off the end must not be read as a pass."""

    with pytest.raises(TypeError, match=r"Check 'CODE' returned"):
        res.normalize_result(returned, "CODE")


def test_an_unregistered_status_raises() -> None:
    with pytest.raises(ValueError, match="Unknown status 42"):
        CheckResult(42)
