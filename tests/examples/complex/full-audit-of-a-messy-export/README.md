# Full audit of a messy export

Everything at once on the file the tool was built for: both registry tables at
full verbosity, the by-rule table, two rule files whose criteria overlap, the
tests a failure blocked, two columns of context, and the summary.

Level:    complex
Input:    `examples/data/customers.csv` with two rule files, verbosity 2
Expected: every table the entry point can print, in one run; exit 0

Why this combination:

No single feature is under test here. What is under test is that they compose:
the rule files change which tests are enabled, the enabled set changes which
failures appear, the failures change which tests are skipped, and the summary
has to agree with all of it.
