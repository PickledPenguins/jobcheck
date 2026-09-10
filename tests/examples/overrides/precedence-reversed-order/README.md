# The same three files in the other order

The global `disable` now comes first, so the later `enable` wins on the legacy
batch row. Same files, opposite result -- precedence is positional.

Input:    three `-o` paths, global rule first
Expected: row 3 (the LEGACY_A/BATCH row) reports AGE_NOT_INTEGER; exit 0
