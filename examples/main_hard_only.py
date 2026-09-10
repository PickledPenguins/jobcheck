"""Second entry point loading only one flavor.

Run this alongside ``examples/main.py`` to see that entry points are independent: the
soft_tests tests never register here, so no email check appears in the
registry or in any row's errors. The base flavor still loads, as it always does.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import pandas as pd

from pandas_row_validation import (
    build_context,
    load_overrides_from_dir,
    load_suites,
    loaded_suites,
    print_registry,
    root_cause,
    validate_row,
)


def main(argv: list[str] | None = None) -> None:
    """Load only the hard_tests suite, then validate a two-row frame.

    It takes no options, but still parses the command line so that ``--help``
    works and a mistyped flag is rejected rather than silently ignored.
    """

    argparse.ArgumentParser(
        description="Demo entry point loading only the hard_tests suite. Takes no options."
    ).parse_args(argv)

    load_suites(["hard_tests"], package="example_suites")
    print(f"Loaded suites: {sorted(loaded_suites())}\n")

    # Only 01_age_rules.yaml applies here: the email rules in 02_*.yaml name
    # codes from a flavor this entry point does not load, which would be a
    # load-time error, so this directory is filtered by pattern.
    overrides = load_overrides_from_dir("examples/rules/split_by_topic", pattern="01_*.yaml")

    print("== Registry (hard_tests only) ==")
    print_registry(overrides=overrides, debug=1)

    df = pd.DataFrame(
        [
            {"id": 1, "age": 30.5, "email": "ignored@example.com", "start_date": "2024-01-01",
             "end_date": "2024-01-02", "source_system": "LEGACY_A", "record_type": "BATCH"},
            {"id": 2, "age": 30.5, "email": "ignored", "start_date": "2024-01-01",
             "end_date": "2024-01-02", "source_system": "MODERN", "record_type": "STREAM"},
        ]
    )
    df["errors"] = df.apply(lambda row: validate_row(row, ctx=build_context(row), overrides=overrides), axis=1)

    print("\n== Per-row results ==")
    for _, row in df.iterrows():
        results = row["errors"]
        codes = [r.code for r in results] or ["OK"]
        cause = root_cause(results)
        suffix = f" (root cause {cause})" if cause else ""
        print(f"row id={row['id']}: " + ", ".join(codes) + suffix)


if __name__ == "__main__":
    main()
