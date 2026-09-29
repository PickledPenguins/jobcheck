"""Checks on a job whose row names several run directories: `base`, `base2`, ...
`base{v}`.

The entry point gives each run directory a row of its own, so the per-run checks
chain per run: INPUT_EXISTS on run 3 depends on RUN_DIR_EXISTS on run 3 only. The
checks on `base` and `v` hold for the whole job; the expansion gives a job whose
`base` or `v` is unusable a single row, so their failures are reported once.
OWNER_PRESENT holds for the whole job too, and a rule turns it off past run 1.
"""

from jobcheck import OK, Status, Verdict, is_null, register_check


@register_check("BASE_PRESENT", "Base run directory is blank")
def base_present(row):
    return Verdict(Status.MISSING) if is_null(row["base"]) else OK


@register_check("COUNT_VALID", "Run count is not a whole number of at least 1")
def count_valid(row):
    text = "" if is_null(row["v"]) else str(row["v"]).strip()
    if text.isdigit() and int(text) >= 1:
        return OK
    return Verdict(Status.MALFORMED, {"v": row["v"]})


@register_check("OWNER_PRESENT", "Owner is blank")
def owner_present(row):
    return Verdict(Status.MISSING) if is_null(row["owner"]) else OK


@register_check("RUN_DIR_EXISTS", "Run directory does not exist",
                depends_on=["BASE_PRESENT", "COUNT_VALID"])
def run_dir_exists(row, context):
    if not context.run_dir.is_dir():
        return Verdict(Status.MISSING, {"run_dir": context.shown})
    return OK


@register_check("INPUT_EXISTS", "Input file is not in the run directory",
                depends_on=["RUN_DIR_EXISTS"])
def input_exists(row, context):
    if not (context.run_dir / "input.dat").is_file():
        return Verdict(Status.MISSING, {"run_dir": context.shown})
    return OK
