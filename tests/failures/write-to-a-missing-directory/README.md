# Writing the report where no directory exists

`--write` creates or replaces a file; it does not create the directory above it. The path is checked before anything is loaded or validated, so a run that cannot keep its output says so immediately rather than after the work, and nothing is printed that the file was supposed to hold.

Input:    the built-in demo frame, `--write nope/report.csv`
Expected: nothing on stdout; stderr names the path and the missing directory; exit 2
