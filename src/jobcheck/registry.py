"""The registry: what checks exist, how they depend on each other, and loading.

Registration, file loading, dependency validation, ordering and layers --
everything about the *set* of checks, and nothing about running them.
:mod:`jobcheck.engine` evaluates a row against this registry,
:mod:`jobcheck.registry_tables` displays it, the override rule format lives in
:mod:`jobcheck.rules`, the value types a check returns in
:mod:`jobcheck.results`, per-row metadata in :mod:`jobcheck.context`, and
reporting in :mod:`jobcheck.report`.

:func:`load_overrides` here is a thin wrapper over the parser in
:mod:`jobcheck.rules`: it supplies the codes that exist, which is the only
thing that module needs from this one.
"""

from __future__ import annotations

import importlib.util
import inspect
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
from .rules import MatchCriterion, OverrideRule

# What an author writes: (row) or (row, context), returning PASS or a
# CheckResult. The engine stores the normalized two-argument form.
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
    source_file: str
    default_enabled: bool = True
    depends_on: list[str] = field(default_factory=list)
    layer: int = 0
    """How deep in the dependency graph this check sits: 0 with no prerequisites,
    otherwise one more than its deepest prerequisite. Computed by
    :func:`validate_registry`, never set by hand. A low layer means a
    fundamental check, which is what makes it a root cause."""


CHECKS: list[Check] = []

# Check files imported by path through load_checks(), resolved and in load
# order.
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


def _make_runner(fn: CheckFn, code: str) -> RunnerFn:
    """Wrap an author's function so the engine can always call ``fn(row, context)``.

    A check takes ``(row)`` or ``(row, context)``; the shape is settled once here,
    at registration, rather than inspected on every row. Any other signature is
    an authoring error and raises immediately -- a check that cannot be called is
    worth failing the import for.
    """

    signature = inspect.signature(fn)
    parameters = list(signature.parameters.values())
    positional = [p for p in parameters
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    needed = [p.name for p in parameters
              if p.kind is p.KEYWORD_ONLY and p.default is p.empty]
    if needed:
        raise ValueError(
            f"Check {code!r}: {fn.__name__}{signature} needs keyword argument(s) "
            f"{', '.join(needed)} that the engine cannot supply. Give them defaults, "
            "or read them from the row or the context."
        )
    if any(p.kind is p.VAR_POSITIONAL for p in parameters) or len(positional) == 2:
        return lambda row, ctx: fn(row, ctx)
    if len(positional) == 1:
        return lambda row, ctx: fn(row)
    raise ValueError(
        f"Check {code!r}: {fn.__name__}{signature} must take (row) or (row, context), "
        f"not {len(positional)} positional argument(s)."
    )


def register_check(
    code: str,
    message: str,
    default_enabled: bool = True,
    depends_on: list[str] | None = None,
) -> Callable[[CheckFn], CheckFn]:
    """Decorator registering one validation function into :data:`CHECKS`.

    Adding a check means adding a function to some ``check_*.py`` file and nothing
    else: there is no central list to edit. The source file is captured
    automatically from where the function lives.

    The decorated function takes ``(row)`` or ``(row, context)`` and returns
    :data:`~jobcheck.results.PASS` or a :class:`~jobcheck.results.CheckResult`
    -- ``CheckResult(condition)`` wraps a bare comparison.

    Everything that can be wrong here fails at import: a duplicate code, an
    empty message, a signature the engine cannot call. ``depends_on`` is the one
    exception -- the prerequisite may live in a module not yet imported, so it is
    checked by :func:`validate_registry` once loading finishes.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        global _TOPO_ORDER

        # depends_on is inspected before it is copied: list("CODE") would turn a
        # mistyped bare string into its characters, and the prerequisite check
        # downstream would then complain about a check called 'C'.
        prerequisites = [] if depends_on is None else depends_on
        if not isinstance(code, str) or not code:
            raise ValueError(f"Check code must be a non-empty string, got {code!r}.")
        if not isinstance(message, str) or not message:
            raise ValueError(f"Check {code!r}: message must be the text a person sees on failure.")
        if any(check.code == code for check in CHECKS):
            where = f"{fn.__module__}.{fn.__name__}" if getattr(fn, "__module__", None) else fn.__name__
            raise ValueError(
                f"Duplicate check code {code!r} (registering {where}). "
                "Codes are permanent identifiers and must be unique."
            )
        if not isinstance(prerequisites, list) or not all(
            isinstance(prerequisite, str) and prerequisite for prerequisite in prerequisites
        ):
            raise ValueError(
                f"Check {code!r}: depends_on must be a list of check codes, got {prerequisites!r}. "
                "A bare string is a list of its characters, which is never what you meant."
            )
        if not isinstance(default_enabled, bool):
            raise ValueError(
                f"Check {code!r}: default_enabled must be True or False, got {default_enabled!r}.")

        module = getattr(fn, "__module__", None)
        if module:
            _REGISTERING_MODULES.add(module)
        CHECKS.append(
            Check(
                code=code,
                message=message,
                fn=_make_runner(fn, code),
                source_file=inspect.getsourcefile(fn) or "<unknown>",
                default_enabled=default_enabled,
                depends_on=list(dict.fromkeys(prerequisites)),
            )
        )
        _TOPO_ORDER = None
        return fn

    return decorator


def clear_registry() -> None:
    """Drop every registered check and all loaded-file bookkeeping.

    Exists for checks of the framework itself, which need to build small
    throwaway registries (a dependency cycle, a dangling prerequisite) without
    the example checks in the way, and for a process that validates several
    runs in turn.
    """

    global _TOPO_ORDER
    CHECKS.clear()
    _LOADED_FILES.clear()
    # Evict the check modules too: Python caches a module after its first import,
    # so without this a later load_checks() would re-import nothing and leave
    # the registry silently empty.
    for name in _REGISTERING_MODULES:
        sys.modules.pop(name, None)
    _REGISTERING_MODULES.clear()
    _TOPO_ORDER = None


def loaded_check_files() -> list[str]:
    """Check files loaded so far, in load order (a copy)."""

    return list(_LOADED_FILES)


def load_checks(paths: list[str]) -> None:
    """Import the named check files so their checks register themselves.

    Every file is named explicitly, as a list of paths to ``.py`` files.
    Nothing is discovered, and nothing is imported that was not asked for,
    so two entry points in one codebase can run different sets of checks without
    interfering with each other.

    The files need not be a package and need no ``__init__.py``. A file listed
    twice, or already loaded, is skipped. Dependencies are validated once every
    file in the call has been loaded, so a prerequisite may live in any of them.
    """

    if isinstance(paths, str):
        raise TypeError(
            f"load_checks takes a list of paths, not one string: pass [{paths!r}]. "
            "A bare string would be read as a list of its characters."
        )
    resolved: list[str] = []
    for path in list(paths):
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
        module_name = f"jobcheck_check_file_{Path(name).stem}_{len(_LOADED_FILES)}"
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

    validate_registry()


def _topological_order() -> list[Check]:
    """Order checks so every prerequisite precedes its dependents.

    Depth-first search with a visiting set, which detects cycles as a side
    effect -- so ordering and cycle detection share one traversal.
    """

    by_code = {check.code: check for check in CHECKS}
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
    it merely lives in a check file this entry point did not load.  That is
    deliberately as loud as a typo: silently skipping a dependent check because
    its prerequisite's file is absent would change which checks run based on an
    unrelated argument, with no diagnostic.

    Also computes every check's :attr:`Check.layer` and caches the evaluation
    order, so neither is recomputed inside the per-row loop.
    """

    global _TOPO_ORDER
    known = {check.code for check in CHECKS}
    for check in CHECKS:
        for prerequisite in check.depends_on:
            if prerequisite not in known:
                raise ValueError(
                    f"Check {check.code!r} depends on {prerequisite!r}, which is not registered. "
                    "Either the code is a typo, or it lives in a check file that was not loaded "
                    f"(currently loaded: {loaded_check_files()})."
                )
    try:
        order = _topological_order()
    except RecursionError:
        # The walk is recursive, so its depth is the depth of the chain when a
        # prerequisite is registered after its dependents. A bare RecursionError
        # names neither the registry nor the chain, which is no help at all.
        deepest = max((len(check.depends_on) for check in CHECKS), default=0)
        raise ValueError(
            f"Dependency chain too deep to resolve among {len(CHECKS)} checks "
            f"(deepest declared depends_on: {deepest}). Shorten the chain, or "
            "register prerequisites before the checks that depend on them."
        ) from None
    by_code = {check.code: check for check in CHECKS}
    for check in order:
        check.layer = (
            0 if not check.depends_on
            else 1 + max(by_code[code].layer for code in check.depends_on)
        )
    _TOPO_ORDER = order


def _get_topo_order() -> list[Check]:
    """Return the cached evaluation order, computing it if the registry changed.

    ``validate_registry`` always sets the cache, so the second read cannot be
    ``None``; it is spelled as a local so mypy can see that without a branch
    nothing can reach.
    """

    if _TOPO_ORDER is None:
        validate_registry()
    order: list[Check] = _TOPO_ORDER or []
    return order


def load_overrides(paths: list[str]) -> list[OverrideRule]:
    """Load override rules from the named YAML files, in the order given.

    Named explicitly as a list, exactly as :func:`load_checks` names check files, and
    precedence follows that order: for a given row, the last matching rule wins.

    Load the check files first: a rule naming a code that is not registered is
    an error, since it would otherwise sit in the file doing nothing.
    """

    return rules.load_overrides(paths, {check.code for check in CHECKS})
