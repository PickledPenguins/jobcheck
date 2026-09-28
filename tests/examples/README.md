# Example catalog

One directory per case: `cmd` (run from the project root), `README.md`,
`expected_stdout.txt` (compared byte for byte), `exit_code`. Run by
`tests/test_e2e_catalogs.py` in the long suite.

Dimensions covered: the data (the built-in demo frame and all three shipped CSV
files), rule loading (the shipped file, topic files, files from unrelated
directories, and both orderings of the same three), the report format (table and
CSV), one row explained, and the summary. The `bundles/` cases run
`examples/bundle_main.py` instead, and carry their own check files: a bundle is
read together with the files beside it. The `run_file/` case runs
`examples/run_from_config.py` on the shipped `examples/run.yaml`.

Four `complex/` cases carry their own check files, data and rules, because the
shipped four cannot show what they show: a check with three prerequisites across
files, a check that raises, a rule disabling a presence check, and checks reading
a per-row context. Three run through `examples/run_from_config.py` (or
`examples/main.py`) on files in the case directory; the context case runs its own
script, since neither entry point passes a context builder.

Overlap is deliberate — several cases differ only in one flag, and each stands
alone as a copyable reference.

Not covered here, because a unit test asserts it more precisely: every rejection
of a malformed rule file (see `../failures/`), individual check behavior, and
table rendering details.

Absolute paths are normalized to `<project>` before comparison; nothing else is.

Regenerate after an intended change with `python3 scripts/regen_catalog.py`,
then read the diff — a blind regeneration defeats the catalog.
