# A clean file in the nightly job's shape

The same shape as `large-export-full-report` -- every rule file, CSV out, counts
after -- against the file with nothing wrong, so the two diff cleanly and the
difference is the data rather than the invocation.

Level:    complex
Input:    `examples/data/customers_clean.csv` under all four rule files
Expected: the CSV header row alone where the report would go, then counts that
          are all passes with `root_cause_rows` 0 throughout; exit 0
