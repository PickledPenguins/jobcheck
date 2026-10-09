# Example catalog

One directory per case: `cmd` (run from the project root), `README.md`,
`expected_stdout.txt` (compared byte for byte), `exit_code`. Run by
`tests/test_e2e_catalogs.py` in the long suite.

Dimensions covered: the data (the built-in demo frame and all three shipped CSV
files), rule loading (the shipped file, topic files, files from unrelated
directories, and both orderings of the same three), the report format (table and
CSV), how much of the report to print (`--include`), one row explained, and the
summary. The `run_file/` case runs
`examples/run_from_config.py` on the shipped `examples/run.yaml`.

Four `complex/` cases carry what the shipped files cannot show: a chain of checks across
three files, a check that raises, a rule disabling a presence check, and checks
reading a per-row context. All four bring their own data; three bring their own
check files (the rule case runs the shipped checks), and two their own rule files
(the order-lines and rule cases). Three run through `examples/run_from_config.py` (or
`examples/main.py`) on files in the case directory; the context case runs its own
script, since neither entry point passes a context builder.

Overlap is deliberate — several cases differ only in one flag, and each stands
alone as a copyable reference.

Not covered here, because a unit test asserts it more precisely: every rejection
of a malformed rule file (see `../failures/`), individual check behavior, and
how pandas lays out a table.

Absolute paths are normalized to `<project>` before comparison; nothing else is.

Add a case with `scripts/new_catalog_case.py`, which writes `cmd` and `README.md` and
records the output; its docstring has a full example. The entry point's arguments go
after a bare `--`, which is required even when there are none. `--entry` names a script
other than `examples/main.py`: `examples/run_from_config.py` or a
script in the case directory.

A `.py` file in a case directory needs a basename no other file under `tests/` uses,
`../failures/` included. Case directories are not packages, so mypy checks each such file
as a top-level module named after its basename, and two of the same name fail the fast
suite with `Duplicate module named ...`, naming both paths.

Regenerate after an intended change with `python3 scripts/regen_catalog.py`,
then read the diff — a blind regeneration defeats the catalog.
