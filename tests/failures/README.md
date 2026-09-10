# Failure catalog

The mistakes a user actually makes, each asserting the exact final line of
stderr and the exit code. Same layout as the example catalog, but with
`expected_stderr.txt` instead of `expected_stdout.txt`.

Only the last non-blank line of stderr is compared: it is the message the user
reads, while the traceback frames above it carry line numbers that move with any
edit. Absolute paths are normalised to `<project>`.

Covered: unknown suite; missing override file; a rule naming a code whose suite
was not loaded; unknown flag and a flag missing its value (both exit 2); and the
rule-file rejections a non-developer hits — `match: []`, missing `match`,
`match: al`, an invalid regex, a misspelled code, and a duplicate rule name
across two files.

These are also the troubleshooting reference: `docs/usage.md` quotes the same
messages.
