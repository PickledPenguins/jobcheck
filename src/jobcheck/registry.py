"""The registry: what checks exist, how they depend on each other, and loading.

Everything about the *set* of checks -- registration, file loading, dependency
validation, ordering and layers -- and nothing about running them, which is
`engine.py`.
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

    `code` is permanent: never renumbered, never reused even after the check it
    named is deleted, because rule files and saved reports refer to codes.

    There is no `column` field -- a check reads whatever columns it needs from
    the row, and many weigh several together.
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
    """Wrap an author's function so the engine can always call `fn(row, context)`.

    The shape is settled once, at registration, rather than inspected per row.
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
    def call_with_context(row: "pd.Series[Any]", context: RowContext | None) -> Any:
        return fn(row, context)

    def call_with_row_only(row: "pd.Series[Any]", context: RowContext | None) -> Any:
        return fn(row)

    # *args counts as taking the context: the author's function will accept it.
    if any(p.kind is p.VAR_POSITIONAL for p in parameters) or len(positional) == 2:
        return call_with_context
    if len(positional) == 1:
        return call_with_row_only
    raise ValueError(
        f"Check {code!r}: {fn.__name__}{signature} must take (row) or (row, context), "
        f"not {len(positional)} positional argument(s)."
    )


def _reject_bad_registration(
    code: Any, message: Any, default_enabled: Any, prerequisites: Any, where: str
) -> None:
    """Everything a `register_check` call can get wrong, in one place.

    `depends_on` is checked for shape here and for existence in
    `validate_registry`: a prerequisite may live in a module not yet imported, so
    only its shape can be judged this early.
    """

    if not isinstance(code, str) or not code:
        raise ValueError(f"Check code must be a non-empty string, got {code!r}.")
    if not isinstance(message, str) or not message:
        raise ValueError(f"Check {code!r}: message must be the text a person sees on failure.")
    if any(check.code == code for check in CHECKS):
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


def register_check(
    code: str,
    message: str,
    default_enabled: bool = True,
    depends_on: list[str] | None = None,
) -> Callable[[CheckFn], CheckFn]:
    """Register one validation function: a function in a `check_*.py` file, and
    no central list to edit.

    Everything that can be wrong fails at import, where the author is looking at
    the file with the mistake in it.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        global _TOPO_ORDER

        module = getattr(fn, "__module__", None)
        # depends_on is inspected before it is copied: list("CODE") would turn a
        # mistyped bare string into its characters, and the prerequisite check
        # downstream would then complain about a check called 'C'.
        prerequisites = [] if depends_on is None else depends_on
        _reject_bad_registration(
            code, message, default_enabled, prerequisites,
            where=f"{module}.{fn.__name__}" if module else fn.__name__,
        )

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

    For a throwaway registry, and for a process validating several runs in turn.
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


#: Everything `clear_registry` clears, as one value. A dict rather than four
#: return values so adding registry state does not change this signature.
RegistryState = dict[str, Any]


def snapshot() -> RegistryState:
    """Copy the whole registry, to be handed back to `restore` later.

    One place owns what registry state *is*, so a caller cannot miss a piece.
    """

    return {
        "checks": list(CHECKS),
        "loaded_files": list(_LOADED_FILES),
        "registering_modules": set(_REGISTERING_MODULES),
        "topo_order": _TOPO_ORDER,
    }


def restore(state: RegistryState) -> None:
    """Put back a registry :func:`snapshot` took, dropping whatever is there now."""

    global _TOPO_ORDER
    clear_registry()
    CHECKS.extend(state["checks"])
    _LOADED_FILES.extend(state["loaded_files"])
    _REGISTERING_MODULES.update(state["registering_modules"])
    _TOPO_ORDER = state["topo_order"]


def loaded_check_files() -> list[str]:
    """Check files loaded so far, in load order (a copy)."""

    return list(_LOADED_FILES)


def load_checks(paths: list[str]) -> None:
    """Import the named check files so their checks register themselves.

    Every file is named explicitly and nothing is discovered, so two entry points
    in one codebase can run different sets of checks without interfering. A file
    listed twice, or already loaded, is skipped.
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

    Depth-first, so a code met twice on one path is a cycle: ordering and cycle
    detection share the traversal.
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
    """Check every `depends_on` edge, compute each check's layer, and cache the
    evaluation order so neither is recomputed inside the per-row loop.

    An unregistered prerequisite raises, including one that merely lives in a
    file this entry point did not load: skipping the dependent silently would
    change which checks run based on an unrelated argument.
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
    """The cached evaluation order, computed if the registry has changed since.

    The local spelling is what lets mypy see the cache is set by then.
    """

    if _TOPO_ORDER is None:
        validate_registry()
    order: list[Check] = _TOPO_ORDER or []
    return order


def load_overrides(paths: list[str]) -> list[OverrideRule]:
    """Load override rules from the named YAML files, in precedence order. Load
    the check files first: a rule naming an unregistered code is an error."""

    return rules.load_overrides(paths, {check.code for check in CHECKS})
