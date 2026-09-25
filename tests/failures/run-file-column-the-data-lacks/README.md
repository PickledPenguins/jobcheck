# A run file asking the report for a column the data lacks

Which columns a table can carry is the library's to say, so this is found only
once the data is loaded and the report is built. The registry table ahead of it
was fine and would have printed; the run prints neither, because the tables are
built before any of them reaches stdout. The message names the table by
position and lists the columns the data does have.

Input:    `tests/failures/run-file-column-the-data-lacks/run.yaml`, whose report asks for `phone`
Expected: exit 2 with `error: <run file>: table 2 (report): add_columns ['phone'] cannot be used for the report` and the data's columns; nothing on stdout
