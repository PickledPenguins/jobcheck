"""The documents against the public API they describe -- both directions.

Every call a document shows is bound against the real signature, which catches an
argument that became required, a keyword that was renamed, and a function that no
longer exists; every exported name is documented in `interfaces.md` -- each function
with its real signature, each type with its fields or members -- and nothing there is
gone; every check code a document shows is one that exists. `tests/test_readme.py`
executes the README's own session, and `test_docs_blocks_unit.py` runs the blocks.

The drift this was written for: a call that appeared in three
documents for as long as `package=` had a default, and went on appearing after it
became required, where it raises TypeError for anyone who copies it.
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import enum
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

import jobcheck as prv
from jobcheck import rules
from jobcheck.results import _normalize_verdict
from doc_files import DOCS, PUBLIC, README, ROOT

pytestmark = pytest.mark.fast

CALLABLES = {name: value for name, value in PUBLIC.items() if inspect.isroutine(value)}


def python_blocks(path: Path) -> list[str]:
    """Every ```python block in one document."""

    return re.findall(r"```python\n(.*?)```", path.read_text(encoding="utf-8"), re.S)


def documented_calls(source: str) -> list[tuple[str, int, list[str]]]:
    """Calls to public functions in one block: (name, positional count, keywords)."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # a deliberate fragment; the surrounding prose owns it
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
        if name not in CALLABLES:
            continue
        if any(isinstance(a, ast.Starred) for a in node.args) or \
                any(k.arg is None for k in node.keywords):
            continue  # *args / **kwargs: nothing to check
        found.append((name, len(node.args), [k.arg for k in node.keywords if k.arg]))
    return found


@pytest.mark.parametrize("path", DOCS + [README], ids=lambda p: p.name)
def test_every_documented_call_matches_the_real_signature(path: Path) -> None:
    for block in python_blocks(path):
        for name, positional, keywords in documented_calls(block):
            signature = inspect.signature(CALLABLES[name])
            try:
                signature.bind(*[None] * positional, **{key: None for key in keywords})
            except TypeError as exc:
                pytest.fail(
                    f"{path.name}: {name}({', '.join(['...'] * positional + keywords)}) "
                    f"does not match {name}{signature}: {exc}"
                )


def known_names() -> set[str]:
    """Every name a document may show in call form without promising our API.

    This package's own surface, the methods of the types it exports -- a reader
    will call `Verdict.passed` as `passed(...)` -- pandas' frame and series
    methods, every builtin, and the placeholder names the examples use for a
    group or a callback.

    The builtins come from `builtins` rather than from a list somebody keeps
    adding to: the hand-written version held eight of them and failed the ninth
    time one was mentioned in prose. No public name here shadows a builtin, so
    allowing them all hides nothing this package could remove.
    """

    import pandas as pd

    methods = {name for value in PUBLIC.values() if inspect.isclass(value)
               for name in dir(value)}
    return (set(dir(prv)) | methods | set(dir(pd.DataFrame)) | set(dir(pd.Series))
            | set(dir(builtins))
            | {"group", "check", "rule", "main", "progress", "perf_counter"})


def called_names(text: str) -> list[str]:
    """Names shown as `name(` that nothing provides, sorted."""

    return sorted({name for name in re.findall(r"`([a-z_][a-z0-9_]*)\(", text)
                   if name not in known_names() and not name.startswith("_")})


@pytest.mark.parametrize("path", DOCS + [README], ids=lambda p: p.name)
def test_no_document_names_a_public_function_that_is_gone(path: Path) -> None:
    """A name in backticks with a call after it is a promise the reader will try."""

    text = path.read_text(encoding="utf-8")
    known = known_names()
    for name in set(re.findall(r"`([a-z_][a-z0-9_]*)\(", text)):
        assert name in known or name.startswith("_"), (
            f"{path.name}: `{name}()` does not exist. A backticked name followed by `(` "
            "reads as a call a reader will try, so it has to be one this package, pandas "
            "or the builtins provide. Name it without the parentheses if it is neither."
        )


def test_every_exported_name_is_documented_in_interfaces() -> None:
    """The other direction: a public name nobody documented is a name nobody finds."""

    interfaces = (ROOT / "docs" / "interfaces.md").read_text(encoding="utf-8")
    missing = [name for name in prv.__all__ if name not in interfaces]
    assert missing == [], f"undocumented public names: {missing}"


INTERFACES = ROOT / "docs" / "interfaces.md"

#: Stands for "no default" on either side of the comparison below.
NO_DEFAULT = object()


def documented_parameters(form: str) -> list[tuple[str, object]] | None:
    """(name, default) for each parameter of one documented call form, or None when
    the form is a call with arguments rather than a signature."""

    try:
        arguments = ast.parse(f"def _({form}): pass").body[0].args  # type: ignore[attr-defined]
        positional = [*arguments.posonlyargs, *arguments.args]
        padding = [None] * (len(positional) - len(arguments.defaults))
        pairs = [*zip(positional, [*padding, *arguments.defaults]),
                 *zip(arguments.kwonlyargs, arguments.kw_defaults)]
        return [(argument.arg, NO_DEFAULT if default is None else ast.literal_eval(default))
                for argument, default in pairs]
    except (SyntaxError, ValueError):
        return None


def real_parameters(function: Any) -> list[tuple[str, object]]:
    return [(parameter.name, NO_DEFAULT if parameter.default is parameter.empty
             else parameter.default)
            for parameter in inspect.signature(function).parameters.values()]


@pytest.mark.parametrize(
    "name", sorted(name for name, value in PUBLIC.items() if inspect.isfunction(value)))
def test_interfaces_shows_every_exported_function_s_real_signature(name: str) -> None:
    """Regression: `render_comments`, `row_explanation` and `summarize_outcomes` had
    no signature anywhere, and the name check passed on one mention in a list.
    Parameter names, order and defaults must all match."""

    text = INTERFACES.read_text(encoding="utf-8")
    forms = re.findall(rf"`{name}\(([^`]*)\)(?: -> [^`]*)?`", text)
    real = real_parameters(PUBLIC[name])
    assert any(documented_parameters(form) == real for form in forms), (
        f"interfaces.md shows no `{name}(...)` with the parameters "
        f"{inspect.signature(PUBLIC[name])}; it shows {forms}")


def section_of(text: str, name: str) -> str:
    """One `### \\`name\\`` section of interfaces.md, up to the next heading."""

    match = re.search(rf"^### `{name}`\n(.*?)(?=^##)", text, re.M | re.S)
    assert match, f"interfaces.md has no section headed `{name}`"
    return match.group(1)


@pytest.mark.parametrize("name", sorted(
    name for name, value in PUBLIC.items()
    if isinstance(value, type) and (dataclasses.is_dataclass(value)
                                    or issubclass(value, enum.Enum))))
def test_interfaces_names_every_field_and_member_of_an_exported_type(name: str) -> None:
    section = section_of(INTERFACES.read_text(encoding="utf-8"), name)
    value = PUBLIC[name]
    if dataclasses.is_dataclass(value):
        missing = [field.name for field in dataclasses.fields(value)
                   if f"`{field.name}`" not in section and f"`{field.name}:" not in section]
    else:
        missing = [member.name for member in value if member.name not in section]
    assert missing == [], f"interfaces.md, `{name}`: not named: {missing}"


def test_interfaces_does_not_document_names_that_are_gone() -> None:
    interfaces = (ROOT / "docs" / "interfaces.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^### `([A-Za-z_][A-Za-z0-9_]*)", interfaces, re.M))
    unknown = sorted(name for name in documented if not hasattr(prv, name))
    assert unknown == [], f"documented but not exported: {unknown}"


def glance_rows() -> dict[str, list[str]]:
    """The cells of each row of interfaces.md's "At a glance" tables, by name."""

    text = INTERFACES.read_text(encoding="utf-8")
    match = re.search(r"^## At a glance\n(.*?)(?=^## )", text, re.M | re.S)
    assert match, "interfaces.md has no `## At a glance` section"
    rows = {}
    for line in match.group(1).splitlines():
        name = re.match(r"\| \[?`(\w+)`", line)
        if name:
            rows[name.group(1)] = [cell.strip() for cell in line.strip("|").split(" | ")]
    return rows


def test_at_a_glance_has_one_row_per_exported_name() -> None:
    """The summary tables exist so a reader never has to hunt: a name missing from
    them is exactly the scattering they replace."""

    rows = glance_rows()
    assert sorted(rows) == sorted(prv.__all__), (
        f"missing: {sorted(set(prv.__all__) - set(rows))}; "
        f"not exported: {sorted(set(rows) - set(prv.__all__))}")


@pytest.mark.parametrize(
    "name", sorted(name for name, value in PUBLIC.items() if inspect.isfunction(value)))
def test_at_a_glance_shows_each_function_s_real_arguments(name: str) -> None:
    """Required cell: the parameters without a default; optional cell: the rest as
    `name=default`. Both in the real order, both with the real defaults."""

    _, required, optional, *_ = glance_rows()[name]
    documented = [(argument, NO_DEFAULT) for argument in re.findall(r"`(\w+)`", required)]
    for argument, default in re.findall(r"`(\w+)=([^`]*)`", optional):
        documented.append((argument, ast.literal_eval(default)))
    assert documented == real_parameters(PUBLIC[name]), (
        f"At a glance, `{name}`: shows {required} / {optional}; "
        f"the signature is {inspect.signature(PUBLIC[name])}")



def _main() -> Any:
    """The demo entry point, imported the way the catalog runs it."""

    import main

    return main


def variables_read() -> set[str]:
    """Every environment variable the code or the suite reads or sets, and every
    variable the suite runner expands. Upper-case and underscored like a code, and
    documented by name, so they are derived here rather than listed."""

    names: set[str] = set()
    for path in [*ROOT.glob("src/jobcheck/*.py"), *ROOT.glob("examples/*.py"),
                 *ROOT.glob("scripts/*.py"), *ROOT.glob("tests/*.py")]:
        names.update(re.findall(r"environ(?:\.get|\.setdefault)?\s*[(\[]\s*[\"']([A-Z][A-Z0-9_]*)[\"']",
                                path.read_text(encoding="utf-8")))
    runner = (ROOT / "tests" / "run-tests.sh").read_text(encoding="utf-8")
    names.update(re.findall(r"\$\{?([A-Z][A-Z0-9_]*)", runner))
    return names


def documented_codes() -> dict[str, set[str]]:
    """Every CODE_SHAPED token each document shows, minus the ones that are not codes.

    A check code is the one identifier in these documents that a reader will paste
    into a rule file, so a document naming a code that no longer exists sends them
    to a load-time error. The exclusions are derived rather than listed: the
    package's own exported names, the status names, the outcome names and the rule
    keys are all upper-case too, and none of them is a check code.
    """

    from jobcheck.results import Status

    not_a_code = (
        {name.upper() for name in prv.__all__}
        | {member.name for member in Status}
        | {member.name for member in prv.Outcome}
        | {key.upper() for key in rules._RULE_KEYS}
        # Words that happen to be shouted in prose or shell, not codes.
        | {"CSV", "YAML", "PATH", "ROW", "COLUMN", "NAME", "OFF", "ON", "TODO",
           "README", "PYTHON", "LEGACY_A", "MODERN", "STREAM", "BATCH", "NO_KEY"}
        # The demo entry point's own constants, documented in cli.md.
        | {name for name in vars(_main()) if name.isupper()}
        | variables_read()
    )
    found: dict[str, set[str]] = {}
    for path in DOCS + [README]:
        tokens = set(re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b",
                                path.read_text(encoding="utf-8")))
        found[path.name] = tokens - not_a_code
    return found


@pytest.mark.parametrize("name", [path.name for path in DOCS + [README]])
def test_every_check_code_a_document_shows_is_a_real_one(
    name: str, example_checks: None
) -> None:
    """Regression: a document showed `AGE_IN_RANGE`, which no check ever defined,
    and a reader writing a rule file for it would meet an unknown-code error."""

    real = set(prv.registry_table()["code"]) | {
        # Codes the documents invent to show a reader writing their own check.
        "AGE_ABOVE_LIMIT", "THREADS_INT", "BRAND_NEW_CODE", "ADDED_AT_RUNTIME",
        "FIELD_MISSING", "NO_SUCH_CODE", "SOURCE_CODE", "MY_CODE",
        "ORDER_ID_PRESENT", "ORDER_ID_NUMERIC", "RUN_DIR_PRESENT", "RUN_DIR_EXISTS",
        "VAL_IN_RANGE", "BASE_EXISTS", "CHILD_EXISTS",
    }
    unknown = sorted(documented_codes()[name] - real)
    assert unknown == [], f"{name}: no such check code: {unknown}"



def test_the_public_name_check_allows_a_builtin_and_refuses_an_invention(tmp_path: Path) -> None:
    """The rule the check applies, asserted directly rather than through a document.

    Regression: the builtins were a hand-written list of eight, so writing
    `exec(...)` in a document failed a check that means to allow any builtin.
    """

    assert called_names("call `exec()` and `zip()` and `validate()` here") == []
    assert called_names("call `frobnicate()` here") == ["frobnicate"]



def test_no_document_says_a_bare_bool_or_status_is_converted() -> None:
    """A check returning `True` or `Status.MISSING` raises; two documents once said
    it was converted, and nothing executable can read a prose table."""

    for value in (True, False, prv.Status.MISSING):
        with pytest.raises(TypeError):
            _normalize_verdict(value, "X")
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"bare bools? (still work|is converted|are converted)", text,
                             re.I), (
            f"{path.name} says a bare bool is accepted; _normalize_verdict refuses it")
        assert "status value is converted" not in text, (
            f"{path.name} says a bare status is accepted; _normalize_verdict refuses it")
