"""The documents against the public API they describe -- both directions.

Every call a document shows is bound against the real signature, which catches an
argument that became required, a keyword that was renamed, and a function that no
longer exists; every exported name is documented in `interfaces.md` and nothing
there is gone; every check code a document shows is one that exists. `tests/test_readme.py`
executes the README's own session, and `test_docs_blocks_unit.py` runs the blocks.

The drift this was written for: a call that appeared in three
documents for as long as `package=` had a default, and went on appearing after it
became required, where it raises TypeError for anyone who copies it.
"""

from __future__ import annotations

import ast
import builtins
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


def test_interfaces_does_not_document_names_that_are_gone() -> None:
    interfaces = (ROOT / "docs" / "interfaces.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^### `([A-Za-z_][A-Za-z0-9_]*)", interfaces, re.M))
    unknown = sorted(name for name in documented if not hasattr(prv, name))
    assert unknown == [], f"documented but not exported: {unknown}"



def _main() -> Any:
    """The demo entry point, imported the way the catalog runs it."""

    import main

    return main


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
        | {key.upper() for key in rules.RULE_KEYS}
        # Words that happen to be shouted in prose or shell, not codes.
        | {"CSV", "YAML", "PATH", "ROW", "COLUMN", "NAME", "OFF", "ON", "TODO",
           "README", "PYTHON", "LEGACY_A", "MODERN", "STREAM", "BATCH", "NO_KEY"}
        # The demo entry point's own constants, documented in cli.md.
        | {name for name in vars(_main()) if name.isupper()}
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
        "ORDER_ID_PRESENT", "ORDER_ID_NUMERIC",
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


#: The width `contributing.md` claims, and the directories it is claimed for.
#: `tests/` is deliberately absent: 74 of its lines are over, and they are table
#: rows, pinned error messages and parametrize entries where wrapping costs more
#: than it buys. The claim and this list are stated together in that document.
