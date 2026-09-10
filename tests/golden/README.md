# Golden files

The exact text the report library produces, compared byte for byte by
`tests/test_golden_output.py`. One view per file, so a diff points at what moved
rather than at a wall of unrelated output.

| File | What it pins |
|---|---|
| `report_table.txt` | The failure report in table form: column widths, wrapping, the `<no key>` label. |
| `report.csv` | The same report as CSV: column order, quoting, formula escaping, the trailing newline. Also compared against the bytes `write_report` puts on disk. |
| `report_with_data_columns.txt` | `data_columns=[...]`: frame columns placed between `row` and `code`, and how their values render. |
| `report_with_skipped.txt` | `include_skipped=True`, so every outcome the report can carry appears: failed, skipped, disabled, each status, both root-cause values. |
| `row_explanation.txt` | `print_row_explanation` on the all-null row, including the root-cause line. |
| `summary.txt` | `print_summary`: per-test counts and the root-cause tally. |

All five come from the fixed frame and rule file in `tests/golden_fixture.py` —
no clock, no paths, no filesystem ordering — which is what makes byte comparison
safe.

Regenerate after an intended change with `python3 scripts/regen_golden.py`, then
**read the diff**. A blind regeneration turns a golden file into a rubber stamp.

These are not the only pinned output: `tests/examples/` holds the same kind of
comparison for what `examples/main.py` prints end to end, through a real subprocess.
