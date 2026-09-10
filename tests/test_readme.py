"""The README, executed.

Every Python block in the README is run against the real library, and where the
README shows the output, the block's printed output is compared to it byte for
byte. Nothing is stubbed or patched: the only fixture is the empty registry each
block starts from, which is what a fresh interpreter would give it.

The blocks are run in the order the README presents them, each in its own
registry, so a snippet that would only work after some earlier snippet ran is
caught rather than hidden.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from pandas_row_validation import registry as reg

pytestmark = pytest.mark.fast

README = Path(__file__).resolve().parent.parent / "README.md"
BLOCK = re.compile(r"```(\w*)\n(.*?)```", re.S)


def blocks() -> list[tuple[str, str]]:
    """Every fenced block in the README, as (language, body)."""

    return [(lang, body) for lang, body in BLOCK.findall(README.read_text(encoding="utf-8"))]


def python_blocks() -> list[tuple[int, str, str]]:
    """Each Python block with the output block that follows it, if any."""

    found = blocks()
    pairs: list[tuple[int, str, str]] = []
    for index, (lang, body) in enumerate(found):
        if lang != "python":
            continue
        expected = ""
        if index + 1 < len(found) and found[index + 1][0] == "":
            expected = found[index + 1][1]
        pairs.append((index, body, expected))
    return pairs


def block_id(case: tuple[int, str, str]) -> str:
    return f"block-{case[0]}"


def test_the_readme_has_python_blocks_to_check() -> None:
    """A guard on the guard: if the README stops carrying examples, say so rather
    than passing an empty parametrisation."""

    assert len(python_blocks()) >= 3


def is_template(source: str) -> bool:
    """The "writing a test" block is a template, not part of the worked session."""

    return "test_group(" in source


def session_blocks() -> list[tuple[int, str, str]]:
    """The blocks the README presents as one continuous session."""

    return [case for case in python_blocks() if not is_template(case[1])]


def test_the_readme_session_runs_and_prints_exactly_what_it_shows(
    fresh_registry: None,
) -> None:
    """The worked example, start to finish, in one namespace -- which is what a
    reader following along has. Every shown output is compared byte for byte."""

    namespace: dict[str, Any] = {}
    compared = 0
    for index, source, expected in session_blocks():
        captured = io.StringIO()
        with redirect_stdout(captured):
            exec(compile(source, f"README.md:block-{index}", "exec"), namespace)
        if expected:
            assert captured.getvalue() == expected, f"block {index} prints something else"
            compared += 1
    assert compared >= 2, "the README stopped showing output for its examples"


def test_a_later_block_only_uses_names_an_earlier_one_defined(fresh_registry: None) -> None:
    """A reader pastes these in order; a block reaching for something undefined
    would fail on them and not on us."""

    namespace: dict[str, Any] = {}
    for index, source, _ in session_blocks():
        with redirect_stdout(io.StringIO()):
            exec(compile(source, f"README.md:block-{index}", "exec"), namespace)

    # The session builds a frame and validates it; both names outlive the blocks.
    assert "df" in namespace and "outcomes" in namespace
    assert len(namespace["outcomes"]) == len(namespace["df"])


def test_the_writing_a_test_block_registers_a_working_test(fresh_registry: None) -> None:
    """The template block is checked on its own: it produces a test that runs, not
    just one that imports."""

    import pandas as pd

    source = next(source for _, source, _ in python_blocks() if is_template(source))
    namespace: dict[str, Any] = {}
    exec(compile(source, "README.md:writing-a-test", "exec"), namespace)

    registered = {test.code: test for test in reg.TESTS}
    assert "AGE_ABOVE_LIMIT" in registered
    assert registered["AGE_ABOVE_LIMIT"].depends_on == ["AGE_PRESENT"]

    # The group's prerequisite is real, so the whole thing validates once the
    # suite that defines it is loaded.
    reg.load_suites(["hard_tests"], package="example_suites")
    row = pd.Series({"age": 200, "email": "a@b.com", "start_date": None, "end_date": None})
    assert "AGE_ABOVE_LIMIT" in [outcome.code for outcome in reg.validate_row(row)]


def test_the_example_code_does_not_collide_with_the_shipped_tests(
    fresh_registry: None,
) -> None:
    """A README example that duplicated a shipped code would fail on import for
    anyone who pasted it into a project with the example suites loaded."""

    reg.load_suites(["hard_tests", "soft_tests"], package="example_suites")
    shipped = {test.code for test in reg.TESTS}
    for _, source, _ in python_blocks():
        for code in re.findall(r'@\w+\(\s*"([A-Z_]+)"', source):
            assert code not in shipped, f"README defines {code}, which the suites already own"


@pytest.mark.parametrize(
    "name",
    [
        "docs/writing-tests.md",
        "docs/reporting.md",
        "docs/configuration.md",
        "docs/interfaces.md",
        "docs/cli.md",
        "docs/architecture.md",
        "docs/testing.md",
        "docs/contributing.md",
        "docs/future-work.md",
    ],
)
def test_every_document_the_readme_links_to_exists(name: str) -> None:
    text = README.read_text(encoding="utf-8")
    assert f"]({name})" in text, f"README no longer links to {name}"
    assert (README.parent / name).is_file()


def test_the_readme_shell_commands_name_files_that_exist() -> None:
    text = README.read_text(encoding="utf-8")
    for filename in ("scripts/install-hooks.sh", "run-tests.sh"):
        assert filename in text
        assert (README.parent / filename).is_file()
    assert (README.parent / "pyproject.toml").is_file()


# --- the prose claims, not just the code blocks -----------------------------


def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_the_stated_runtime_dependencies_are_the_real_ones() -> None:
    """The README names pandas and PyYAML; requirements.txt is the contract."""

    lines = [
        line.split("#")[0].strip()
        for line in (README.parent / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert [line.split(">=")[0] for line in lines] == ["pandas", "PyYAML"]
    text = readme_text()
    assert "pandas 2.1+" in text and "PyYAML" in text


def test_the_stated_pandas_floor_is_the_one_the_code_needs() -> None:
    """render_report calls DataFrame.map, which arrived in pandas 2.1; a lower floor
    would promise a version where every CSV render raises."""

    from pandas_row_validation import report

    assert "report.map(" in Path(report.__file__).read_text(encoding="utf-8")
    requirements = (README.parent / "requirements.txt").read_text(encoding="utf-8")
    assert "pandas>=2.1" in requirements


def test_the_package_installs_the_way_the_readme_says() -> None:
    """The README tells people to pip install it; pyproject.toml is what makes that
    true, and it must agree with the package that ships."""

    text = (README.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert "pip install -e ." in readme_text()
    assert 'name = "pandas-row-validation"' in text
    assert 'where = ["src"]' in text
    assert (README.parent / "src" / "pandas_row_validation" / "__init__.py").is_file()


def test_the_declared_version_matches_the_package() -> None:
    import pandas_row_validation

    text = (README.parent / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'^version = "([^"]+)"', text, re.M)
    assert declared is not None
    assert declared.group(1) == pandas_row_validation.__version__


def test_a_bare_bool_return_works_as_the_readme_says(fresh_registry: None) -> None:
    from pandas_row_validation import normalise_result

    assert "a bare `True`/`False` works too" in readme_text()
    assert normalise_result(True, "CODE").passed is True
    assert normalise_result(False, "CODE").failed is True


def test_the_report_is_one_line_per_failure_as_claimed(fresh_registry: None) -> None:
    import pandas as pd

    from pandas_row_validation import build_report, collect_outcomes, load_suites

    assert "One line per failure, not one per row." in readme_text()
    load_suites(["hard_tests"], package="example_suites")
    frame = pd.DataFrame([{"age": -5, "start_date": "2024-05-01", "end_date": "2024-03-01"}])
    report = build_report(collect_outcomes(frame), df=frame)
    assert len(report) == 2, "one row, two failures, two report lines"


def test_the_scope_limits_the_readme_states_hold(fresh_registry: None) -> None:
    """"it does not fix, coerce, or drop rows" -- validation leaves the frame alone."""

    import pandas as pd

    from pandas_row_validation import collect_outcomes, load_suites

    assert "It does not fix, coerce, or drop rows." in readme_text()
    load_suites(["hard_tests"], package="example_suites")
    frame = pd.DataFrame([{"age": -5, "start_date": None, "end_date": None}])
    before = frame.copy(deep=True)
    collect_outcomes(frame)
    assert frame.equals(before)


def test_rule_files_can_only_switch_existing_codes(fresh_registry: None, tmp_path: Any) -> None:
    """"the override rule files can only switch existing tests on or off ...
    never define new ones"."""

    from pandas_row_validation import load_overrides, load_suites

    assert "they cannot define new ones" in readme_text()
    load_suites(["hard_tests"], package="example_suites")
    path = tmp_path / "rules.yaml"
    path.write_text(
        '- name: "invent"\n  action: enable\n  codes: [BRAND_NEW_CODE]\n  match: all\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown code 'BRAND_NEW_CODE'"):
        load_overrides(str(path))


def test_the_suites_the_readme_names_exist(fresh_registry: None) -> None:
    from pandas_row_validation import load_suites, loaded_suites

    assert 'load_suites(["hard_tests", "soft_tests"], package="example_suites")' in readme_text()
    load_suites(["hard_tests", "soft_tests"], package="example_suites")
    assert loaded_suites() == {"base", "hard_tests", "soft_tests"}


# --- the documented CLI is the real CLI -------------------------------------


def test_every_option_of_the_entry_point_is_documented() -> None:
    """docs/cli.md is the reference manual for the entry point, so a flag added
    without a section there is a flag nobody will find."""

    import main

    document = (README.parent / "docs" / "cli.md").read_text(encoding="utf-8")
    parser = main.build_parser()
    for action in parser._actions:  # the public API for this is the option strings
        for option in action.option_strings:
            assert f"`{option}" in document, f"{option} is not documented in docs/cli.md"


def test_no_option_is_documented_that_does_not_exist() -> None:
    """The other direction: a flag removed from the entry point leaves its section
    behind, and a reader tries it."""

    import re

    import main

    document = (README.parent / "docs" / "cli.md").read_text(encoding="utf-8")
    real = {option for action in main.build_parser()._actions
            for option in action.option_strings}
    documented = set(re.findall(r"^### `(--?[a-z-]+)", document, re.M))
    assert documented <= real, f"documented but not real: {sorted(documented - real)}"
