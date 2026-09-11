"""What an adopter actually gets: the library alone, with nothing of ours in it.

These are the checks that would have caught the two findings the fourth review
turned up -- the example suites travelling inside the distribution, and the
library being unusable from outside this repository. They install nothing: the
package is imported from ``src/`` the way an installed copy would be, in a
subprocess whose working directory is not this project.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jobcheck.results import CheckResult, PASS, Status

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PACKAGE = SRC / "jobcheck"

pytestmark = pytest.mark.long


def run_isolated(code: str, cwd: Path, extra_path: list[Path] | None = None) -> subprocess.CompletedProcess[str]:
    """Run code with only the library (and anything named) importable.

    Deliberately not from the repository root: PYTHONPATH carries `src` and
    nothing else unless the check says otherwise, so an accidental dependency on
    the working directory shows up as an ImportError.
    """

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in [SRC, *(extra_path or [])])
    return subprocess.run(
        [sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True, timeout=120
    )


# --- what ships -------------------------------------------------------------


def test_the_package_ships_no_checks_of_its_own() -> None:
    """Regression: the example check files lived in the package, so they were in
    the wheel and registered our examples into every consumer's registry."""

    shipped = sorted(path.relative_to(PACKAGE).as_posix()
                     for path in PACKAGE.rglob("check_*.py"))
    assert shipped == []


def test_the_example_checks_live_outside_the_package() -> None:
    checks = ROOT / "examples" / "checks"
    for name in ("check_row_shape.py", "check_age.py", "check_dates.py", "check_email.py"):
        assert (checks / name).is_file()


def test_the_annotations_are_advertised() -> None:
    """Without the marker, mypy treats an installed copy as untyped."""

    assert (PACKAGE / "py.typed").is_file()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'jobcheck = ["py.typed"]' in pyproject


def test_every_shipped_module_is_importable_on_its_own(tmp_path: Path) -> None:
    modules = sorted(path.stem for path in PACKAGE.glob("*.py") if path.stem != "__init__")
    code = "\n".join(f"import jobcheck.{name}" for name in modules) + "\nprint('ok')"
    result = run_isolated(code, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


# --- what an adopter does with it ------------------------------------------


def test_importing_the_library_registers_nothing(tmp_path: Path) -> None:
    result = run_isolated(
        "import jobcheck as v; print(len(v.CHECKS), v.__version__)", cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["0", "0.2.0"]


def adopter_package(tmp_path: Path) -> Path:
    """A minimal file of someone else's checks, in their own directory."""

    theirs = tmp_path / "their_checks"
    theirs.mkdir(parents=True)
    (theirs / "check_theirs.py").write_text(
        "from jobcheck import PASS, Status, CheckResult, is_null, register_check\n\n\n"
        '@register_check("FIELD_MISSING", "Their field is missing")\n'
        "def field_present(row):\n"
        "    return CheckResult(Status.MISSING) if is_null(row['field']) else PASS\n",
        encoding="utf-8",
    )
    return tmp_path


def test_an_adopter_gets_only_their_own_tests(tmp_path: Path) -> None:
    """Regression: a consumer's registry picked up ROW_ALL_NULL, our example."""

    home = adopter_package(tmp_path)
    result = run_isolated(
        "import pandas as pd\n"
        "from jobcheck import load_checks, CHECKS, validate_row\n"
        "load_checks(['their_checks/check_theirs.py'])\n"
        "print(sorted(t.code for t in CHECKS))\n"
        "print([o.code for o in validate_row(pd.Series({'field': None}))])\n",
        cwd=home,
        extra_path=[home],
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["['FIELD_MISSING']", "['FIELD_MISSING']"]


def test_an_adopter_can_produce_a_report(tmp_path: Path) -> None:
    """The whole journey from outside: load, validate, render, write."""

    home = adopter_package(tmp_path)
    result = run_isolated(
        "import pandas as pd\n"
        "from jobcheck import (build_report, validate, load_checks,\n"
        "                      render_report, write_report)\n"
        "load_checks(['their_checks/check_theirs.py'])\n"
        "df = pd.DataFrame([{'id': 1, 'field': 'x'}, {'id': 2, 'field': None}])\n"
        "report = build_report(validate(df), df=df, key_column='id')\n"
        "write_report(report, 'report.csv')\n"
        "print(render_report(report, fmt='csv').splitlines()[1])\n",
        cwd=home,
        extra_path=[home],
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("2,FIELD_MISSING,MISSING (1),0,failed")
    assert (home / "report.csv").is_file()


def test_a_misspelled_path_says_so_rather_than_raising_an_import_error(
    tmp_path: Path,
) -> None:
    """A typo in a path is a missing file, named, rather than an ImportError."""

    home = adopter_package(tmp_path)
    result = run_isolated(
        "from jobcheck import load_checks\n"
        "try:\n"
        "    load_checks(['thier_checks/check_theirs.py'])\n"
        "except ValueError as exc:\n"
        "    print(exc)\n",
        cwd=home,
        extra_path=[home],
    )
    assert result.returncode == 0, result.stderr
    assert "No check file at 'thier_checks/check_theirs.py'" in result.stdout
    assert "nothing is discovered" in result.stdout


def test_a_null_field_is_not_truthy_for_an_adopter(tmp_path: Path) -> None:
    """The pandas trap the docs warn about: a missing value arrives as NaN, which
    is truthy, so `if row["field"]` silently passes. is_null is the way through."""

    home = adopter_package(tmp_path)
    result = run_isolated(
        "import pandas as pd\n"
        "from jobcheck import is_null\n"
        "row = pd.DataFrame([{'field': 'x'}, {'field': None}]).iloc[1]\n"
        "print(bool(row['field']), is_null(row['field']))\n",
        cwd=home,
        extra_path=[home],
    )
    assert result.stdout.split() == ["True", "True"]


# --- the version floor ------------------------------------------------------


# Stdlib that arrived after the floor declared in pyproject.toml. Matched against
# parsed imports and attribute access, not raw text: a comment or a string that
# happens to say "tomllib" is not a promise the project cannot keep, and an
# earlier text-matching version of this check excluded its own file to cope.
TOO_NEW_MODULES = {"tomllib": "3.11"}
TOO_NEW_FROM = {
    ("typing", "Self"): "3.11",
    ("typing", "override"): "3.12",
    ("enum", "StrEnum"): "3.11",
    ("datetime", "UTC"): "3.11",
    ("itertools", "batched"): "3.12",
}
TOO_NEW_ATTRIBUTES = {
    "typing.Self": "3.11",
    "typing.override": "3.12",
    "enum.StrEnum": "3.11",
    "datetime.UTC": "3.11",
    "itertools.batched": "3.12",
}


def too_new_uses(tree: ast.AST) -> list[str]:
    """Every use of a stdlib name newer than the declared floor, by import or attribute."""

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in TOO_NEW_MODULES:
                    found.append(f"import {alias.name} ({TOO_NEW_MODULES[root]})")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in TOO_NEW_MODULES:
                found.append(f"from {module} ({TOO_NEW_MODULES[module.split('.')[0]]})")
            for alias in node.names:
                floor = TOO_NEW_FROM.get((module, alias.name))
                if floor:
                    found.append(f"from {module} import {alias.name} ({floor})")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            dotted = f"{node.value.id}.{node.attr}"
            floor = TOO_NEW_ATTRIBUTES.get(dotted)
            if floor:
                found.append(f"{dotted} ({floor})")
    return found


def test_nothing_uses_a_stdlib_newer_than_the_declared_floor() -> None:
    """Regression: two checks imported tomllib, which is 3.11, while pyproject,
    the README and the CI matrix all said 3.10."""

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in pyproject

    offenders: list[str] = []
    for directory in ("src", "examples", "tests", "scripts"):
        for path in (ROOT / directory).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            offenders += [f"{path.relative_to(ROOT)}: {use}" for use in too_new_uses(tree)]
    assert offenders == []


def test_the_floor_guard_catches_a_real_violation() -> None:
    """A guard nobody has seen fail is a guard nobody knows works."""

    assert too_new_uses(ast.parse("import tomllib")) == ["import tomllib (3.11)"]
    assert too_new_uses(ast.parse("from typing import Self")) == [
        "from typing import Self (3.11)"
    ]
    assert too_new_uses(ast.parse("import datetime\nx = datetime.UTC")) == [
        "datetime.UTC (3.11)"
    ]
    # The false positives the text-matching version produced.
    assert too_new_uses(ast.parse('x = "tomllib is 3.11"')) == []
    assert too_new_uses(ast.parse("# mentions StrEnum in a comment")) == []
