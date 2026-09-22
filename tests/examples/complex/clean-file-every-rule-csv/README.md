# A clean file in the nightly job's shape

The same shape as `large-export-full-report` -- every rule file, CSV out, counts
after -- against the file with nothing wrong, so the two diff cleanly and the
difference is the data rather than the invocation.

Level:    complex
Input:    `examples/data/customers_clean.csv` under all four rule files
Expected: `No failures.` where the CSV rows would go (no header row: the console
          report is prose when empty in both formats), then counts that are all
          passes and `Root causes: none - every row passed.`; exit 0
