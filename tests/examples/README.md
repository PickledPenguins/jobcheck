# Example catalog

One directory per case: `cmd` (run from the project root), `README.md`,
`expected_stdout.txt` (compared byte for byte), `exit_code`. Run by
`tests/test_e2e_catalogs.py` in the long suite.

Dimensions covered: suite selection (default, one suite, multi-value `-e`,
repeated `-e`), override loading (root file, split across a directory, several
files in unrelated directories, both orderings of the same three files),
verbosity (0, 1, 2), and entry point (`examples/main.py`, `examples/main_hard_only.py`).

Overlap is deliberate — `multi-value-flag` and `repeated-flag` produce the same
output as `default-run`, and each stands alone as a copyable reference.

Not covered here, because a unit test asserts it more precisely: every rejection
of a malformed rule file (see `../failures/`), individual check behaviour, and
table rendering details.

Absolute paths are normalised to `<project>` before comparison; nothing else is.

Regenerate after an intended change with `python3 scripts/regen_catalog.py`,
then read the diff — a blind regeneration defeats the catalog.
