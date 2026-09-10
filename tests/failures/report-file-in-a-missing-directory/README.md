# Writing a report into a directory that is not there

One of the mistakes a user actually makes, and the message it gets.

Input:    `--report-file` under a directory that does not exist
Expected: see `expected_stderr.txt`; a non-zero exit
