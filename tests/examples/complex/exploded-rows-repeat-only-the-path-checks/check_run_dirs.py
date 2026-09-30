"""Checks on a job whose `basedirname` lists its run directories, one row per
directory after the entry point explodes the list.

BASE_EXISTS repeats, so it runs on every copy of a job's row, and CHILD_EXISTS
repeats because it depends on it: each directory's child is checked only when
that directory exists. NAMES_PRESENT and VAL_IN_RANGE are about the job, so they
run on its first row and every copy shares their result.
"""

from pathlib import Path

from jobcheck import OK, Status, Verdict, is_null, register_check

RUNS = Path(__file__).resolve().parent / "runs"


@register_check("NAMES_PRESENT", "No run directories listed")
def names_present(row):
    return Verdict(Status.MISSING) if is_null(row["basedirname"]) else OK


@register_check("VAL_IN_RANGE", "val is outside 0 to 10")
def val_in_range(row):
    return OK if 0 <= float(row["val"]) <= 10 else Verdict(Status.INVALID, {"val": row["val"]})


@register_check("BASE_EXISTS", "Run directory does not exist",
                depends_on=["NAMES_PRESENT"], repeat=True)
def base_exists(row):
    return OK if (RUNS / row["dirname"]).is_dir() else Verdict(Status.MISSING)


@register_check("CHILD_EXISTS", "Child directory does not exist", depends_on=["BASE_EXISTS"])
def child_exists(row):
    child = RUNS / row["dirname"] / row["basedirname"]
    return OK if child.is_dir() else Verdict(Status.MISSING, {"child": child.relative_to(RUNS)})
