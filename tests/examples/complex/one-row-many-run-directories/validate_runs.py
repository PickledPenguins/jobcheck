"""Validate jobs whose rows each name several run directories, known only at run time.

A job's row holds a base directory `base` and a count `v`; its run directories
are `base`, `base2`, ... `base{v}`. The frame is expanded to one row per run
before `validate`, so each run gets its own report lines, its own dependency
chain and its own rule matches -- the library is not asked to do anything new.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "src"))

import pandas as pd  # noqa: E402

from jobcheck import (  # noqa: E402
    RowContext, build_report, is_null, load_checks, load_rules, summarize_outcomes, validate,
)


def run_count(v: object) -> int:
    """`v` when it is a whole number of at least 1, else 1: a bad count becomes
    one row that COUNT_VALID reports, not an exception that stops the run."""

    text = "" if is_null(v) else str(v).strip()
    return int(text) if text.isdigit() and int(text) >= 1 else 1


def expand(jobs: pd.DataFrame) -> pd.DataFrame:
    """One row per run, numbered from 1 in `instance`, keyed `J2#3` in `key`."""

    runs = jobs.assign(instance=[list(range(1, run_count(v) + 1)) for v in jobs["v"]])
    runs = runs.explode("instance", ignore_index=True)
    runs["key"] = runs["id"] + "#" + runs["instance"].astype(str)
    return runs


@dataclass
class RunContext(RowContext):
    """The run directory one row's checks read. None where `base` is blank."""

    run_dir: Path | None = None
    shown: str = ""


def build_context(row: "pd.Series[str]") -> RunContext:
    if is_null(row["base"]):
        return RunContext()
    suffix = "" if row["instance"] == 1 else str(row["instance"])
    shown = row["base"] + suffix
    return RunContext(run_dir=HERE / shown, shown=shown)


def main() -> None:
    load_checks(["check_run_instances.py"], base_dir=str(HERE))
    rules = load_rules(["rules.yaml"], base_dir=str(HERE))
    runs = expand(pd.read_csv(HERE / "jobs.csv", dtype=str))
    outcomes = validate(runs, rules=rules, context_builder=build_context)
    print(build_report(outcomes, df=runs, key_column="key").to_csv(index=False))
    print(summarize_outcomes(outcomes).to_csv(index=False), end="")


if __name__ == "__main__":
    main()
