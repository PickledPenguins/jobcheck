"""The registry: what checks exist, how they depend on each other, and loading.

Registration, suite and file discovery, dependency validation, ordering and
layers -- everything about the *set* of checks, and nothing about running them.
:mod:`jobcheck.engine` evaluates a row against this registry,
:mod:`jobcheck.registry_tables` displays it, the override rule format lives in
:mod:`jobcheck.rules`, the value types a check returns in
:mod:`jobcheck.results`, per-row metadata in :mod:`jobcheck.context`, and
reporting in :mod:`jobcheck.report`.

The three ``load_overrides*`` functions here are thin wrappers over the parser in
:mod:`jobcheck.rules`: they supply the codes that exist, which is the only
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
    CheckOutcome,
    normalise_result,
)
from .tables import format_table

# Checks placed directly in the top-level package (not in a suite subpackage)
# belong to this suite and are loaded by every load_suites() call.
BASE_SUITE = "base"

# What an author writes: (row) or (row, ctx), returning PASS, a CheckResult, a
# bool, or a Status value. The engine stores the normalised two-argument form.
CheckFn = Callable[..., Any]
RunnerFn = Callable[["pd.Series[Any]", RowContext | None], Any]


@dataclass
class Check:
    """One named validation rule.

    ``code`` is a permanent identifier.  It is never renumbered and never
    reused, even after the check it named is deleted: override YAML files
    written by non-developers, saved reports and downstream tooling all refer
    to codes, so a reused code silently changes the meaning of existing data.

    A check reads whatever columns it needs from the row itself, so there is no
    ``column`` field: these rules are row-scoped, and many of them weigh several
    columns together.
    """

    __test__ = False  # not a pytest check class, despite the name

    code: str
    message: str
    fn: RunnerFn
    suite: str
    source_file: str
    default_enabled: bool = True
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    layer: int = 0
    """How deep in the dependency graph this check sits: 0 with no prerequisites,
    otherwise one more than its deepest prerequisite. Computed by
    :func:`validate_registry`, never set by hand. A low layer means a
    fundamental check, which is what makes it a root cause."""


CHECKS: list[Check] = []

_LOADED_SUITES: set[str] = set()
# Check files imported by path through load_checks(), resolved and in load
# order. Kept separate from _LOADED_SUITES because a file has no suite of its
# own: it lands in BASE_SUITE, and only the path identifies it again.
_LOADED_FILES: list[str] = []
# Modules that have registered a check, so clear_registry can evict them from
# sys.modules; without that a later import is a no-op -- Python caches modules --
# and the registry would silently stay empty. Recorded at registration rather
# than at import, so a module pulled in by any route is still tracked.
_REGISTERING_MODULES: set[str] = set()
# Cached topological order over depends_on edges.  The graph only changes when
# the registry changes, so it is computed once per registry state and never
# inside the per-row loop.
_TOPO_ORDER: list[Check] | None = None


def _infer_suite(fn: CheckFn) -> str:
    """Derive a check's suite from the module that defines it.

    ``jobcheck.hard_checks.test_age`` -> ``hard_checks``; a module sitting
    directly in the package (``jobcheck.test_row_shape``) or defined outside
    any package (a script, a notebook) -> :data:`BASE_SUITE`. Never passed by
    hand, so a check file cannot drift out of sync with where it lives.
    """

    # A function defined by exec() -- a notebook cell, a REPL, a doc example --
    # has no __module__ at all, so this must not assume a string is there.
    parts = (getattr(fn, "__module__", None) or "").split(".")
    if len(parts) >= 3:
        return parts[-2]
    return BASE_SUITE


def _make_runner(fn: CheckFn, code: str) -> RunnerFn:
    """Wrap an author's function so the engine can always call ``fn(row, ctx)``.

    A check takes ``(row)`` or ``(row, ctx)``; the shape is settled once here,
    at registration, rather than inspected on every row. Any other signature is
    an authoring error and raises immediately -- a check that cannot be called is
    worth failing the import for.
    """

    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError) as exc:  # pragma: no cover - exotic callables
        raise ValueError(f"Check {code!r}: cannot inspect {fn!r}: {exc}") from exc

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
            f"Check {code!r}: {fn.__name__}{signature} needs keyword argument(s) "
            f"{', '.join(required_keywords)} that the engine cannot supply. Give them "
            "defaults, or read them from the row or the context."
        )

    if takes_varargs or len(positional) == 2:
        return lambda row, ctx: fn(row, ctx)
    if len(positional) == 1:
        return lambda row, ctx: fn(row)
    raise ValueError(
        f"Check {code!r}: {fn.__name__}{signature} must take (row) or (row, ctx), "
        f"not {len(positional)} positional argument(s)."
    )


def _register(
    fn: CheckFn,
    code: str,
    message: str,
    default_enabled: bool,
    description: str,
    depends_on: list[str],
    suite: str | None,
) -> CheckFn:
    """Validate one check's declaration and add it to :data:`CHECKS`."""

    global _TOPO_ORDER

    if not isinstance(code, str) or not code:
        raise ValueError(f"Check code must be a non-empty string, got {code!r}.")
    if not isinstance(message, str) or not message:
        raise ValueError(f"Check {code!r}: message must be the text a person sees on failure.")
    if any(t.code == code for t in CHECKS):
        where = f"{fn.__module__}.{fn.__name__}" if getattr(fn, "__module__", None) else fn.__name__
        raise ValueError(
            f"Duplicate check code {code!r} (registering {where}). "
            "Codes are permanent identifiers and must be unique."
        )
    if not isinstance(depends_on, list) or not all(
        isinstance(prerequisite, str) and prerequisite for prerequisite in depends_on
    ):
        raise ValueError(
            f"Check {code!r}: depends_on must be a list of check codes, got {depends_on!r}. "
            "A bare string is a list of its characters, which is never what you meant."
        )
    if not isinstance(default_enabled, bool):
        raise ValueError(f"Check {code!r}: default_enabled must be True or False, got {default_enabled!r}.")
    if not isinstance(description, str):
        raise ValueError(f"Check {code!r}: description must be text, got {description!r}.")
    if suite is not None and (not isinstance(suite, str) or not suite):
        raise ValueError(
            f"Check {code!r}: suite must be the name of a suite, got {suite!r}. Leave it out "
            "to take the name of the directory the check lives in."
        )

    module = getattr(fn, "__module__", None)
    if module:
        _REGISTERING_MODULES.add(module)
    CHECKS.append(
        Check(
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


def register_check(
    code: str,
    message: str,
    default_enabled: bool = True,
    description: str = "",
    depends_on: list[str] | None = None,
    suite: str | None = None,
) -> Callable[[CheckFn], CheckFn]:
    """Decorator registering one validation function into :data:`CHECKS`.

    Adding a check means adding a function to some ``check_*.py`` file and nothing
    else: there is no central list to edit. The suite and source file are
    captured automatically from where the function lives.

    The decorated function takes ``(row)`` or ``(row, ctx)`` and returns
    :data:`~validation.results.PASS`, a :class:`~validation.results.CheckResult`,
    a bool, or a :class:`~validation.results.Status` value.

    Everything that can be wrong here fails at import: a duplicate code, an
    empty message, a signature the engine cannot call. ``depends_on`` is the one
    exception -- the prerequisite may live in a module not yet imported, so it is
    checked by :func:`validate_registry` once loading finishes.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        # depends_on is passed through unchanged: list("CODE") would turn a
        # mistyped bare string into its characters before _register could reject
        # it, and the prerequisite check downstream would then complain about a
        # check called 'C'. _register copies the list once it is known to be one.
        return _register(
            fn, code, message, default_enabled, description,
            [] if depends_on is None else depends_on, suite
        )

    return decorator


class CheckGroup:
    """Shared defaults for the checks in one file. Built by :func:`check_group`.

    Prerequisites declared on the group are **unconditional**: a check's own
    ``depends_on`` adds to them rather than replacing them, so "everything in
    this file waits for X" cannot be quietly undone one check at a time. A check
    that must run regardless belongs in a group without that prerequisite, or
    outside any group.
    """

    __test__ = False  # not a pytest check class, despite the name

    def __init__(
        self,
        depends_on: list[str] | None = None,
        suite: str | None = None,
        default_enabled: bool = True,
    ) -> None:
        if depends_on is not None and not isinstance(depends_on, list):
            raise ValueError(
                f"check_group depends_on must be a list of check codes, got {depends_on!r}. "
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
    ) -> Callable[[CheckFn], CheckFn]:
        """Register one check with this group's defaults applied."""

        if depends_on is not None and not isinstance(depends_on, list):
            raise ValueError(
                f"Check {code!r}: depends_on must be a list of check codes, got {depends_on!r}. "
                "A bare string is a list of its characters, which is never what you meant."
            )
        combined = self.depends_on + [
            prerequisite
            for prerequisite in (depends_on or [])
            if prerequisite not in self.depends_on
        ]

        def decorator(fn: CheckFn) -> CheckFn:
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


def check_group(
    depends_on: list[str] | None = None,
    suite: str | None = None,
    default_enabled: bool = True,
) -> CheckGroup:
    """Defaults for a file of checks: prerequisites, suite, and default state.

    Saves repeating the same ``depends_on`` on every check in a layer file. The
    group's prerequisites always apply; a check adds its own on top.
    """

    return CheckGroup(depends_on=depends_on, suite=suite, default_enabled=default_enabled)


def clear_registry() -> None:
    """Drop every registered check and all loaded-suite bookkeeping.

    Exists for checks of the framework itself, which need to build small
    throwaway registries (a dependency cycle, a dangling prerequisite) without
    the example checks in the way.  Not part of normal pipeline use.
    """

    global _TOPO_ORDER
    CHECKS.clear()
    _LOADED_SUITES.clear()
    _LOADED_FILES.clear()
    # Evict the check modules too: Python caches a module after its first import,
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
    """Import every ``check_*.py`` module directly inside one package."""

    pkg = importlib.import_module(package_name)
    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        raise ValueError(f"{package_name!r} is a module, not a package; expected a package directory")
    for module in pkgutil.iter_modules(list(pkg_path)):
        # "check_", not "test_": a file named test_*.py inside a user's package
        # is collected by pytest, which then imports it a second time under its
        # own rules and reports the registry's duplicate-code guard as a test
        # failure. One convention, checked in one place.
        if module.name.startswith("check_"):
            importlib.import_module(f"{package_name}.{module.name}")


def load_suites(suites: list[str], package: str) -> None:
    """Import the named suite subpackages so their checks register themselves.

    *package* is the package your checks live in -- your own, not this one, which
    ships no checks. It is required for that reason: a default would name this
    library, and the error for a missing suite would then point at the wrong
    tree entirely.

    Loading is explicit and per-entry-point, so several scripts can live in one
    codebase, each opting into a different subset of checks without interfering
    with each other.

    The base suite (``check_*.py`` files sitting directly in *package*) is always
    loaded, whatever was requested -- those are the checks that must run no matter
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
            "package= is the package your own checks live in."
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
                "Pass package= to point this at your own checks."
            )

    if BASE_SUITE not in _LOADED_SUITES:
        _import_test_modules(package)
        _LOADED_SUITES.add(BASE_SUITE)

    for suite in wanted:
        _import_test_modules(f"{package}.{suite}")
        _LOADED_SUITES.add(suite)

    validate_registry()


def loaded_files() -> list[str]:
    """Check files loaded by path so far, in load order (a copy)."""

    return list(_LOADED_FILES)


def load_checks(paths: str | list[str]) -> None:
    """Import the named check files so their checks register themselves.

    The counterpart to :func:`load_suites` for a caller that has paths rather
    than an importable package -- a pipeline that writes check files into a run
    directory and then validates that run cannot express them as a package, and
    should not have to.

    Every file is named explicitly -- a path to a ``.py`` file, or several of
    them. Nothing is discovered, and nothing is imported that was not asked for,
    so two entry points in one codebase can run different sets of checks without
    interfering with each other.

    The files need not be a package and need no ``__init__.py``. A file listed
    twice, or already loaded, is skipped. Dependencies are validated once every
    file in the call has been loaded, so a prerequisite may live in any of them.

    A file imported this way is given a flat module name, so :func:`_infer_suite`
    places its checks in :data:`BASE_SUITE` -- the suite that is always loaded.
    """

    given = [paths] if isinstance(paths, str) else list(paths)
    resolved: list[str] = []
    for path in given:
        candidate = Path(path).resolve()
        if not candidate.is_file():
            raise ValueError(
                f"No check file at {path!r}. load_checks() names files explicitly; "
                "nothing is discovered."
            )
        name = str(candidate)
        if name not in _LOADED_FILES and name not in resolved:
            resolved.append(name)

    for name in resolved:
        # A unique module name per load: two run directories can each hold a
        # checks.py, and importing the second under the first's name would be a
        # no-op that silently registered nothing.
        module_name = f"jobcheck_test_file_{Path(name).stem}_{len(_LOADED_FILES)}"
        spec = importlib.util.spec_from_file_location(module_name, name)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot import {name!r} as a Python file.")
        module = importlib.util.module_from_spec(spec)
        # Registered before execution so a check file that imports itself, or is
        # pickled by a worker, finds the module rather than importing it twice.
        sys.modules[module_name] = module
        # No __pycache__ beside the caller's file. A check file loaded by path
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

    # The base suite is where a path-imported file's checks land, and
    # validate_registry() names the loaded suites when a prerequisite is missing.
    if resolved:
        _LOADED_SUITES.add(BASE_SUITE)
    validate_registry()


def _topological_order() -> list[Check]:
    """Order checks so every prerequisite precedes its dependents.

    Depth-first search with a visiting set, which detects cycles as a side
    effect -- so ordering and cycle detection share one traversal.
    """

    by_code = {t.code: t for t in CHECKS}
    order: list[Check] = []
    done: set[str] = set()
    visiting: list[str] = []
    visiting_set: set[str] = set()

    def visit(code: str) -> None:
        if code in done:
            return
        if code in visiting_set:
            cycle = visiting[visiting.index(code):] + [code]
            raise ValueError("Dependency cycle among checks: " + " -> ".join(cycle))
        visiting.append(code)
        visiting_set.add(code)
        for prerequisite in by_code[code].depends_on:
            visit(prerequisite)
        visiting.pop()
        visiting_set.discard(code)
        done.add(code)
        order.append(by_code[code])

    for check in CHECKS:
        visit(check.code)
    return order


def validate_registry() -> None:
    """Check every ``depends_on`` edge and cache the evaluation order.

    A prerequisite code that is not registered raises -- including the case where
    it merely belongs to a suite this entry point did not load.  That is
    deliberately as loud as a typo: silently skipping a dependent check because
    its prerequisite's suite is absent would change which checks run based on an
    unrelated argument, with no diagnostic.

    Also computes every check's :attr:`Check.layer` and caches the evaluation
    order, so neither is recomputed inside the per-row loop.
    """

    global _TOPO_ORDER
    known = {t.code for t in CHECKS}
    for check in CHECKS:
        for prerequisite in check.depends_on:
            if prerequisite not in known:
                raise ValueError(
                    f"Check {check.code!r} depends on {prerequisite!r}, which is not registered. "
                    "Either the code is a typo, or it belongs to a suite that was not loaded "
                    f"(currently loaded: {sorted(_LOADED_SUITES)})."
                )
    order = _topological_order()
    by_code = {t.code: t for t in CHECKS}
    for check in order:
        check.layer = (
            0 if not check.depends_on
            else 1 + max(by_code[code].layer for code in check.depends_on)
        )
    _TOPO_ORDER = order


def _get_topo_order() -> list[Check]:
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

    return {check.code for check in CHECKS}


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
