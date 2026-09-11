"""The documents, checked against the code they describe -- both directions.

`tests/test_readme.py` executes the README's own session. These cover the rest of
`docs/`, where the examples are fragments rather than a runnable session and so
cannot simply be executed: instead every call they show is bound against the real
signature, which is what catches an argument that became required, a keyword that
was renamed, and a function that no longer exists.

The drift this was written for: a call that appeared in three
documents for as long as `package=` had a default, and went on appearing after it
became required, where it raises TypeError for anyone who copies it.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

import jobcheck as prv

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / "docs").glob("*.md"))
README = ROOT / "README.md"
#: A README longer than this has stopped being an index and become a manual.
README_MAX_LINES = 300

PUBLIC = {name: getattr(prv, name) for name in prv.__all__}
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


@pytest.mark.parametrize("path", DOCS + [README], ids=lambda p: p.name)
def test_no_document_names_a_public_function_that_is_gone(path: Path) -> None:
    """A name in backticks with a call after it is a promise the reader will try."""

    import pandas as pd

    text = path.read_text(encoding="utf-8")
    # Names a document may legitimately mention that are not this package's:
    # pandas' own methods, the placeholder names the examples use for a group or
    # a callback, and the builtins.
    # A public type's methods count as public names: CheckResult.passed is
    # documented as `report(...)`, and a reader will call it that way.
    methods = {name for value in PUBLIC.values() if inspect.isclass(value)
               for name in dir(value)}
    known = (set(dir(prv)) | methods | set(dir(pd.DataFrame)) | set(dir(pd.Series))
             | {"group", "check", "rule", "main", "progress", "bool", "count",
                "print", "len", "str", "int", "list", "dict", "open", "sorted",
                "perf_counter"})
    for name in set(re.findall(r"`([a-z_][a-z0-9_]*)\(", text)):
        assert name in known or name.startswith("_"), f"{path.name}: `{name}()` does not exist"


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


def test_the_readme_stays_an_index() -> None:
    """New material belongs in the document that owns the subject, not here."""

    lines = README.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= README_MAX_LINES, f"README is {len(lines)} lines"


def test_every_document_is_reachable_from_the_readme() -> None:
    """A document nobody links to is a document nobody reads."""

    linked = set(re.findall(r"\]\(docs/([a-z\-]+\.md)\)", README.read_text(encoding="utf-8")))
    assert {path.name for path in DOCS} - linked == set()


@pytest.mark.parametrize("path", DOCS + [README], ids=lambda p: p.name)
def test_no_internal_link_or_anchor_is_dead(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        file_part, _, anchor = target.partition("#")
        target_path = (path.parent / file_part).resolve() if file_part else path
        assert target_path.exists(), f"{path.name}: {target} does not exist"
        if anchor:
            headings = re.findall(r"^#{1,6} (.+)$", target_path.read_text(encoding="utf-8"), re.M)
            slugs = {re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-")
                     for h in headings}
            assert anchor in slugs, f"{path.name}: {target} has no such heading"


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_every_document_says_how_to_get_back(path: Path) -> None:
    """The index links out; each document links back, or a reader is stranded."""

    assert "](../README.md)" in path.read_text(encoding="utf-8")


def test_the_shipped_rule_keys_are_all_documented() -> None:
    """Configuration is the document that owns the rule-file format."""

    from jobcheck import rules

    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    for key in rules.RULE_KEYS:
        assert f"`{key}`" in configuration or f"{key}:" in configuration, key
    # The two actions are literals in the parser rather than a constant, so they
    # are named here as well: a third one added without a document is the drift
    # this catches.
    source = (ROOT / "src" / "jobcheck" / "rules.py").read_text(encoding="utf-8")
    assert 'action not in ("enable", "disable")' in source, "the actions moved; update the doc check"
    for action in ("enable", "disable"):
        assert action in configuration, action


def test_the_status_vocabulary_is_documented() -> None:
    """Status values are permanent identifiers; a new one nobody documents is a
    value that turns up in someone's report with no explanation."""

    from jobcheck.results import Status

    writing = (ROOT / "docs" / "writing-checks.md").read_text(encoding="utf-8")
    for status in Status:
        assert status.name in writing, status.name


@pytest.mark.parametrize("outcome", ["passed", "failed", "errored", "skipped", "disabled"])
def test_every_outcome_name_is_documented(outcome: str) -> None:
    reporting = (ROOT / "docs" / "reporting.md").read_text(encoding="utf-8")
    writing = (ROOT / "docs" / "writing-checks.md").read_text(encoding="utf-8")
    assert outcome in reporting or outcome in writing
