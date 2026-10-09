"""The registry: what checks exist, how they depend on each other

Everything about the *set* of checks (registration, file loading, dependency
validation, ordering and layers)
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
import sys
import zlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from .context import RowContext
from .paths import _key_names, _read_yaml, _resolve_input_file
from . import rules
from .rules import Rule

# What an author writes: (row) or (row, context), returning OK or a
# Verdict. The engine stores the normalized two-argument form.
CheckFn = Callable[..., Any]
RunnerFn = Callable[["pd.Series[Any]", RowContext | None], Any]


@dataclass
class _Check:
    """One registered check: its code, its message and the function that runs it"""

    code: str  # `code` is permanent: never renumbered, or reused
    message: str
    fn: RunnerFn
    source_file: str
    default_enabled: bool = True
    depends_on: list[str] = field(default_factory=list)
    repeat: bool = False  # Run on every copy of a row, not only the first
    repeats: bool = False  # Whether this check runs on every copy
    layer: int = 0  # How deep in the dependency graph this check sits


_CHECKS: list[_Check] = []

# Check files imported by path through load_checks(), resolved and in load order
_LOADED_FILES: list[str] = []

# The prefix of the module name load_checks gives each check file it runs;
# clear_registry drops those modules from sys.modules, and no others.
_CHECK_FILE_PREFIX = "jobcheck_check_file_"

# Cached topological order over depends_on edges, recomputed only when the
# registry changes, never inside the per-row loop.
_TOPO_ORDER: list[_Check] | None = None


def _name_of(fn: CheckFn) -> str:
    return getattr(fn, "__name__", type(fn).__name__)


def _source_file_of(fn: CheckFn) -> str:
    """The file a check was written in, or `<unknown>` (partial, callable object)."""
    try:
        return inspect.getsourcefile(fn) or "<unknown>"
    except TypeError:
        return "<unknown>"


def _defaulted_second(positional: list[inspect.Parameter]) -> inspect.Parameter | None:
    """The second of two positional parameters, when it has a default other than None
    E.g. `def f(row, limit=130)` reads as `(row, context)`, so `limit` would be
    handed the context."""
    if len(positional) != 2:
        return None
    second = positional[1]
    if second.default is second.empty or second.default is None:
        return None
    return second


def _make_runner(fn: CheckFn, code: str) -> RunnerFn:
    """Wrap Check function so the engine can always call `fn(row, context)`.

    The shape is settled once at registration.
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
            "putting it after a *.")

    def call_with_context(row: "pd.Series[Any]", context: RowContext | None) -> Any:
        return fn(row, context)

    def call_with_row_only(row: "pd.Series[Any]", context: RowContext | None) -> Any:
        return fn(row)

    # *args counts as taking the context, the Check function will accept it
    if any(p.kind is p.VAR_POSITIONAL for p in parameters) or len(positional) == 2:
        return call_with_context
    if len(positional) == 1:
        return call_with_row_only
    raise ValueError(
        f"Check {code!r}: {_name_of(fn)}{signature} must take (row) or (row, context), "
        f"not {len(positional)} positional argument(s).")


def _reject_bad_registration(
    code: Any, message: Any, default_enabled: Any, prerequisites: Any, repeat: Any, where: str
) -> None:
    """Everything the `register_check` call specifically can get wrong.

    `depends_on` is checked for shape here and for existence in
    `_validate_registry`. A prerequisite may live in a module not yet imported, so
    only its shape can be judged this early.
    """

    if not isinstance(code, str) or not code:
        raise ValueError(f"Check code must be a non-empty string, got {code!r}.")
    if not isinstance(message, str) or not message:
        raise ValueError(f"Check {code!r}: message must be the text a person sees on failure.")
    existing = next((check for check in _CHECKS if check.code == code), None)
    if existing is not None:
        # A file whose import failed part-way is not recorded as loaded, but the
        # checks it registered first stay: loading it again will duplicate the codes.
        raise ValueError(
            f"Duplicate check code {code!r} (registering {where}; "
            f"already registered from {existing.source_file}).")
    if (not isinstance(prerequisites, list) or
        not all(isinstance(prerequisite, str) and prerequisite
                for prerequisite in prerequisites)
    ):
        raise ValueError(
            f"Check {code!r}: depends_on must be a list of check codes, got {prerequisites!r}.")
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
    """Register one validation function: a function in a check file, and
    no central list to edit.

    `repeat=True` runs the check, and every check that depends on it, on each
    copy of a row when `validate` is given a `repeat_key`; the other checks run
    on the first copy whose rules enable them, and are shared by the rest.

    Everything that can be wrong fails at import.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        global _TOPO_ORDER

        module = getattr(fn, "__module__", None)
        # Checked before list() copies it: a bare string would become its characters
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
    the files `load_checks` is given.
    """
    global _TOPO_ORDER
    _CHECKS.clear()
    _LOADED_FILES.clear()
    for name in [name for name in sys.modules if name.startswith(_CHECK_FILE_PREFIX)]:
        del sys.modules[name]
    _TOPO_ORDER = None


class _NoBytecodeLoader(importlib.machinery.SourceFileLoader):
    """Imports a check file without writing a .pyc beside it (it may sit in a run's input directory)"""
    def set_data(self, path: str, data: Any, *, _mode: int = 0o666) -> None:
        pass


def load_checks(paths: list[str], base_dir: str | Path | None = None) -> None:
    """Import the named check files so their checks register themselves.

    Every file is named explicitly and nothing is discovered, so two entry points
    in one codebase can run different sets of checks without interfering. A file
    listed twice or already loaded raises before any file is imported.

    The dependency graph is validated once every file is imported, so a check may
    depend on one in any file of the same call, and on any file an earlier call loaded.

    A file that raises is not rolled back: the error propagates, and whatever
    was registered before it stays. Loading again in the same process must start
    with `clear_registry()`.

    A relative path is resolved against *base_dir* when one is given and
    against the working directory otherwise.
    """

    if isinstance(paths, str):
        raise TypeError(f"load_checks takes a list of paths, not one string: pass [{paths!r}].")

    resolved: list[str] = []
    for path in list(paths):
        name = str(_resolve_input_file(path, "check file", "load_checks()", base_dir))
        if name in _LOADED_FILES or name in resolved:
            raise ValueError(f"Check file listed twice or already loaded: {name}.")
        if Path(name).suffix != ".py":
            raise ValueError(f"Cannot import {name!r} as a Python file.")
        resolved.append(name)

    for name in resolved:
        # One module name per path, the same every run. Two run directories can each
        # hold a checks.py, and each needs its own sys.modules entry.
        module_name = f"{_CHECK_FILE_PREFIX}{Path(name).stem}_{zlib.crc32(name.encode()):08x}"
        loader = _NoBytecodeLoader(module_name, name)
        spec = importlib.util.spec_from_file_location(module_name, name, loader=loader)
        assert spec is not None  # None only when no loader is given
        module = importlib.util.module_from_spec(spec)
        # Registered before execution so a check file that imports itself finds
        # the module rather than importing it twice.
        sys.modules[module_name] = module
        loader.exec_module(module)
        _LOADED_FILES.append(name)
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
        if code in done:  # Path below code has been fully explored, return early
            return
        # Raise when a code is found twice in one path (a cycle)
        if code in visiting_set:
            cycle = visiting[visiting.index(code):] + [code]
            raise ValueError("Dependency cycle among checks: " + " -> ".join(cycle) + ".")
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
    this entry point did not load.
    """

    global _TOPO_ORDER
    known = {check.code for check in _CHECKS}
    for check in _CHECKS:
        for prerequisite in check.depends_on:
            if prerequisite not in known:
                raise ValueError(
                    f"Check {check.code!r} depends on {prerequisite!r}, which is not registered. "
                    "Either the code is a typo, or it lives in a check file that was not loaded "
                    f"(currently loaded: {_LOADED_FILES}).")
    order = _topological_order()
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


def load_rules(paths: list[str], base_dir: str | Path | None = None) -> list[Rule]:
    """Load rules from the named YAML files, in precedence order. Load
    the check files first: a rule naming an unregistered code is an error. A file
    listed twice raises.

    *base_dir* anchors relative paths exactly as it does in `load_checks`."""
    return rules._load_rule_files(paths, {check.code for check in _CHECKS}, base_dir)


def warn_blocking_rules(rules: list[Rule]) -> list[str]:
    """Warn about disable rules that switch off more than they name.

    A check runs only once its prerequisites passed, so disabling one skips
    everything that depends on it, directly or not, on every row the rule
    matches (a skipped check reports nothing). One line per rule and
    disabled code, naming the dependents the rule does not itself disable.
    Listing them in the rule says the silence is intentional, and ends the warning.
    Needs the registry, which is why it lives here rather than beside
    `warn_shadowed_rules` in `rules.py`.
    """

    order = _get_topo_order()
    rank = {check.code: (check.layer, check.code) for check in order}
    # Every check depending on each code, directly or through others. Reversed, the
    # order reaches each check before its prerequisites, so its set is complete when read.
    below: dict[str, set[str]] = {check.code: set() for check in order}
    for check in reversed(order):
        for prerequisite in check.depends_on:
            below[prerequisite] |= {check.code} | below[check.code]

    warnings: list[str] = []
    for rule in list(rules):
        if rule.action != "disable":
            continue
        reach = {code: below.get(code, set()) for code in rule.codes}
        for code in rule.codes:
            # A code below another one the rule disables is silent either way;
            # naming it again would repeat that code's warning.
            if any(code in reach[other] for other in rule.codes if other != code):
                continue
            blocked = sorted(reach[code] - set(rule.codes), key=rank.__getitem__)
            if blocked:
                warnings.append(
                    f"rule {rule.name!r} disables {code}, which also stops "
                    f"{', '.join(blocked)} on the rows it matches: a check whose "
                    "prerequisite is off is skipped, and reports nothing")
    return warnings


# The only two keys a setup file holds. Named so the rejection can list them,
# and so a reader sees the whole schema in one line.
SETUP_KEYS = ("checks", "rules")


def _setup_paths(document: Any, key: str, path: Path, required: bool) -> list[str]:
    """One key of a setup file, validated as a list of paths."""

    value = document.get(key)
    if value is None:
        if required:
            raise ValueError(
                f"{path}: {key!r} is required: a setup file names the files to load.")
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"{path}: {key!r} must be a list of paths, got {type(value).__name__}.")
    for position, entry in enumerate(value, 1):
        if not isinstance(entry, str):
            raise ValueError(
                f"{path}: {key!r} entry {position} must be a path, "
                f"got {type(entry).__name__}.")
    if required and not value:
        raise ValueError(f"{path}: {key!r} is empty: name at least one file.")
    return list(value)


def load_setup(path: str) -> list[Rule]:
    """Load the check files and rule files from one YAML setup file. Returns the rules.

    The file holds `checks` and, optionally, `rules`, each a list of paths:
        checks:
          - checks/check_age.py
        rules:
          - rules/01_age.yaml

    Both are resolved against the **setup file's own directory**, so the file and
    the paths in it travel together. The setup file's own path is relative to where
    the caller stands, like any path a user types. `checks` is required, because a
    setup naming only rules configures nothing (rules switch checks on and off).
    It composes `load_checks` and `load_rules`.
    """

    setup_file = _resolve_input_file(path, "setup file", "load_setup()")
    document = _read_yaml(setup_file, str(setup_file))
    if not isinstance(document, dict):
        key_str = ' and '.join(repr(key) for key in SETUP_KEYS)
        raise ValueError(
            f"{setup_file}: a setup file is a mapping of "
            f"{key_str}, got {type(document).__name__}.")
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
