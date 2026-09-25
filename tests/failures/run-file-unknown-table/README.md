# A run file naming a table that does not exist

The run file is checked for shape before anything is loaded, so a misspelled or
invented table name costs nothing: the message names the entry by position and
lists the four tables there are.

Input:    `tests/failures/run-file-unknown-table/run.yaml`, whose second table is `charts`
Expected: exit 2 with `error: <run file>: table 2: unknown table 'charts'` and the list of tables; nothing on stdout
