# A file without an id column

The report labels every row by its id, so a file without one is refused before anything is validated, rather than after the whole run.

Input:    a file keyed by a customer column instead of id
Expected: exit 2 naming the path and the columns the file has
