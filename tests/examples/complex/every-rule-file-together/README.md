# Every rule file together

All four shipped rule files, from three directories, in one run. Several of
them touch the same codes, so the last-match-wins rule decides the outcome for
every row -- and the `-v` cross-reference columns show which rules were even in
the running for each test.

Level:    complex
Input:    `examples/data/customers.csv` with all four rule files
Expected: the cross-reference columns naming several rules per code, and a report
          reflecting only the last matching one; exit 0

Why this combination:

Precedence is invisible in any one rule file. It only exists between files, and
this is the case where four of them argue about three codes on 49 rows.
