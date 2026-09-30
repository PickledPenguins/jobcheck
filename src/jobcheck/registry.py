"""The registry: what checks exist, how they depend on each other, and loading.

Everything about the *set* of checks -- registration, file loading, dependency
validation, ordering and layers -- and nothing about running them, which is
`engine.py`. `load_setup` and its two-key schema live here too, because the setup
file composes `load_checks` and `load_rules` and this is the module that has both.
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
from .paths import _key_names, _read_yaml, resolve_input_file
from . import rules
from .rules import Rule

# What an author writes: (row) or (row, context), returning OK or a
# Verdict. The engine stores the normalized two-argument form.
CheckFn = Callable[..., Any]
RunnerFn = Callable[["pd.Series[Any]", RowContext | None], Any]


@dataclass
class _Check:
    """One registered check: its code, its message and the function that runs it.

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
    repeat: bool = False
    """Declared: run on every copy of a row, not only the first. See `repeats`."""
    repeats: bool = False
    """Whether this check runs on every copy: declared with `repeat`, or inherited
    from a prerequisite that repeats. Computed by :func:`_validate_registry`."""
    layer: int = 0
    """How deep in the dependency graph this check sits: 0 with no prerequisites,
    otherwise one more than its deepest prerequisite. Computed by
    :func:`_validate_registry`, never set by hand. A low layer means a
    fundamental check, which is what makes it a root cause."""


_CHECKS: list[_Check] = []

# Check files imported by path through load_checks(), resolved and in load
# order.
_LOADED_FILES: list[str] = []
# The prefix of the module name load_checks gives each check file it runs;
# clear_registry drops those modules from sys.modules, and no others.
_CHECK_FILE_PREFIX = "jobcheck_check_file_"
# Check files mid-import, innermost last: how a nested load_checks call (a
# bundle) knows it is nested, and how a bundle naming itself is skipped.
_LOADING: list[str] = []
# Cached topological order over depends_on edges, recomputed only when the
# registry changes, never inside the per-row loop.
_TOPO_ORDER: list[_Check] | None = None
# Import attempts so far, which makes each load's module name unique. Not
# len(_LOADED_FILES): a bundle is named before its members finish, so the two
# would share a number.
_LOAD_SEQUENCE = 0


def _name_of(fn: CheckFn) -> str:
    """What to call the thing being registered, in a message. A plain function
    carries `__name__`; a `functools.partial` or a callable object does not."""

    return getattr(fn, "__name__", type(fn).__name__)


def _source_file_of(fn: CheckFn) -> str:
    """The file a check was written in, or `<unknown>` for the shapes
    `inspect.getsourcefile` refuses (a partial, a callable object)."""

    try:
        return inspect.getsourcefile(fn) or "<unknown>"
    except TypeError:
        return "<unknown>"


def _defaulted_second(positional: list[inspect.Parameter]) -> inspect.Parameter | None:
    """The second of two positional parameters, when it has a default other than
    None: `def f(row, limit=130)` reads as `(row, context)`, so `limit` would be
    handed the context. Shared by `_make_runner` and `engine._context_caller`."""

    if len(positional) != 2:
        return None
    second = positional[1]
    if second.default is second.empty or second.default is None:
        return None
    return second


def _make_runner(fn: CheckFn, code: str) -> RunnerFn:
    """Wrap an author's function so the engine can always call `fn(row, context)`.

    The shape is settled once, at registration, rather than inspected per row.
    `engine._context_caller` applies the same rule to a context builder; change
    the two together.
    """

    signature = inspect.signature(fn)
    parameters = list(signature.parameters.values())
    positional = [p for p in parameters
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    needed = [p.name for p in parameters
              if p.kind is p.KEYWORD_ONLY and p.default is p.empty]
    if needed:
        raise ValueError(
            f"Check {code!r}: {_name_of(fn)}{signature} needs keyword argument(s) "
            f"{', '.join(needed)} that the engine cannot supply. Give them defaults, "
            "or read them from the row or the context."
        )
    defaulted = _defaulted_second(positional)
    if defaulted is not None:
        raise ValueError(
            f"Check {code!r}: {_name_of(fn)}{signature} has a default on its second "
            f"parameter, {defaulted.name!r}, which would be handed the row's context. "
            "Bind the value with functools.partial, or make it keyword-only by "
            "putting it after a *."
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
        f"Check {code!r}: {_name_of(fn)}{signature} must take (row) or (row, context), "
        f"not {len(positional)} positional argument(s)."
    )


def _reject_bad_registration(
    code: Any, message: Any, default_enabled: Any, prerequisites: Any, repeat: Any, where: str
) -> None:
    """Everything a `register_check` call can get wrong, in one place.

    `depends_on` is checked for shape here and for existence in
    `_validate_registry`: a prerequisite may live in a module not yet imported, so
    only its shape can be judged this early.
    """

    if not isinstance(code, str) or not code:
        raise ValueError(f"Check code must be a non-empty string, got {code!r}.")
    if not isinstance(message, str) or not message:
        raise ValueError(f"Check {code!r}: message must be the text a person sees on failure.")
    if any(check.code == code for check in _CHECKS):
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
    if not isinstance(repeat, bool):
        raise ValueError(f"Check {code!r}: repeat must be True or False, got {repeat!r}.")


def register_check(
    code: str,
    message: str,
    default_enabled: bool = True,
    depends_on: list[str] | None = None,
    repeat: bool = False,
) -> Callable[[CheckFn], CheckFn]:
    """Register one validation function: a function in a `check_*.py` file, and
    no central list to edit.

    `repeat=True` runs the check, and every check that depends on it, on each
    copy of a row when `validate` is given a `repeat_key`; the other checks run
    on the first copy only.

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
            code, message, default_enabled, prerequisites, repeat,
            where=f"{module}.{_name_of(fn)}" if module else _name_of(fn),
        )

        check = _Check(
            code=code,
            message=message,
            fn=_make_runner(fn, code),
            source_file=_source_file_of(fn),
            default_enabled=default_enabled,
            depends_on=list(dict.fromkeys(prerequisites)),
            repeat=repeat,
        )
        _CHECKS.append(check)
        _TOPO_ORDER = None
        return fn

    return decorator


def clear_registry() -> None:
    """Drop every registered check and all loaded-file bookkeeping.

    For a process validating several runs in turn, each with its own check
    files. The next `load_checks` runs each file again; a module a check file
    merely imports is cached by Python and does not, so checks register only in
    the files `load_checks` is given. The in-progress load stack is not touched:
    it belongs to a running `load_checks` call rather than to the registry.
    """

    global _TOPO_ORDER
    _CHECKS.clear()
    _LOADED_FILES.clear()
    for name in [name for name in sys.modules if name.startswith(_CHECK_FILE_PREFIX)]:
        del sys.modules[name]
    _TOPO_ORDER = None


def load_checks(paths: list[str], base_dir: str | Path | None = None) -> None:
    """Import the named check files so their checks register themselves.

    Every file is named explicitly and nothing is discovered, so two entry points
    in one codebase can run different sets of checks without interfering. A file
    listed twice, already loaded, or already being loaded further up the call is
    skipped.

    A check file may call this itself -- a bundle file naming the files it
    collects, so a caller loads one path instead of ten. The dependency graph is
    then validated once, as the outermost call returns, since a prerequisite may
    arrive in any file of any of the calls.

    A file that raises is not rolled back: the error propagates, and whatever
    was registered before it stays. Loading again in the same process starts
    with `clear_registry()`.

    A relative path is resolved against *base_dir* when one is given and
    against the working directory otherwise.

    Load from one thread: the registry and `sys.dont_write_bytecode` are
    process-wide, and nothing guards them.
    """

    if isinstance(paths, str):
        raise TypeError(
            f"load_checks takes a list of paths, not one string: pass [{paths!r}]. "
            "A bare string would be read as a list of its characters."
        )

    global _LOAD_SEQUENCE
    resolved: list[str] = []
    for path in list(paths):
        name = str(resolve_input_file(path, "check file", "load_checks()", base_dir))
        # A file mid-import is skipped, so a bundle naming itself, or two naming
        # each other, finish instead of recursing.
        if name not in _LOADED_FILES and name not in resolved and name not in _LOADING:
            resolved.append(name)

    for name in resolved:
        # A unique module name per load: two run directories can each hold a
        # checks.py, and each needs its own sys.modules entry -- sharing one, the
        # second would replace the first there, so the first could no longer be
        # imported or pickled by name.
        module_name = f"{_CHECK_FILE_PREFIX}{Path(name).stem}_{_LOAD_SEQUENCE}"
        _LOAD_SEQUENCE += 1
        spec = importlib.util.spec_from_file_location(module_name, name)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot import {name!r} as a Python file.")
        module = importlib.util.module_from_spec(spec)
        # Registered before execution so a check file that imports itself, or is
        # pickled by a worker, finds the module rather than importing it twice.
        sys.modules[module_name] = module
        # No __pycache__ beside a check file: it may sit in a run's input
        # directory, and the unique module name means a .pyc is never reused.
        # The flag is process-wide for the length of the exec.
        writing_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        _LOADING.append(name)
        try:
            spec.loader.exec_module(module)
        finally:
            _LOADING.pop()
            sys.dont_write_bytecode = writing_bytecode
        _LOADED_FILES.append(name)

    # Nested calls leave it to the outermost one: a bundle's members may depend
    # on each other in any order, and on files the caller names after the bundle.
    if not _LOADING:
        _validate_registry()


def _topological_order() -> list[_Check]:
    """Order checks so every prerequisite precedes its dependents.

    Depth-first, so a code met twice on one path is a cycle: ordering and cycle
    detection share the traversal.
    """

    by_code = {check.code: check for check in _CHECKS}
    order: list[_Check] = []
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

    for check in _CHECKS:
        visit(check.code)
    return order


def _validate_registry() -> None:
    """Check every `depends_on` edge, compute each check's layer and whether it
    repeats, and cache the evaluation order so none of it is recomputed inside
    the per-row loop.

    An unregistered prerequisite raises, including one that lives in a file
    this entry point did not load. The message names `clear_registry` because
    the file holding the bad `depends_on` is already recorded, so loading it
    again after the fix is skipped until the registry is emptied.
    """

    global _TOPO_ORDER
    known = {check.code for check in _CHECKS}
    for check in _CHECKS:
        for prerequisite in check.depends_on:
            if prerequisite not in known:
                raise ValueError(
                    f"Check {check.code!r} depends on {prerequisite!r}, which is not registered. "
                    "Either the code is a typo, or it lives in a check file that was not loaded "
                    f"(currently loaded: {_LOADED_FILES}). Loading the missing file "
                    "works; correcting an already-loaded one does not, because load_checks "
                    "skips a path it has already read -- call clear_registry() first."
                )
    try:
        order = _topological_order()
    except RecursionError:
        # The walk is recursive, so a long enough chain exhausts the stack. The
        # chain's length is unknown here, so the message names the limit instead.
        widest = max((len(check.depends_on) for check in _CHECKS), default=0)
        raise ValueError(
            f"Dependency chain too deep to resolve among {len(_CHECKS)} checks: the "
            f"ordering walk is recursive and gives out near Python's recursion limit "
            f"of {sys.getrecursionlimit()} (widest declared depends_on: {widest}). "
            "Shorten the chain, or register prerequisites before the checks that "
            "depend on them."
        ) from None
    by_code = {check.code: check for check in _CHECKS}
    for check in order:
        check.layer = (
            0 if not check.depends_on
            else 1 + max(by_code[code].layer for code in check.depends_on)
        )
        check.repeats = check.repeat or any(by_code[code].repeats for code in check.depends_on)
    _TOPO_ORDER = order


def _get_topo_order() -> list[_Check]:
    """The cached evaluation order, computed if the registry has changed since."""

    if _TOPO_ORDER is None:
        _validate_registry()
    order: list[_Check] = _TOPO_ORDER or []
    return order


def load_rules(paths: list[str],
                   base_dir: str | Path | None = None) -> list[Rule]:
    """Load rules from the named YAML files, in precedence order. Load
    the check files first: a rule naming an unregistered code is an error.

    *base_dir* anchors relative paths exactly as it does in `load_checks`."""

    return rules._load_rule_files(paths, {check.code for check in _CHECKS}, base_dir)


#: The only two keys a setup file holds. Named so the rejection can list them,
#: and so a reader sees the whole schema in one line.
SETUP_KEYS = ("checks", "rules")


def _setup_paths(document: Any, key: str, path: Path, required: bool) -> list[str]:
    """One key of a setup file, validated as a list of paths.

    Refuses a string where a list belongs. `checks: checks.py` is the shape
    somebody writes first, and YAML reads it as a string, which would otherwise
    load a file per character.
    """

    value = document.get(key)
    if value is None:
        if required:
            raise ValueError(
                f"{path}: {key!r} is required: a setup file names the files to load.")
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"{path}: {key!r} must be a list of paths, got {type(value).__name__}. "
            f"Write it as a list even for one file.")
    for position, entry in enumerate(value, 1):
        if not isinstance(entry, str):
            raise ValueError(
                f"{path}: {key!r} entry {position} must be a path, "
                f"got {type(entry).__name__}.")
    if required and not value:
        raise ValueError(f"{path}: {key!r} is empty: name at least one file.")
    return list(value)


def load_setup(path: str) -> list[Rule]:
    """Load the check files and rule files one YAML file names, and return the
    rules -- the whole of configuring this library, in one call.

    The file holds `checks` and, optionally, `rules`, each a list of paths::

        checks:
          - checks/all_checks.py
        rules:
          - rules/01_age.yaml

    Both are resolved against the **setup file's own directory**, so the file and
    the paths in it travel together; the setup file's own path is relative to where
    the caller stands, like any path a user types. `checks` is required, because a
    setup naming only rules configures nothing -- rules switch checks on and off.
    It composes `load_checks` and `load_rules` and does nothing they do not.
    """

    setup_file = resolve_input_file(path, "setup file", "load_setup()")
    document = _read_yaml(setup_file, str(setup_file))
    if not isinstance(document, dict):
        raise ValueError(
            f"{setup_file}: a setup file is a mapping of "
            f"{' and '.join(repr(key) for key in SETUP_KEYS)}, "
            f"got {type(document).__name__}.")
    unknown = set(document) - set(SETUP_KEYS)
    if unknown:
        raise ValueError(
            f"{setup_file}: unknown key(s) {_key_names(unknown)}. A setup file holds "
            f"{_key_names(SETUP_KEYS)}.")

    here = setup_file.parent
    check_files = _setup_paths(document, "checks", setup_file, required=True)
    rule_files = _setup_paths(document, "rules", setup_file, required=False)
    load_checks(check_files, base_dir=here)
    return load_rules(rule_files, base_dir=here)
