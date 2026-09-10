# Source files and the by-rule table

`-vv` would add source files and the by-rule table -- and `--no-registry`
suppresses all three tables, which is the interaction worth seeing: the
verbosity flag says how much detail, `--no-registry` says whether at all.

Level:    moderate
Input:    `examples/data/customers.csv`, verbosity 2, registry suppressed
Expected: no registry tables despite `-vv`; the report and summary only; exit 0
