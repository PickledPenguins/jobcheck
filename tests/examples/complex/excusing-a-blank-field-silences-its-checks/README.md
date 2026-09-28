# Excusing a blank field silences every check that reads it

The rule means "a blank age is fine for LEGACY_B rows" and says "switch AGE_PRESENT off for them". A disabled prerequisite blocks its dependents, so the negative, non-numeric and implausible ages on those rows pass without a word -- only the `skipped` column in the summary shows it, and the rules table warns about nothing. Rules cannot say "not required"; the check itself has to know which rows may leave the field blank.

Level:    complex
Input:    `legacy_import.csv` (six rows, four of them LEGACY_B) with `legacy_rules.yaml`, one rule disabling `AGE_PRESENT` for LEGACY_B
Expected: the rules table with no warning, then a report holding only the two MODERN rows; the three LEGACY_B rows with bad ages are absent, and the summary counts them as skipped; exit 0
