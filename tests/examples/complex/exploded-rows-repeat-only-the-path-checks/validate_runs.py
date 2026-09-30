"""Validate jobs whose rows list their run directories, known only at run time.

`basedirname` holds a comma-separated list such as `alpha,alpha,beta`. The frame
is exploded to one row per name, every other column copied, and a repeated name
is numbered in `dirname`: `alpha`, `alpha2`, `beta`. `validate` is told that rows
sharing an `id` are copies, so only the checks registered with `repeat=True`, and
their dependents, run on every copy; the rest run once per job.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "src"))

import pandas as pd  # noqa: E402

from jobcheck import (  # noqa: E402
    build_report, load_checks, load_rules, row_explanation, summarize_outcomes, validate,
)


def expand(jobs: pd.DataFrame) -> pd.DataFrame:
    """One row per listed name; `dirname` numbers the second and later uses of a name."""

    runs = jobs.assign(basedirname=jobs["basedirname"].str.split(","))
    runs = runs.explode("basedirname", ignore_index=True)
    # dropna=False: a job listing no names keeps a blank row for NAMES_PRESENT.
    use = runs.groupby(["id", "basedirname"], dropna=False).cumcount() + 1
    runs["dirname"] = runs["basedirname"] + use.map(lambda n: "" if n == 1 else str(n))
    return runs


def main() -> None:
    load_checks(["check_run_dirs.py"], base_dir=str(HERE))
    rules = load_rules(["rules.yaml"], base_dir=str(HERE))
    runs = expand(pd.read_csv(HERE / "jobs.csv", dtype=str))
    outcomes = validate(runs, rules=rules, repeat_key="id")
    print(build_report(outcomes, df=runs, key_column="id", add_columns=["dirname"])
          .to_csv(index=False))
    print(summarize_outcomes(outcomes).to_csv(index=False))
    # J2's second copy: what ran there, and what it shares with J2's first row.
    print(row_explanation(outcomes[4]).to_csv(index=False), end="")


if __name__ == "__main__":
    main()
