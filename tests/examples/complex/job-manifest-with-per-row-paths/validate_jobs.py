"""Validate a job manifest whose checks need per-row paths and a cross-row count.

Neither `examples/main.py` nor the run file can pass a context builder, so a
manifest like this one needs an entry point of its own. The builder takes
`(row, args)`: `args` carries what the whole run shares -- the base directory and
which jobs write each output -- computed once, before any row.
"""

from __future__ import annotations

import sys
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "src"))

import pandas as pd  # noqa: E402

from jobcheck import (  # noqa: E402
    RowContext, build_report, load_checks, render, summarize_outcomes, validate,
)


@dataclass
class JobContext(RowContext):
    """The paths one row's checks read, derived once for the row."""

    run_dir: Path = Path()
    input_file: Path = Path()
    output_writers: dict[str, list[str]] = field(default_factory=dict)


def build_context(row: "pd.Series[str]", args: Namespace) -> JobContext:
    run_dir = args.base / row["run_dir"]
    return JobContext(run_dir=run_dir, input_file=run_dir / row["input"],
                      output_writers=args.output_writers)


def main() -> None:
    load_checks(["check_job_paths.py"], base_dir=str(HERE))
    jobs = pd.read_csv(HERE / "jobs.csv", dtype=str)
    shared = Namespace(
        base=HERE,
        output_writers=jobs.dropna(subset=["output"]).groupby("output")["id"]
        .apply(list).to_dict(),
    )
    outcomes = validate(jobs, context_builder=build_context, context_args=shared)
    print(render(build_report(outcomes, df=jobs, key_column="id", add_columns=["run_dir"])))
    print()
    print(render(summarize_outcomes(outcomes)))


if __name__ == "__main__":
    main()
