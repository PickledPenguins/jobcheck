# Two rules share a name across two files

Names identify a rule in tables and errors, so they must be unique across every
file loaded together.

Input:    two `-o` paths defining `same_name`
Expected: stderr naming both files; exit 1
