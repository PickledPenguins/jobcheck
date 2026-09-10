# Every layer failing at once

One run showing every layer of the dependency graph failing on some row: a
missing age at layer 0, an unreadable one at layer 1, a negative and an
implausible one at layer 2, and dates and emails doing the same -- each with the
values that caused it beside the failure.

Level:    complex
Input:    `examples/data/customers.csv`, keyed by name, four data columns
Expected: failures at layers 0, 1 and 2, their skipped dependants, and a summary; exit 0

Why this combination:

The layering claim -- one failure per row rather than one per test that reads
the column -- is only observable when several layers are failing at once on
different rows of the same file.
