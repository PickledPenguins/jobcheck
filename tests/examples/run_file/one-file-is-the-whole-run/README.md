# One file is the whole run

The run file names the setup file, the data and the four tables to print, with the columns each carries. Commit it beside a bug report and the run is reproducible without a shell history line.

Level:    moderate
Input:    `examples/run.yaml`, the shipped run file: `examples/setup.yaml` and `examples/data/customers.csv`
Expected: the rules table and its shadowed-rule warning, the registry, a report keyed by `id` with `name` beside it and no `comments` or `detail`, and the summary; exit 0
