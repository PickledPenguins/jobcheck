"""Checks on a job manifest, reading paths the context built once per row.

The path checks take `(row, context)`: the absolute run directory and input file
are derived from each other and from the run's base directory, so they are worked
out once per row by the builder rather than once per check. The presence checks
take `(row)` and come first, so a path check only runs where its cells are filled
and the builder had a path to give.
"""

from jobcheck import OK, Status, Verdict, is_null, register_check


@register_check("RUN_DIR_PRESENT", "Run directory is blank")
def run_dir_present(row):
    return Verdict(Status.MISSING) if is_null(row["run_dir"]) else OK


@register_check("INPUT_PRESENT", "Input file name is blank")
def input_present(row):
    return Verdict(Status.MISSING) if is_null(row["input"]) else OK


@register_check("RUN_DIR_EXISTS", "Run directory does not exist",
                depends_on=["RUN_DIR_PRESENT"])
def run_dir_exists(row, context):
    if not context.run_dir.is_dir():
        return Verdict(Status.MISSING, {"run_dir": row["run_dir"]})
    return OK


@register_check("INPUT_EXISTS", "Input file is not in the run directory",
                depends_on=["RUN_DIR_EXISTS", "INPUT_PRESENT"])
def input_exists(row, context):
    if not context.input_file.is_file():
        return Verdict(Status.MISSING, {"input": row["input"]})
    return OK


@register_check("INPUT_EMPTY", "Input file is empty", depends_on=["INPUT_EXISTS"])
def input_not_empty(row, context):
    size = context.input_file.stat().st_size
    return OK if size > 0 else Verdict(Status.INVALID, {"bytes": size})


@register_check("OUTPUT_PRESENT", "Output path is missing")
def output_present(row):
    return Verdict(Status.MISSING) if is_null(row["output"]) else OK


@register_check("OUTPUT_SHARED", "Another job writes the same output",
                depends_on=["OUTPUT_PRESENT"])
def output_not_shared(row, context):
    writers = context.output_writers[row["output"]]
    if len(writers) > 1:
        return Verdict(Status.INVALID, {"writers": ",".join(writers)})
    return OK
