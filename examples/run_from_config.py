"""Third demonstration entry point: one YAML file is the whole run.

`examples/main.py` spreads a run across its flags and its own constants; this one
reads every part of it -- the setup file, the data, which tables to print and
which columns each carries -- from one file, so the run is something to commit,
diff against last week's, or hand to somebody else. The file is the whole input:
there are no flags, so there is no question of which one wins.

The run-file format is this script's, not the library's. `src/jobcheck/` has no
command line and one configuration format of its own (the rule file, and the
setup file that names rule files); this shows an adopter the pattern rather than
dictating it.

    setup: setup.yaml              # a load_setup file: the checks and the rules
    data: data/customers.csv       # read as text, as `main.py --data` reads it
    tables:                        # printed in this order; a table may repeat
      - table: registry
        drop_columns: [source_file]
      - table: report
        key_column: id

Both paths are resolved against the run file's own directory, as `load_setup`
resolves its own, so the run file and what it names travel together.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from typing import Any, Callable, NoReturn

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import yaml  # noqa: E402

from jobcheck import (  # noqa: E402
    CheckOutcome,
    Rule,
    build_report,
    load_setup,
    registry_table,
    rules_table,
    summarize_outcomes,
    validate,
    warn_blocking_rules,
    warn_missing_rule_columns,
    warn_shadowed_rules,
)
from main import exit_if_a_check_raised, load_frame, table_text  # noqa: E402

#: The run file loaded when the command line names none.
DEFAULT_RUN = os.path.join(PROJECT_ROOT, "examples/run.yaml")

#: The top-level keys of a run file. All three are required.
RUN_KEYS = ("setup", "data", "tables")

#: Every table a run can print, and the options each takes beside `table`.
#: The options are the table functions' own argument names, so the library's
#: documentation of each one is the documentation of the key -- except
#: `drop_columns`, which this script applies to the built table with pandas.
TABLE_OPTIONS: dict[str, tuple[str, ...]] = {
    "registry": ("drop_columns",),
    "rules": ("drop_columns",),
    "report": ("key_column", "add_columns", "drop_columns", "include", "format"),
    "summary": (),
}

#: The options that hold a list of column names; every other one is a string.
LIST_OPTIONS = ("add_columns", "drop_columns")


class StrictLoader(yaml.SafeLoader):
    """`SafeLoader`, refusing a key given twice in one mapping.

    PyYAML keeps the last of two identical keys and says nothing, so a second
    `tables:` would quietly drop every table the first one listed. The library
    reads its own files the same way; an entry point reading a format of its
    own needs its own copy.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> Any:
        seen: dict[Any, int] = {}
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue  # `<<` may repeat a key on purpose; the explicit one wins
            key = self.construct_object(key_node, deep=deep)
            line = key_node.start_mark.line + 1
            try:
                earlier = seen.get(key)
            except TypeError:  # unhashable: SafeLoader refuses it itself
                continue
            if earlier is not None:
                raise yaml.constructor.ConstructorError(
                    None, None,
                    f"key {key!r} appears twice in one mapping, on lines {earlier} and "
                    f"{line}; YAML would keep only the last", key_node.start_mark)
            seen[key] = line
        return super().construct_mapping(node, deep=deep)


def build_parser() -> argparse.ArgumentParser:
    """One positional argument and nothing else, as `bundle_main.py` has."""

    parser = argparse.ArgumentParser(
        description="Run the whole of one validation from a run file: the setup, "
                    "the data, and the tables to print.")
    parser.add_argument("run_file", nargs="?", default=DEFAULT_RUN, metavar="PATH",
                        help="the run file (default: the shipped examples/run.yaml).")
    return parser


def key_names(keys: Any) -> str:
    """Keys as a message lists them, `'extra', True`: each as Python writes it, so a
    key YAML read as a bool or a number shows as one. The library's own messages
    use the same form."""

    return ", ".join(repr(key) for key in sorted(keys, key=str))


def fail(run_file: str, message: str) -> NoReturn:
    """Every problem with the run file, one line on stderr and exit 2."""

    print(f"error: {run_file}: {message}", file=sys.stderr)
    raise SystemExit(2)


def read_run_file(run_file: str) -> dict[str, Any]:
    """The run file, parsed and checked for shape before anything is loaded.

    Only the shape is checked here. Whether a column or an `include` level exists
    is the library's to say, and whether a format exists is `table_text`'s; both
    say it when the tables are built -- see `print_tables`.
    """

    try:
        with open(run_file, encoding="utf-8") as handle:
            document = yaml.load(handle, Loader=StrictLoader)
    except OSError as exc:
        fail(run_file, f"cannot read it: {exc.strerror}")
    except UnicodeDecodeError as exc:
        fail(run_file, f"not UTF-8 text: {exc}. Save the file as UTF-8.")
    except yaml.YAMLError as exc:
        # PyYAML's message runs over several lines; one keeps it one error.
        fail(run_file, f"not valid YAML: {' '.join(str(exc).split())}")

    if not isinstance(document, dict):
        fail(run_file, f"a run file is a mapping of {key_names(RUN_KEYS)}, "
                       f"got {type(document).__name__}.")
    unknown = set(document) - set(RUN_KEYS)
    if unknown:
        fail(run_file, f"unknown key(s) {key_names(unknown)}. A run file holds "
                       f"{key_names(RUN_KEYS)}.")
    for key in RUN_KEYS:
        if key not in document:
            fail(run_file, f"{key!r} is required.")
    for key in ("setup", "data"):
        if not isinstance(document[key], str):
            fail(run_file, f"{key!r} must be a path, got {type(document[key]).__name__}.")

    tables = document["tables"]
    if not isinstance(tables, list) or not tables:
        fail(run_file, "'tables' must be a non-empty list: a run prints at least one.")
    for position, spec in enumerate(tables, 1):
        check_table(run_file, position, spec)
    return document


def check_table(run_file: str, position: int, spec: Any) -> None:
    """One entry of `tables`: a known table, and only the options it takes."""

    where = f"table {position}"
    if not isinstance(spec, dict) or "table" not in spec:
        fail(run_file, f"{where} must be a mapping with a 'table' key naming one of "
                       f"{', '.join(TABLE_OPTIONS)}.")
    name = spec["table"]
    # A list or a mapping cannot even be looked up, and is as unknown as a typo.
    if not isinstance(name, str) or name not in TABLE_OPTIONS:
        fail(run_file, f"{where}: unknown table {name!r}. "
                       f"The tables are {', '.join(TABLE_OPTIONS)}.")
    allowed = TABLE_OPTIONS[name]
    unknown = set(spec) - {"table", *allowed}
    if unknown:
        takes = key_names(allowed) if allowed else "no options"
        fail(run_file, f"{where} ({name}): unknown option(s) {key_names(unknown)}. "
                       f"It takes {takes}.")
    for option, value in spec.items():
        if option == "table":
            continue
        # A bare string where a list belongs is the shape somebody writes first,
        # and a string is iterable: it would ask for one column per character.
        if option in LIST_OPTIONS:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                fail(run_file, f"{where} ({name}): {option!r} must be a list of column "
                               f"names. Write it as a list even for one column.")
        elif not isinstance(value, str):
            fail(run_file, f"{where} ({name}): {option!r} must be a string, "
                           f"got {type(value).__name__}.")


def print_tables(tables: list[dict[str, Any]], rules: list[Rule], df: Any,
                 outcomes: list[list[CheckOutcome]]) -> None:
    """Print each table the run file names, in its order, a blank line between."""

    printers: dict[str, Callable[[dict[str, Any], list[str]], object]] = {
        # Given the rules, which is what fills `could_be_overridden_by`.
        "registry": lambda options, drop: print(table_text(
            registry_table(rules=rules, **options).drop(columns=drop))),
        "rules": lambda options, drop: print_rules_and_warnings(rules, options, drop),
        "report": lambda options, drop: print_one_report(df, outcomes, options, drop),
        "summary": lambda options, drop: print(table_text(summarize_outcomes(outcomes))),
    }
    for position, spec in enumerate(tables, 1):
        if position > 1:
            print()
        options = {key: value for key, value in spec.items() if key != "table"}
        # The library takes no drop_columns; this script drops from the built table.
        drop = options.pop("drop_columns", [])
        try:
            printers[spec["table"]](options, drop)
        except (ValueError, KeyError) as exc:
            # KeyError is pandas refusing a drop_columns name the table lacks.
            reason = exc.args[0] if isinstance(exc, KeyError) else exc
            raise ValueError(f"table {position} ({spec['table']}): {reason}") from None


def print_rules_and_warnings(rules: list[Rule], options: dict[str, Any],
                             drop: list[str]) -> None:
    """The rules table, then any rule a later one overrules on every row and any
    disable rule that silences checks it does not name -- what
    `main.py --rules-table` prints."""

    print(table_text(rules_table(rules, **options).drop(columns=drop)))
    for warning in warn_shadowed_rules(rules) + warn_blocking_rules(rules):
        print(f"warning: {warning}")


def print_one_report(df: Any, outcomes: list[list[CheckOutcome]],
                     options: dict[str, Any], drop: list[str]) -> None:
    """Build and print one report. `format` is the run file's name for `fmt`."""

    fmt = options.pop("format", "table")
    print(table_text(build_report(outcomes, df=df, **options).drop(columns=drop), fmt=fmt))


def main(argv: list[str] | None = None) -> None:
    """Read the run file, load what it names, validate, and print its tables."""

    run_file = build_parser().parse_args(argv).run_file
    document = read_run_file(run_file)
    here = os.path.dirname(os.path.abspath(run_file))

    try:
        rules = load_setup(os.path.join(here, document["setup"]))
    except (ValueError, OSError, yaml.YAMLError) as exc:
        fail(run_file, str(exc))
    df = load_frame(os.path.join(here, document["data"]))
    for warning in warn_missing_rule_columns(df, rules):
        print(f"warning: {warning}", file=sys.stderr)
    outcomes = validate(df, rules=rules)

    # Printed into a buffer first, so a table whose options the library refuses
    # -- a column that does not exist, an unknown format -- fails the run before
    # any of it reaches stdout, rather than after the tables above it.
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            print_tables(document["tables"], rules, df, outcomes)
    except ValueError as exc:
        fail(run_file, str(exc))
    sys.stdout.write(buffer.getvalue())
    exit_if_a_check_raised(outcomes)


if __name__ == "__main__":
    main()
