# Failure catalog

The mistakes a user actually makes, each asserting the exact final line of
stderr and the exit code. Same layout as the example catalog, but with
`expected_stderr.txt` instead of `expected_stdout.txt`.

Only the last non-blank line of stderr is compared: it is the message the user
reads, while the traceback frames above it carry line numbers that move with any
edit. Absolute paths are normalized to `<project>`.

Covered: a data file that is missing, a directory, empty or not CSV; `--explain`
past the end of the frame and below its start; an unknown flag and a flag missing
its value (both exit 2); a missing rule file; and the rule-file rejections a
non-developer hits — `match: []`, missing `match`, `match: al`, an invalid regex,
a misspelled code, a bad `action`, a file that is not a list, and a duplicate rule
name across two files. Two run files for `examples/run_from_config.py`: one naming a
table that does not exist, refused before anything loads, and one asking the report for
a column the data lacks, refused once the data is read and before any table prints.

These are also the troubleshooting reference: `docs/cli.md` quotes the same
exit codes.
