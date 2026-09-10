"""Row-validation engine: what tests exist, and what happens to one row.

Registration, suite discovery, dependency validation and ordering, per-row
evaluation, and the registry tables. The override rule format lives in
:mod:`pandas_row_validation.rules`, the value types a test returns in
:mod:`pandas_row_validation.results`, table rendering in :mod:`pandas_row_validation.tables`, per-row
metadata in :mod:`pandas_row_validation.context`, and reporting in
:mod:`pandas_row_validation.report`.

The three ``load_overrides*`` functions here are thin wrappers over the parser in
:mod:`pandas_row_validation.rules`: they supply the codes that exist, which is the only
thing that module needs from this one.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from .context import RowContext
from . import rules
# MatchCriterion and OverrideRule are re-exported from here for
# __init__.py, which imports the public rule types from the registry
# rather than reaching into .rules directly.
from .rules import MatchCriterion, OverrideRule, rule_matches
from .results import (
    DISABLED,
    ERRORED,
    FAILED,
    PASSED,
    SKIPPED,
    Status,
    TestOutcome,
    normalise_result,
)
from .tables import format_table

# Tests placed directly in the top-level package (not in a suite subpackage)
# belong to this suite and are loaded by every load_suites() call.
BASE_SUITE = "base"

# What an author writes: (row) or (row, ctx), returning PASS, a TestResult, a
# bool, or a Status value. The engine stores the normalised two-argument form.
TestFn = Callable[..., Any]
RunnerFn = Callable[["pd.Series[Any]", RowContext | None], Any]


@dataclass
class Test:
    """One named validation rule.

    ``code`` is a permanent identifier.  It is never renumbered and never
    reused, even after the test it named is deleted: override YAML files
    written by non-developers, saved reports and downstream tooling all refer
    to codes, so a reused code silently changes the meaning of existing data.

    A test reads whatever columns it needs from the row itself, so there is no
    ``column`` field: these rules are row-scoped, and many of them weigh several
    columns together.
    """

    __test__ = False  # not a pytest test class, despite the name

    code: str
    message: str
    fn: RunnerFn
    suite: str
    source_file: str
    default_enabled: bool = True
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    layer: int = 0
    """How deep in the dependency graph this test sits: 0 with no prerequisites,
    otherwise one more than its deepest prerequisite. Computed by
    :func:`validate_registry`, never set by hand. A low layer means a
    fundamental test, which is what makes it a root cause."""


TESTS: list[Test] = []

_LOADED_SUITES: set[str] = set()
# Test files imported by path through load_test_files(), resolved and in load
# order. Kept separate from _LOADED_SUITES because a file has no suite of its
# own: it lands in BASE_SUITE, and only the path identifies it again.
_LOADED_FILES: list[str] = []
# Modules that have registered a test, so clear_registry can evict them from
# sys.modules; without that a later import is a no-op -- Python caches modules --
# and the registry would silently stay empty. Recorded at registration rather
# than at import, so a module pulled in by any route is still tracked.
_REGISTERING_MODULES: set[str] = set()
# Cached topological order over depends_on edges.  The graph only changes when
# the registry changes, so it is computed once per registry state and never
# inside the per-row loop.
_TOPO_ORDER: list[Test] | None = None


def _infer_suite(fn: TestFn) -> str:
    """Derive a test's suite from the module that defines it.

    ``pandas_row_validation.hard_tests.test_age`` -> ``hard_tests``; a module sitting
    directly in the package (``pandas_row_validation.test_row_shape``) or defined outside
    any package (a script, a notebook) -> :data:`BASE_SUITE`. Never passed by
    hand, so a test file cannot drift out of sync with where it lives.
    """

    # A function defined by exec() -- a notebook cell, a REPL, a doc example --
    # has no __module__ at all, so this must not assume a string is there.
    parts = (getattr(fn, "__module__", None) or "").split(".")
    if len(parts) >= 3:
        return parts[-2]
    return BASE_SUITE


def _make_runner(fn: TestFn, code: str) -> RunnerFn:
    """Wrap an author's function so the engine can always call ``fn(row, ctx)``.

    A test takes ``(row)`` or ``(row, ctx)``; the shape is settled once here,
    at registration, rather than inspected on every row. Any other signature is
    an authoring error and raises immediately -- a test that cannot be called is
    worth failing the import for.
    """

    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError) as exc:  # pragma: no cover - exotic callables
        raise ValueError(f"Test {code!r}: cannot inspect {fn!r}: {exc}") from exc

    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    takes_varargs = any(
        parameter.kind is parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
    required_keywords = [
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.kind is parameter.KEYWORD_ONLY and parameter.default is parameter.empty
    ]
    if required_keywords:
        raise ValueError(
            f"Test {code!r}: {fn.__name__}{signature} needs keyword argument(s) "
            f"{', '.join(required_keywords)} that the engine cannot supply. Give them "
            "defaults, or read them from the row or the context."
        )

    if takes_varargs or len(positional) == 2:
        return lambda row, ctx: fn(row, ctx)
    if len(positional) == 1:
        return lambda row, ctx: fn(row)
    raise ValueError(
        f"Test {code!r}: {fn.__name__}{signature} must take (row) or (row, ctx), "
        f"not {len(positional)} positional argument(s)."
    )


def _register(
    fn: TestFn,
    code: str,
    message: str,
    default_enabled: bool,
    description: str,
    depends_on: list[str],
    suite: str | None,
) -> TestFn:
    """Validate one test's declaration and add it to :data:`TESTS`."""

    global _TOPO_ORDER

    if not isinstance(code, str) or not code:
        raise ValueError(f"Test code must be a non-empty string, got {code!r}.")
    if not isinstance(message, str) or not message:
        raise ValueError(f"Test {code!r}: message must be the text a person sees on failure.")
    if any(t.code == code for t in TESTS):
        where = f"{fn.__module__}.{fn.__name__}" if getattr(fn, "__module__", None) else fn.__name__
        raise ValueError(
            f"Duplicate test code {code!r} (registering {where}). "
            "Codes are permanent identifiers and must be unique."
        )
    if not isinstance(depends_on, list) or not all(
        isinstance(prerequisite, str) and prerequisite for prerequisite in depends_on
    ):
        raise ValueError(
            f"Test {code!r}: depends_on must be a list of test codes, got {depends_on!r}. "
            "A bare string is a list of its characters, which is never what you meant."
        )
    if not isinstance(default_enabled, bool):
        raise ValueError(f"Test {code!r}: default_enabled must be True or False, got {default_enabled!r}.")
    if not isinstance(description, str):
        raise ValueError(f"Test {code!r}: description must be text, got {description!r}.")
    if suite is not None and (not isinstance(suite, str) or not suite):
        raise ValueError(
            f"Test {code!r}: suite must be the name of a suite, got {suite!r}. Leave it out "
            "to take the name of the directory the test lives in."
        )

    module = getattr(fn, "__module__", None)
    if module:
        _REGISTERING_MODULES.add(module)
    TESTS.append(
        Test(
            code=code,
            message=message,
            fn=_make_runner(fn, code),
            suite=suite or _infer_suite(fn),
            source_file=inspect.getsourcefile(fn) or "<unknown>",
            default_enabled=default_enabled,
            description=description,
            depends_on=list(dict.fromkeys(depends_on)),
        )
    )
    _TOPO_ORDER = None
    return fn


def register_test(
    code: str,
    message: str,
    default_enabled: bool = True,
    description: str = "",
    depends_on: list[str] | None = None,
    suite: str | None = None,
) -> Callable[[TestFn], TestFn]:
    """Decorator registering one validation function into :data:`TESTS`.

    Adding a test means adding a function to some ``test_*.py`` file and nothing
    else: there is no central list to edit. The suite and source file are
    captured automatically from where the function lives.

    The decorated function takes ``(row)`` or ``(row, ctx)`` and returns
    :data:`~validation.results.PASS`, a :class:`~validation.results.TestResult`,
    a bool, or a :class:`~validation.results.Status` value.

    Everything that can be wrong here fails at import: a duplicate code, an
    empty message, a signature the engine cannot call. ``depends_on`` is the one
    exception -- the prerequisite may live in a module not yet imported, so it is
    checked by :func:`validate_registry` once loading finishes.
    """

    def decorator(fn: TestFn) -> TestFn:
        return _register(
            fn, code, message, default_enabled, description, list(depends_on or []), suite
        )

    return decorator


class TestGroup:
    """Shared defaults for the tests in one file. Built by :func:`test_group`.

    Prerequisites declared on the group are **unconditional**: a test's own
    ``depends_on`` adds to them rather than replacing them, so "everything in
    this file waits for X" cannot be quietly undone one test at a time. A test
    that must run regardless belongs in a group without that prerequisite, or
    outside any group.
    """

    __test__ = False  # not a pytest test class, despite the name

    def __init__(
        self,
        depends_on: list[str] | None = None,
        suite: str | None = None,
        default_enabled: bool = True,
    ) -> None:
        if depends_on is not None and not isinstance(depends_on, list):
            raise ValueError(
                f"test_group depends_on must be a list of test codes, got {depends_on!r}. "
                "A bare string is a list of its characters, which is never what you meant."
            )
        self.depends_on = list(dict.fromkeys(depends_on or []))
        self.suite = suite
        self.default_enabled = default_enabled

    def __call__(
        self,
        code: str,
        message: str,
        default_enabled: bool | None = None,
        description: str = "",
        depends_on: list[str] | None = None,
        suite: str | None = None,
    ) -> Callable[[TestFn], TestFn]:
        """Register one test with this group's defaults applied."""

        if depends_on is not None and not isinstance(depends_on, list):
            raise ValueError(
                f"Test {code!r}: depends_on must be a list of test codes, got {depends_on!r}. "
                "A bare string is a list of its characters, which is never what you meant."
            )
        combined = self.depends_on + [
            prerequisite
            for prerequisite in (depends_on or [])
            if prerequisite not in self.depends_on
        ]

        def decorator(fn: TestFn) -> TestFn:
            return _register(
                fn,
                code,
                message,
                self.default_enabled if default_enabled is None else default_enabled,
                description,
                combined,
                suite or self.suite,
            )

        return decorator


def test_group(
    depends_on: list[str] | None = None,
    suite: str | None = None,
    default_enabled: bool = True,
) -> TestGroup:
    """Defaults for a file of tests: prerequisites, suite, and default state.

    Saves repeating the same ``depends_on`` on every test in a layer file. The
    group's prerequisites always apply; a test adds its own on top.
    """

    return TestGroup(depends_on=depends_on, suite=suite, default_enabled=default_enabled)


def clear_registry() -> None:
    """Drop every registered test and all loaded-suite bookkeeping.

    Exists for tests of the framework itself, which need to build small
    throwaway registries (a dependency cycle, a dangling prerequisite) without
    the example tests in the way.  Not part of normal pipeline use.
    """

    global _TOPO_ORDER
    TESTS.clear()
    _LOADED_SUITES.clear()
    _LOADED_FILES.clear()
    # Evict the test modules too: Python caches a module after its first import,
    # so without this a later load_suites() would re-import nothing and leave
    # the registry silently empty.
    for name in _REGISTERING_MODULES:
        sys.modules.pop(name, None)
    _REGISTERING_MODULES.clear()
    _TOPO_ORDER = None


def loaded_suites() -> set[str]:
    """Suites loaded so far in this process (a copy, so callers can't mutate)."""

    return set(_LOADED_SUITES)


def _import_test_modules(package_name: str) -> None:
    """Import every ``test_*.py`` module directly inside one package."""

    pkg = importlib.import_module(package_name)
    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        raise ValueError(f"{package_name!r} is a module, not a package; expected a package directory")
    for module in pkgutil.iter_modules(list(pkg_path)):
        # Singular "test_", not "tests_": one convention, checked in one place.
        if module.name.startswith("test_"):
            importlib.import_module(f"{package_name}.{module.name}")


def load_suites(suites: list[str], package: str) -> None:
    """Import the named suite subpackages so their tests register themselves.

    *package* is the package your tests live in -- your own, not this one, which
    ships no tests. It is required for that reason: a default would name this
    library, and the error for a missing suite would then point at the wrong
    tree entirely.

    Loading is explicit and per-entry-point, so several scripts can live in one
    codebase, each opting into a different subset of tests without interfering
    with each other.

    The base suite (``test_*.py`` files sitting directly in *package*) is always
    loaded, whatever was requested -- those are the tests that must run no matter
    which optional sets were chosen.  Repeat and overlapping calls are no-ops:
    each suite is imported at most once.

    Every requested suite is resolved before anything is imported, so a name that
    does not exist leaves the registry exactly as it found it. Dependency
    validation runs at the end, because a prerequisite may live in a module that
    has not been imported yet when a dependent is registered.
    """

    if importlib.util.find_spec(package) is None:
        raise ValueError(
            f"Unknown package {package!r}: it is not importable from here. "
            "package= is the package your own tests live in."
        )

    wanted = [suite for suite in suites if suite not in _LOADED_SUITES]
    for suite in wanted:
        subpackage = f"{package}.{suite}"
        try:
            found = importlib.util.find_spec(subpackage)
        except ModuleNotFoundError:
            found = None
        if found is None:
            raise ValueError(
                f"Unknown suite {suite!r}: expected a subpackage {subpackage!r} "
                f"(directory {package}/{suite}/ containing an __init__.py). "
                "Pass package= to point this at your own tests."
            )

    if BASE_SUITE not in _LOADED_SUITES:
        _import_test_modules(package)
        _LOADED_SUITES.add(BASE_SUITE)

    for suite in wanted:
        _import_test_modules(f"{package}.{suite}")
        _LOADED_SUITES.add(suite)

    validate_registry()


def loaded_files() -> list[str]:
    """Test files loaded by path so far, in load order (a copy)."""

    return list(_LOADED_FILES)


def load_test_files(paths: str | list[str]) -> None:
    """Import the named test files so their tests register themselves.

    The counterpart to :func:`load_suites` for a caller that has paths rather
    than an importable package -- a pipeline that writes test files into a run
    directory and then validates that run cannot express them as a package, and
    should not have to.

    Every file is named explicitly -- a path to a ``.py`` file, or several of
    them. Nothing is discovered, and nothing is imported that was not asked for,
    so two entry points in one codebase can run different sets of tests without
    interfering with each other.

    The files need not be a package and need no ``__init__.py``. A file listed
    twice, or already loaded, is skipped. Dependencies are validated once every
    file in the call has been loaded, so a prerequisite may live in any of them.

    A file imported this way is given a flat module name, so :func:`_infer_suite`
    places its tests in :data:`BASE_SUITE` -- the suite that is always loaded.
    """

    given = [paths] if isinstance(paths, str) else list(paths)
    resolved: list[str] = []
    for path in given:
        candidate = Path(path).resolve()
        if not candidate.is_file():
            raise ValueError(
                f"No test file at {path!r}. load_test_files() names files explicitly; "
                "nothing is discovered."
            )
        name = str(candidate)
        if name not in _LOADED_FILES and name not in resolved:
            resolved.append(name)

    for name in resolved:
        # A unique module name per load: two run directories can each hold a
        # checks.py, and importing the second under the first's name would be a
        # no-op that silently registered nothing.
        module_name = f"pandas_row_validation_test_file_{Path(name).stem}_{len(_LOADED_FILES)}"
        spec = importlib.util.spec_from_file_location(module_name, name)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot import {name!r} as a Python file.")
        module = importlib.util.module_from_spec(spec)
        # Registered before execution so a test file that imports itself, or is
        # pickled by a worker, finds the module rather than importing it twice.
        sys.modules[module_name] = module
        # No __pycache__ beside the caller's file. A test file loaded by path
        # comes from a data directory -- a prepared run's inputs, say -- which is
        # a record of what was read, not somewhere to write to; and the module
        # name is unique per load, so a cached .pyc would never be reused anyway.
        writing_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        finally:
            sys.dont_write_bytecode = writing_bytecode
        _REGISTERING_MODULES.add(module_name)
        _LOADED_FILES.append(name)

    # The base suite is where a path-imported file's tests land, and
    # validate_registry() names the loaded suites when a prerequisite is missing.
    if resolved:
        _LOADED_SUITES.add(BASE_SUITE)
    validate_registry()


def _topological_order() -> list[Test]:
    """Order tests so every prerequisite precedes its dependents.

    Depth-first search with a visiting set, which detects cycles as a side
    effect -- so ordering and cycle detection share one traversal.
    """

    by_code = {t.code: t for t in TESTS}
    order: list[Test] = []
    done: set[str] = set()
    visiting: list[str] = []
    visiting_set: set[str] = set()

    def visit(code: str) -> None:
        if code in done:
            return
        if code in visiting_set:
            cycle = visiting[visiting.index(code):] + [code]
            raise ValueError("Dependency cycle among tests: " + " -> ".join(cycle))
        visiting.append(code)
        visiting_set.add(code)
        for prerequisite in by_code[code].depends_on:
            visit(prerequisite)
        visiting.pop()
        visiting_set.discard(code)
        done.add(code)
        order.append(by_code[code])

    for test in TESTS:
        visit(test.code)
    return order


def validate_registry() -> None:
    """Check every ``depends_on`` edge and cache the evaluation order.

    A prerequisite code that is not registered raises -- including the case where
    it merely belongs to a suite this entry point did not load.  That is
    deliberately as loud as a typo: silently skipping a dependent test because
    its prerequisite's suite is absent would change which tests run based on an
    unrelated argument, with no diagnostic.

    Also computes every test's :attr:`Test.layer` and caches the evaluation
    order, so neither is recomputed inside the per-row loop.
    """

    global _TOPO_ORDER
    known = {t.code for t in TESTS}
    for test in TESTS:
        for prerequisite in test.depends_on:
            if prerequisite not in known:
                raise ValueError(
                    f"Test {test.code!r} depends on {prerequisite!r}, which is not registered. "
                    "Either the code is a typo, or it belongs to a suite that was not loaded "
                    f"(currently loaded: {sorted(_LOADED_SUITES)})."
                )
    order = _topological_order()
    by_code = {t.code: t for t in TESTS}
    for test in order:
        test.layer = (
            0 if not test.depends_on
            else 1 + max(by_code[code].layer for code in test.depends_on)
        )
    _TOPO_ORDER = order


def _get_topo_order() -> list[Test]:
    """Return the cached evaluation order, computing it if the registry changed."""

    if _TOPO_ORDER is None:
        validate_registry()
    order = _TOPO_ORDER
    if order is None:  # pragma: no cover - validate_registry always sets it
        raise RuntimeError("evaluation order was not computed")
    return order


# --------------------------------------------------------------------------
# Loading override rules, and applying them
# --------------------------------------------------------------------------


def _known_codes() -> set[str]:
    """The codes a rule file may name: everything registered right now."""

    return {test.code for test in TESTS}


def load_overrides(path: str) -> list[OverrideRule]:
    """Load override rules from a single YAML file.

    Load the suites first: a rule naming a code that is not registered is an
    error, since it would otherwise sit in the file doing nothing.
    """

    return rules.load_overrides(path, _known_codes())


def load_overrides_from_dir(directory: str, pattern: str = "*.yaml") -> list[OverrideRule]:
    """Load every matching file in one directory, sorted alphabetically.

    Alphabetical order is the load order, and load order decides "last rule
    wins", so filenames carry precedence: name files ``01_x.yaml``,
    ``02_y.yaml`` when the ordering between them matters.
    """

    return rules.load_overrides_from_dir(directory, _known_codes(), pattern=pattern)


def load_overrides_from_files(paths: list[str]) -> list[OverrideRule]:
    """Load an explicit list of files, which need not share a directory.

    Precedence follows the order given, not alphabetical or filesystem order.
    """

    return rules.load_overrides_from_files(paths, _known_codes())


def resolve_enabled_state(row: "pd.Series[Any]", overrides: list[OverrideRule]) -> dict[str, bool]:
    """Effective on/off state of every registered code, for one row.

    Starts from each test's ``default_enabled`` and applies every matching rule
    in list order, so the last matching rule wins.  That precedence is
    positional only -- there is no priority field -- which is why the order
    files are loaded in is documented at each loader.
    """

    return {code: enabled for code, (enabled, _) in _resolve_state(row, overrides).items()}


def _resolve_state(
    row: "pd.Series[Any]", overrides: list[OverrideRule]
) -> dict[str, tuple[bool, str]]:
    """Per-row on/off state plus the reason for it, for explanations."""

    state = {
        t.code: (t.default_enabled, "default" if t.default_enabled else "off by default")
        for t in TESTS
    }
    for rule in overrides:
        if not rule_matches(rule, row):
            continue
        enabled = rule.action == "enable"
        for code in rule.codes:
            if code in state:
                state[code] = (enabled, f"rule {rule.name!r}")
    return state


def explain_row(
    row: "pd.Series[Any]",
    ctx: RowContext | None = None,
    overrides: list[OverrideRule] | None = None,
    on_error: str = "record",
) -> list[TestOutcome]:
    """Run the tests against one row and report what *every* test did.

    This is the root-cause tool, and the single implementation of the per-row
    algorithm -- :func:`validate_row` is a filter over it. Outcomes come back in
    evaluation order, so the first failure is the most fundamental one: a test
    can only fail after all its prerequisites passed.

    Outcomes are ``passed``; ``failed``; ``errored`` (the test raised);
    ``disabled`` (off for this row, with the rule that decided it in ``detail``);
    ``skipped`` (a prerequisite did not pass, with every blocking code in
    ``detail``). Prerequisites are all-or-nothing: a test runs only when every
    code in its ``depends_on`` passed on this row.

    "Did not pass" deliberately covers a prerequisite that was *disabled* or
    *errored* as well as one that failed. A test that never ran confirmed
    nothing about the row, so it must not silently unlock a dependent.

    ``on_error="record"`` turns an exception raised inside a test into a
    :data:`Status.ERROR` outcome and carries on with the row; ``"raise"`` lets it
    propagate, for a run that should stop at the first broken test. A test
    returning something that is not a result at all always raises, whatever this
    is set to: that is an authoring bug, not a data problem.

    Raises ``ValueError`` when the row has duplicate column labels, before
    running anything: ``row[column]`` would then hand a test a Series instead of
    a value.
    """

    if on_error not in ("record", "raise"):
        raise ValueError(f"on_error must be 'record' or 'raise', got {on_error!r}.")
    if row.index.has_duplicates:
        duplicated = sorted({str(label) for label in row.index[row.index.duplicated()]})
        raise ValueError(
            f"Row has duplicate column labels {duplicated}: a test reading one of them "
            "would be handed a Series instead of a value. Rename or drop the duplicate "
            "columns before validating."
        )

    state = _resolve_state(row, overrides or [])
    passed: dict[str, bool] = {}
    outcomes: list[TestOutcome] = []

    for test in _get_topo_order():
        enabled, reason = state.get(test.code, (test.default_enabled, "default"))
        if not enabled:
            passed[test.code] = False
            outcomes.append(
                TestOutcome(test.code, DISABLED, layer=test.layer, suite=test.suite,
                            detail=f"disabled by {reason}")
            )
            continue

        blocking = [code for code in test.depends_on if not passed.get(code, False)]
        if blocking:
            passed[test.code] = False
            outcomes.append(
                TestOutcome(test.code, SKIPPED, layer=test.layer, suite=test.suite,
                            detail="prerequisite did not pass: " + ", ".join(blocking))
            )
            continue

        try:
            returned = test.fn(row, ctx)
        except Exception as exc:
            if on_error == "raise":
                raise
            passed[test.code] = False
            outcomes.append(
                TestOutcome(
                    test.code, ERRORED, status=Status.ERROR, layer=test.layer,
                    suite=test.suite, message=test.message,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        result = normalise_result(returned, test.code)
        passed[test.code] = result.passed
        outcomes.append(
            TestOutcome(
                test.code,
                PASSED if result.passed else FAILED,
                status=result.code,
                layer=test.layer,
                suite=test.suite,
                message="" if result.passed else test.message,
                comments=result.comments,
            )
        )
    return outcomes


def validate_row(
    row: "pd.Series[Any]",
    ctx: RowContext | None = None,
    overrides: list[OverrideRule] | None = None,
    on_error: str = "record",
) -> list[TestOutcome]:
    """Run every enabled test against one row and return the failures.

    The failures come back in evaluation order, so the first is the most
    fundamental: ``results[0]`` is the row's root cause. Tests that were disabled
    or blocked by a failed prerequisite are absent entirely -- neither a pass nor
    a failure -- which is what keeps one broken field from producing a page of
    cascading errors. Use :func:`explain_row` to see them.

    Does not mutate ``row`` or ``ctx``.
    """

    return [
        outcome
        for outcome in explain_row(row, ctx=ctx, overrides=overrides, on_error=on_error)
        if outcome.failed
    ]


def root_cause(outcomes: list[TestOutcome]) -> str | None:
    """The code of the most fundamental failure in a row's results.

    The shallowest failure -- the one at the lowest layer -- with evaluation order
    breaking a tie. ``None`` for a row that passed. Accepts either
    :func:`validate_row` or :func:`explain_row` output.

    Every failure a row reports is already the root of its own chain, since a
    test only runs once its prerequisites passed. When a row fails in two chains
    that do not touch -- a missing email and a malformed age -- neither is
    upstream of the other, and this returns the shallower of them rather than
    whichever the evaluation order happened to reach first. Registration order
    should not decide what a person reads as the cause.
    """

    failures = [outcome for outcome in outcomes if outcome.failed]
    if not failures:
        return None
    return min(failures, key=lambda outcome: outcome.layer).code


# --------------------------------------------------------------------------
# Table rendering
# --------------------------------------------------------------------------


def _rules_for_code(code: str, overrides: list[OverrideRule]) -> list[OverrideRule]:
    """Rules that reference *code*, in load order."""

    return [r for r in overrides if code in r.codes]


def _render_match(rule: OverrideRule) -> str:
    """Compact one-cell rendering of a rule's match criteria."""

    if rule.match_all:
        return "all"
    return "; ".join(f"{c.column}~=/{c.pattern}/" for c in rule.criteria)


def check_rule_columns(df: pd.DataFrame, overrides: list[OverrideRule]) -> list[str]:
    """Warn about columns an override rule matches on that the data lacks.

    A criterion naming a column that is not there never matches, so the rule
    silently never applies -- the one rule mistake nothing else catches, since
    the loader validates codes and patterns but has no data to compare against.

    Returns one human-readable line per problem, empty when every criterion
    column is present. It warns rather than raises: a rule file may deliberately
    cover several data shapes, only some of which carry the column.

    Tests are not checked here. They read the row themselves, so a missing field
    raises from the test and is recorded as a :data:`Status.ERROR` outcome
    naming the column, rather than passing silently.
    """

    present = set(df.columns)
    warnings: list[str] = []
    for rule in overrides:
        for criterion in rule.criteria:
            if criterion.column not in present:
                warnings.append(
                    f"rule {rule.name!r} matches on column {criterion.column!r}, which is not "
                    "in the data: the rule will never apply"
                )
    return warnings


def get_registry_table(debug: int = 0) -> pd.DataFrame:
    """One row per registered test.

    ``layer`` and ``depends_on`` are base columns, not debug-gated: what a test
    requires, and how deep it sits in the dependency graph, change whether it
    runs at all. Rows are ordered suite, then layer, then code, so the
    fundamental tests of each suite read first. ``source_file`` is genuinely
    only useful when debugging, so it appears at ``debug >= 2``.
    """

    columns = ["code", "layer", "suite", "default_state", "description", "depends_on"]
    if debug >= 2:
        columns.append("source_file")

    rows: list[dict[str, Any]] = []
    for test in TESTS:
        row: dict[str, Any] = {
            "code": test.code,
            "layer": test.layer,
            "suite": test.suite,
            "default_state": "ON" if test.default_enabled else "OFF",
            "description": test.description,
            "depends_on": "; ".join(test.depends_on) if test.depends_on else "-",
        }
        if debug >= 2:
            row["source_file"] = test.source_file
        rows.append(row)

    # Columns are passed explicitly so an empty registry still yields a frame
    # with columns to sort by; pd.DataFrame([]) has none and sort_values raises.
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["suite", "layer", "code"])
        .reset_index(drop=True)
    )


def print_registry(overrides: list[OverrideRule] | None = None, debug: int = 0) -> pd.DataFrame:
    """Print the registry table and return the frame behind it.

    At ``debug >= 1`` a ``could_be_overridden_by`` column lists the rules that
    *reference* each code.  It deliberately is not called "was overridden by":
    whether a rule actually fires depends on the row it is matched against, and
    this table has no row.  Only :func:`resolve_enabled_state` can answer that.
    """

    table = get_registry_table(debug=debug)
    if table.empty:
        print("No tests registered.")
        return table

    if debug >= 1:
        rules = overrides or []
        table["could_be_overridden_by"] = [
            "; ".join(r.name for r in _rules_for_code(code, rules)) or "-" for code in table["code"]
        ]

    print(format_table(table, wrap_columns={"description": 40, "could_be_overridden_by": 30}))
    return table


def print_registry_with_overrides(overrides: list[OverrideRule], debug: int = 0) -> pd.DataFrame:
    """Print the registry cross-referenced against the loaded override rules.

    ``effective_state`` states a plain "DEFAULT (ON/OFF)" for any code no rule
    references, so a reader never has to infer that from an empty cell.  When
    rules do reference a code the honest answer is row-dependent, and the cell
    says so rather than inventing one.
    """

    base = get_registry_table(debug=debug)
    if base.empty:
        print("No tests registered.")
        return base

    columns = ["code", "layer", "suite", "default_state", "override_rules", "effective_state"]
    if debug >= 2:
        columns.append("source_file")

    rows: list[dict[str, Any]] = []
    for _, entry in base.iterrows():
        code = str(entry["code"])
        matching = _rules_for_code(code, overrides)
        default_state = str(entry["default_state"])
        if matching:
            effective = f"depends on row (default {default_state} unless a rule above matches)"
        else:
            effective = f"DEFAULT ({default_state})"
        row: dict[str, Any] = {
            "code": code,
            "layer": entry["layer"],
            "suite": entry["suite"],
            "default_state": default_state,
            "override_rules": "; ".join(f"{r.name} ({r.action})" for r in matching) or "-",
            "effective_state": effective,
        }
        if debug >= 2:
            row["source_file"] = entry["source_file"]
        rows.append(row)

    table = pd.DataFrame(rows, columns=columns)
    print(format_table(table, wrap_columns={"override_rules": 34, "effective_state": 34}))
    return table


def print_override_rules(overrides: list[OverrideRule], debug: int = 0) -> pd.DataFrame:
    """Print one row per override rule (rather than per code).

    ``codes_hit_count`` is a count, not the code list, so a rule touching many
    codes does not blow the table apart; :func:`list_rule_codes` gives the
    detail when it is wanted.
    """

    columns = ["name", "action", "codes_hit_count", "match"]
    if debug >= 2:
        columns.append("source_file")

    rows: list[dict[str, Any]] = []
    for rule in overrides:
        row: dict[str, Any] = {
            "name": rule.name,
            "action": rule.action,
            "codes_hit_count": len(rule.codes),
            "match": _render_match(rule),
        }
        if debug >= 2:
            row["source_file"] = rule.source_file
        rows.append(row)

    table = pd.DataFrame(rows, columns=columns)
    if table.empty:
        print("No override rules loaded.")
        return table
    print(format_table(table, wrap_columns={"match": 44}))
    return table


def list_rule_codes(rule_name: str, overrides: list[OverrideRule]) -> list[str]:
    """Print and return the exact codes one named rule touches."""

    for rule in overrides:
        if rule.name == rule_name:
            print(f"{rule.name} ({rule.action}) -> " + ", ".join(rule.codes))
            return list(rule.codes)
    known = ", ".join(r.name for r in overrides) or "(none loaded)"
    raise ValueError(f"No override rule named {rule_name!r}. Loaded rules: {known}")
