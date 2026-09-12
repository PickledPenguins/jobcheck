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
import builtins
import inspect
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import jobcheck as prv
from jobcheck import rules
from jobcheck.results import CheckResult

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


def known_names() -> set[str]:
    """Every name a document may show in call form without promising our API.

    This package's own surface, the methods of the types it exports -- a reader
    will call `CheckResult.passed` as `passed(...)` -- pandas' frame and series
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
        | {prv.PASSED, prv.FAILED, prv.DISABLED, prv.SKIPPED, prv.ERRORED}
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

    real = {check.code for check in prv.CHECKS} | {
        # Codes the documents invent to show a reader writing their own check.
        "AGE_ABOVE_LIMIT", "THREADS_INT", "BRAND_NEW_CODE", "ADDED_AT_RUNTIME",
        "FIELD_MISSING", "NO_SUCH_CODE", "SOURCE_CODE", "MY_CODE",
    }
    unknown = sorted(documented_codes()[name] - real)
    assert unknown == [], f"{name}: no such check code: {unknown}"


def test_every_exit_code_the_entry_point_can_return_is_documented() -> None:
    """The exit codes are the contract a scheduled job is written against, and
    they live in one table; a new one added without a row there is invisible."""

    source = ast.parse((ROOT / "examples" / "main.py").read_text(encoding="utf-8"))
    raised = {
        int(node.exc.args[0].value)
        for node in ast.walk(source)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and getattr(node.exc.func, "id", None) == "SystemExit"
        and node.exc.args
        and isinstance(node.exc.args[0], ast.Constant)
        and isinstance(node.exc.args[0].value, int)
    }
    # 0 for a clean run and 1 for an uncaught exception are the interpreter's, not
    # the entry point's, so they are never raised in the source and are added here.
    expected = raised | {0, 1}
    table = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    documented = {int(value) for value in re.findall(r"^\| (\d+) \| ", table, re.M)}
    assert expected <= documented, f"undocumented exit code(s): {sorted(expected - documented)}"
    assert documented <= expected, f"documented exit code(s) that cannot happen: {sorted(documented - expected)}"


def test_the_public_name_check_allows_a_builtin_and_refuses_an_invention(tmp_path: Path) -> None:
    """The rule the check applies, asserted directly rather than through a document.

    Regression: the builtins were a hand-written list of eight, so writing
    `exec(...)` in a document failed a check that means to allow any builtin.
    """

    assert called_names("call `exec()` and `zip()` and `validate()` here") == []
    assert called_names("call `frobnicate()` here") == ["frobnicate"]


def collected(marker: str) -> int:
    """How many tests pytest collects for one marker, asked of pytest itself.

    A subprocess, because collecting inside the running session would count this
    session's own state rather than a clean one. ``-q --collect-only`` prints one
    ``path: count`` line per file, which is what is summed here.
    """

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", marker],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    counts = re.findall(r"^\S+\.py: (\d+)$", result.stdout, re.M)
    assert counts, f"no collection counts in:\n{result.stdout}"
    return sum(int(count) for count in counts)


def test_the_documented_suite_sizes_are_the_real_ones() -> None:
    """The numbers in the suite table drifted by five, three and eight before
    anything compared them with a collection: they are the one documented
    surface nothing else gates."""

    # The long suite's size includes the three property tests, which an
    # interpreter without hypothesis does not collect at all -- so on that
    # interpreter the documented number is right and the collection is short by
    # three. The long suite refuses to run there for the same reason.
    pytest.importorskip(
        "hypothesis", reason="the long-suite size counts the property tests"
    )

    table = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    documented = {
        mode: int(size.replace(",", ""))
        for mode, size in re.findall(r"\| `\./tests/run-tests\.sh (\w+)` \| ([\d,]+) tests", table)
    }
    fast, long = collected("fast"), collected("long")
    assert documented.get("fast") == fast, f"docs say {documented.get('fast')}, pytest collects {fast}"
    assert documented.get("long") == long, f"docs say {documented.get('long')}, pytest collects {long}"
    assert documented.get("all") == fast + long, (
        f"docs say {documented.get('all')}, fast plus long is {fast + long}")


def test_the_documented_catalog_counts_are_the_real_ones() -> None:
    """The README calls the two catalogs a case total, and testing.md breaks it
    down by level; both are written by hand and neither was checked."""

    cases = sorted(p.parent for p in (ROOT / "tests" / "examples").rglob("cmd"))
    failures = sorted(p.parent for p in (ROOT / "tests" / "failures").rglob("cmd"))
    levels = {level: sum(f"Level:    {level}" in (case / "README.md").read_text(encoding="utf-8")
                         for case in cases)
              for level in ("simple", "moderate", "complex")}

    testing = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    documented = re.search(
        r"holds (\d+) cases at three levels -- (\d+) simple, (\d+) moderate, (\d+) complex --\s+"
        r"and `tests/failures/` holds (\d+),",
        testing.replace("—", "--"),
    )
    assert documented, "docs/testing.md no longer states the catalog counts in the expected shape"
    assert [int(value) for value in documented.groups()] == [
        len(cases), levels["simple"], levels["moderate"], levels["complex"], len(failures)]

    readme = README.read_text(encoding="utf-8")
    total = re.search(r"the (\d+)-case example and failure catalogs", readme)
    assert total, "the README index no longer states a case total"
    assert int(total.group(1)) == len(cases) + len(failures)
