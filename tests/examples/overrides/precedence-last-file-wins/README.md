# Precedence across directories: last file wins

The global `disable` rule is given last, so it beats the earlier `enable` on the
legacy batch row. Files may live in unrelated directories.

Level:    moderate
Input:    three `-o` paths, global rule last
Expected: row 3 (the LEGACY_A/BATCH row) is OK -- AGE_NOT_INTEGER stays off; exit 0
