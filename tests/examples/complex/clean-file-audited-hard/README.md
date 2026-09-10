# A clean file, audited hard

Everything turned on, against a file with nothing wrong. The registry tables,
the rules, the cross-references and the summary all still have something to
say; only the report is empty.

Level:    complex
Input:    `examples/data/customers_clean.csv` with two rule files, verbosity 2
Expected: full tables, `No failures.`, and a summary that is all passes and disables; exit 0

Why this combination:

A tool that only makes sense when something is broken is hard to trust. This is
the negative control for the whole catalog: the same machinery, the same flags,
and a result that says nothing is wrong.
