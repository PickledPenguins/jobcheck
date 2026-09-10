"""Unit tests: the status vocabulary and the value a test returns."""

from __future__ import annotations

import pytest

from pandas_row_validation import results as res
from pandas_row_validation.results import PASS, Status, TestResult

pytestmark = pytest.mark.fast


def test_pass_is_zero_and_every_other_builtin_is_not() -> None:
    assert Status.PASS == 0
    assert [int(m) for m in Status if m is not Status.PASS] == [1, 2, 3, 9]


def test_a_passing_result_is_truthy() -> None:
    result = TestResult()
    assert bool(result) is True
    assert result.passed is True
    assert result.failed is False


def test_a_failing_result_is_falsy() -> None:
    result = TestResult(Status.MISSING)
    assert bool(result) is False
    assert result.failed is True
    assert result.status == "MISSING"


def test_the_shared_pass_singleton_passes_and_carries_no_comments() -> None:
    assert bool(PASS) is True
    assert dict(PASS.comments) == {}


def test_comments_are_copied_and_frozen() -> None:
    """A shared PASS must not be poisonable through a caller's dict."""

    original = {"actual": 7}
    result = TestResult(Status.INVALID, original)
    original["actual"] = 8
    assert result.comments["actual"] == 7
    with pytest.raises(TypeError):
        result.comments["actual"] = 9  # type: ignore[index]


def test_an_unregistered_status_is_rejected(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="Unknown status 4"):
        TestResult(4)


def test_a_test_cannot_return_status_error(fresh_registry: None) -> None:
    """Regression: it recorded as a failure carrying ERROR (9), which broke the
    summary's split between broken tests and bad data."""

    with pytest.raises(ValueError, match="Status.ERROR is the engine's, not a test's"):
        TestResult(Status.ERROR)
    with pytest.raises(ValueError, match="Status.ERROR is the engine's"):
        res.normalise_result(Status.ERROR, "CODE")


def test_the_engine_can_still_record_an_error_outcome(fresh_registry: None) -> None:
    """The status stays usable where it belongs -- on an outcome, not a result."""

    outcome = res.TestOutcome("CODE", res.ERRORED, status=Status.ERROR)
    assert outcome.status_label == "ERROR (9)"
    assert outcome.failed is True


def test_a_non_integer_status_is_rejected() -> None:
    with pytest.raises(TypeError, match="code must be an integer status"):
        TestResult("MISSING")  # type: ignore[arg-type]


def test_a_bool_status_is_rejected() -> None:
    """True is an int in Python; accepting it would make TestResult(True) a pass."""

    with pytest.raises(TypeError, match="code must be an integer status"):
        TestResult(True)  # type: ignore[arg-type]


def test_non_mapping_comments_are_rejected() -> None:
    with pytest.raises(TypeError, match="comments must be a mapping"):
        TestResult(Status.INVALID, ["actual", 7])  # type: ignore[arg-type]


def test_non_string_comment_keys_are_rejected() -> None:
    with pytest.raises(TypeError, match="comment keys must be strings"):
        TestResult(Status.INVALID, {7: "actual"})  # type: ignore[dict-item]


# --- registering project statuses ------------------------------------------


def test_a_registered_status_can_be_returned_and_named(fresh_registry: None) -> None:
    value = res.register_status("DUPLICATE", 10)
    assert value == 10
    assert res.status_name(10) == "DUPLICATE"
    assert res.render_status(10) == "DUPLICATE (10)"
    assert TestResult(10).failed is True


def test_reserved_values_are_refused(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="0-9 belong to the built-in Status members"):
        res.register_status("MINE", 5)


def test_a_duplicate_value_is_refused(fresh_registry: None) -> None:
    res.register_status("DUPLICATE", 10)
    with pytest.raises(ValueError, match="already registered as 'DUPLICATE'"):
        res.register_status("OTHER", 10)


def test_a_duplicate_name_is_refused(fresh_registry: None) -> None:
    res.register_status("DUPLICATE", 10)
    with pytest.raises(ValueError, match="name 'DUPLICATE' is already registered"):
        res.register_status("DUPLICATE", 11)


@pytest.mark.parametrize(
    "name", [pytest.param("lower", id="lowercase"), pytest.param("has space", id="not-an-identifier"),
             pytest.param("", id="empty")],
)
def test_bad_status_names_are_refused(fresh_registry: None, name: str) -> None:
    with pytest.raises(ValueError, match="must be an UPPER_CASE identifier"):
        res.register_status(name, 10)


def test_a_non_integer_value_is_refused(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        res.register_status("MINE", "10")  # type: ignore[arg-type]


def test_all_statuses_lists_builtins_and_registered(fresh_registry: None) -> None:
    res.register_status("DUPLICATE", 10)
    assert res.all_statuses() == {
        0: "PASS", 1: "MISSING", 2: "MALFORMED", 3: "INVALID", 9: "ERROR", 10: "DUPLICATE"
    }


def test_an_unknown_value_renders_as_unknown() -> None:
    assert res.status_name(77) == "UNKNOWN"


# --- normalising what a test returned --------------------------------------


def test_a_result_passes_through() -> None:
    result = TestResult(Status.MISSING)
    assert res.normalise_result(result, "CODE") is result


def test_true_becomes_pass_and_false_becomes_invalid() -> None:
    assert res.normalise_result(True, "CODE").passed is True
    assert res.normalise_result(False, "CODE").code == Status.INVALID


def test_a_bare_status_becomes_a_failing_result() -> None:
    assert res.normalise_result(Status.MALFORMED, "CODE").code == Status.MALFORMED


def test_numpy_scalars_are_accepted(fresh_registry: None) -> None:
    """A comparison against a pandas value returns np.bool_, not bool."""

    import numpy

    assert res.normalise_result(numpy.bool_(True), "CODE").passed is True
    assert res.normalise_result(numpy.bool_(False), "CODE").code == Status.INVALID
    assert res.normalise_result(numpy.int64(1), "CODE").code == Status.MISSING
    assert TestResult(numpy.int64(2)).code == Status.MALFORMED  # type: ignore[arg-type]


def test_a_bare_zero_becomes_a_pass() -> None:
    assert res.normalise_result(0, "CODE").passed is True


@pytest.mark.parametrize(
    "returned", [pytest.param(None, id="none"), pytest.param("ok", id="string"),
                 pytest.param([], id="list")],
)
def test_anything_else_raises_naming_the_test(returned: object) -> None:
    """A test falling off the end must not be read as a pass."""

    with pytest.raises(TypeError, match=r"Test 'CODE' returned"):
        res.normalise_result(returned, "CODE")


def test_an_unregistered_status_from_a_test_raises() -> None:
    with pytest.raises(ValueError, match="Unknown status 42"):
        res.normalise_result(42, "CODE")
