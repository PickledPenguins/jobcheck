"""Unit checks: check_group defaults and how they combine with a check's own."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from jobcheck import registry as reg
from jobcheck import engine
from jobcheck.results import PASS, CheckResult

pytestmark = pytest.mark.fast

ROW = pd.Series({"age": 30})


def register(group: reg.CheckGroup, code: str, **kwargs: Any) -> None:
    @group(code, f"{code} failed", **kwargs)
    def _test(row: "pd.Series[Any]") -> CheckResult:
        return PASS


def by_code(code: str) -> reg.Check:
    return next(t for t in reg.CHECKS if t.code == code)


def test_a_group_supplies_its_prerequisites(fresh_registry: None) -> None:
    group = reg.check_group(depends_on=["ROOT"])
    register(reg.check_group(), "ROOT")
    register(group, "MEMBER")
    assert by_code("MEMBER").depends_on == ["ROOT"]


def test_a_test_adds_its_own_prerequisites_to_the_group_s(fresh_registry: None) -> None:
    """Union, not replacement: 'this file waits for X' cannot be undone per check."""

    register(reg.check_group(), "ROOT")
    register(reg.check_group(), "OTHER")
    register(reg.check_group(depends_on=["ROOT"]), "MEMBER", depends_on=["OTHER"])
    assert by_code("MEMBER").depends_on == ["ROOT", "OTHER"]


def test_a_prerequisite_named_twice_is_kept_once(fresh_registry: None) -> None:
    register(reg.check_group(), "ROOT")
    register(reg.check_group(depends_on=["ROOT"]), "MEMBER", depends_on=["ROOT"])
    assert by_code("MEMBER").depends_on == ["ROOT"]


def test_a_group_prerequisite_repeated_in_its_own_list_is_kept_once(fresh_registry: None) -> None:
    register(reg.check_group(), "ROOT")
    register(reg.check_group(depends_on=["ROOT", "ROOT"]), "MEMBER")
    assert by_code("MEMBER").depends_on == ["ROOT"]


def test_a_group_member_cannot_be_its_own_prerequisite(fresh_registry: None) -> None:
    """The group's prerequisites are unconditional, so a presence check belongs in a
    group without them -- putting it inside is a cycle, caught at load."""

    group = reg.check_group(depends_on=["ROOT"])
    register(group, "ROOT")
    with pytest.raises(ValueError, match="Dependency cycle among checks: ROOT -> ROOT"):
        reg.validate_registry()


def test_a_group_sets_the_default_state(fresh_registry: None) -> None:
    register(reg.check_group(default_enabled=False), "OFF")
    assert by_code("OFF").default_enabled is False


def test_a_test_can_override_the_group_default_state(fresh_registry: None) -> None:
    group = reg.check_group(default_enabled=False)
    register(group, "OFF")
    register(group, "ON", default_enabled=True)
    assert (by_code("OFF").default_enabled, by_code("ON").default_enabled) == (False, True)


def test_a_group_can_name_the_suite(fresh_registry: None) -> None:
    register(reg.check_group(suite="declared"), "CODE")
    assert by_code("CODE").suite == "declared"


def test_a_test_can_override_the_group_suite(fresh_registry: None) -> None:
    group = reg.check_group(suite="declared")
    register(group, "GROUPED")
    register(group, "OWN", suite="its_own")
    assert (by_code("GROUPED").suite, by_code("OWN").suite) == ("declared", "its_own")


def test_without_a_declared_suite_the_module_decides(fresh_registry: None) -> None:
    register(reg.check_group(), "CODE")
    assert by_code("CODE").suite == reg.BASE_SUITE


def test_a_group_carries_description_and_message_through(fresh_registry: None) -> None:
    register(reg.check_group(), "CODE", description="why it exists")
    assert (by_code("CODE").message, by_code("CODE").description) == ("CODE failed", "why it exists")


def test_group_members_run_like_any_other_test(fresh_registry: None) -> None:
    group = reg.check_group()

    @group("FAILS", "it failed")
    def _test(row: "pd.Series[Any]") -> bool:
        return False

    assert [o.code for o in engine.validate_row(ROW)] == ["FAILS"]


def test_two_groups_in_one_file_stay_separate(fresh_registry: None) -> None:
    register(reg.check_group(), "ROOT")
    register(reg.check_group(depends_on=["ROOT"]), "WAITS")
    register(reg.check_group(), "FREE")
    assert by_code("WAITS").depends_on == ["ROOT"]
    assert by_code("FREE").depends_on == []


# --- registration guards ----------------------------------------------------


@pytest.mark.parametrize(
    "code, message, expected",
    [
        pytest.param("", "m", "Check code must be a non-empty string", id="empty-code"),
        pytest.param(None, "m", "Check code must be a non-empty string", id="code-not-a-string"),
        pytest.param("CODE", "", "message must be the text a person sees", id="empty-message"),
        pytest.param("CODE", None, "message must be the text a person sees", id="message-not-a-string"),
    ],
)
def test_a_bad_declaration_is_rejected_at_registration(
    fresh_registry: None, code: Any, message: Any, expected: str
) -> None:
    def check(row: "pd.Series[Any]") -> CheckResult:
        return PASS

    with pytest.raises(ValueError, match=expected):
        reg.register_check(code=code, message=message)(check)
    assert reg.CHECKS == []


def test_a_non_string_prerequisite_is_rejected(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="depends_on must be a list of check codes"):
        register(reg.check_group(), "CODE", depends_on=[7])


def test_a_string_prerequisite_is_rejected_not_split_into_characters(
    fresh_registry: None,
) -> None:
    """Regression: a bare string passed the element check, registering one
    prerequisite per character, and the error then named a letter."""

    with pytest.raises(ValueError, match="A bare string is a list of its characters"):
        register(reg.check_group(), "CODE", depends_on="AGE_PRESENT")
    assert reg.CHECKS == []


def test_a_group_rejects_a_string_of_prerequisites(fresh_registry: None) -> None:
    with pytest.raises(ValueError, match="A bare string is a list of its characters"):
        reg.check_group(depends_on="AGE_PRESENT")  # type: ignore[arg-type]


def test_a_test_needing_a_keyword_argument_is_rejected_at_registration(
    fresh_registry: None,
) -> None:
    """Regression: it registered cleanly and then errored on every single row."""

    def check(row: "pd.Series[Any]", *, strict: bool) -> CheckResult:
        return PASS

    with pytest.raises(ValueError, match="needs keyword argument\\(s\\) strict"):
        reg.register_check(code="CODE", message="m")(check)


def test_a_keyword_argument_with_a_default_is_fine(fresh_registry: None) -> None:
    @reg.register_check(code="CODE", message="m")
    def check(row: "pd.Series[Any]", *, strict: bool = True) -> CheckResult:
        return PASS

    assert engine.validate_row(ROW) == []


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        pytest.param({"default_enabled": "yes"}, "default_enabled must be True or False",
                     id="default_enabled"),
        pytest.param({"description": 7}, "description must be text", id="description"),
        pytest.param({"suite": 7}, "suite must be the name of a suite", id="suite-not-a-name"),
        pytest.param({"suite": ""}, "suite must be the name of a suite", id="suite-empty"),
    ],
)
def test_every_declaration_field_is_validated(
    fresh_registry: None, kwargs: dict[str, Any], expected: str
) -> None:
    def check(row: "pd.Series[Any]") -> CheckResult:
        return PASS

    with pytest.raises(ValueError, match=expected):
        reg.register_check(code="CODE", message="m", **kwargs)(check)
    assert reg.CHECKS == []
