# A key column with blanks in it

`region` is blank on the empty rows, so the report labels them `<no key>`
rather than `nan`. Keying by a non-unique column is legal and sometimes what
you want: it groups the failures by that column's value.

Level:    moderate
Input:    `examples/data/customers.csv`, keyed by `region`
Expected: failures labelled by region, with `<no key>` where it is blank; exit 0
