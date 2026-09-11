#!/usr/bin/env python3
"""Create one catalog case: the directory, the command, and the README.

    scripts/new_catalog_case.py examples data/validate-a-csv-file \
        --level simple --title "Validate a CSV export" \
        --input '`examples/data/customers.csv` (49 rows)' \
        --expected 'one line per failure, keyed by `id`; exit 0' \
        --why 'The everyday run: point the tool at a file and read the failures.' \
        -- --data examples/data/customers.csv

Writes `tests/<kind>/<path>/cmd` and `README.md`, then runs the case through the
real entry point to record `expected_stdout.txt` (or `expected_stderr.txt` for a
failure case) and `exit_code`, exactly as `regen_catalog.py` would.

A case whose command another case already uses is refused. That is not
tidiness: two cases with identical commands are one case filed twice, and the
duplicate is invisible in a directory listing because the names differ. The
first version of this catalog had three of them, made by a throwaway generator
that had no such check.

Exit codes: 0 written; 1 the case already exists or duplicates another's command;
2 usage error.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from catalog import CASE_FILES, case_dirs, run_case, stderr_tail  # noqa: E402

LEVELS = ("simple", "moderate", "complex")


def existing_commands(kind: str) -> dict[str, Path]:
    """Every command already in this catalog, mapped to the case that uses it."""

    commands: dict[str, Path] = {}
    for case in case_dirs(kind):
        commands[(case / "cmd").read_text(encoding="utf-8").strip()] = case
    return commands


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create one catalog case.")
    parser.add_argument("kind", choices=("examples", "failures"))
    parser.add_argument("path", help="case directory under tests/<kind>/, e.g. data/my-case")
    parser.add_argument("--title", required=True)
    parser.add_argument("--why", required=True, help="what it demonstrates, a sentence or two")
    parser.add_argument("--input", required=True, help="the Input: line")
    parser.add_argument("--expected", required=True, help="the Expected: line")
    parser.add_argument("--level", choices=LEVELS, help="required for an example case")
    parser.add_argument("command", nargs="*", help=argparse.SUPPRESS)
    # Split on the first bare `--` by hand: a nargs=REMAINDER positional
    # swallows every option typed after the first positional, so the --title
    # and --level that come after `examples <path>` would never be parsed.
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" not in raw:
        print("new_catalog_case: no command given (use -- before it)", file=sys.stderr)
        return 2
    split = raw.index("--")
    arguments = raw[split + 1:]
    if not arguments:
        print("new_catalog_case: no command given (use -- before it)", file=sys.stderr)
        return 2
    args = parser.parse_args(raw[:split])

    if args.kind == "examples" and not args.level:
        print("new_catalog_case: an example case needs --level", file=sys.stderr)
        return 2

    case = ROOT / "tests" / args.kind / args.path
    if case.exists():
        print(f"new_catalog_case: {case} already exists", file=sys.stderr)
        return 1

    command = "python3 examples/main.py " + " ".join(shlex.quote(a) for a in arguments)
    clash = existing_commands(args.kind).get(command)
    if clash is not None:
        print(f"new_catalog_case: {clash.relative_to(ROOT)} already runs that exact command.\n"
              "Two cases with one command are one case filed twice; change something about "
              "this one, or extend the existing case's README instead.", file=sys.stderr)
        return 1

    case.mkdir(parents=True)
    (case / "cmd").write_text(command + "\n", encoding="utf-8")
    readme = [f"# {args.title}", "", args.why, ""]
    if args.level:
        readme.append(f"Level:    {args.level}")
    readme += [f"Input:    {args.input}", f"Expected: {args.expected}", ""]
    (case / "README.md").write_text("\n".join(readme), encoding="utf-8")

    result = run_case(case)
    stdout_file, stderr_file, exit_file = (case / name for name in CASE_FILES)
    if args.kind == "examples":
        stdout_file.write_text(result.stdout, encoding="utf-8")
        if result.stderr:
            stderr_file.write_text(result.stderr, encoding="utf-8")
    else:
        stderr_file.write_text(stderr_tail(result.stderr), encoding="utf-8")
    exit_file.write_text(f"{result.returncode}\n", encoding="utf-8")

    print(f"{case.relative_to(ROOT)}: exit {result.returncode}")
    print("Read the recorded output before committing -- a case that records the wrong "
          "answer is a defect with a test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
