# Golden files

The exact tables the report library builds, written as pandas writes CSV
(`to_csv(index=False)`) and compared byte for byte by `tests/test_golden_output.py`.
One view per file, so a diff points at the value that moved rather than at a wall of
unrelated output.

| File | What it pins |
|---|---|
| `report.csv` | The failure report: column order, quoting, the `<no key>` label, the trailing newline. Also compared against the bytes a written file holds. |
| `report_with_extra_columns.csv` | `add_columns=[...]`: frame columns placed between `row` and `code`, and how their values read. |
| `report_with_skipped.csv` | `include="blocked"`, so every outcome the report can carry appears: failed, skipped, disabled, each status, both root-cause values. |
| `row_explanation.csv` | `row_explanation` on the all-null row. |
| `summary.csv` | `summarize_outcomes`: per-check counts and the root-cause column. |

All five come from the fixed frame and rule file in `tests/golden_fixture.py` —
no clock, no paths, no filesystem ordering — which is what makes byte comparison
safe.

Regenerate after an intended change with `python3 scripts/regen_golden.py`, then
**read the diff**. A blind regeneration turns a golden file into a rubber stamp.

These are not the only pinned output: `tests/examples/` holds the same kind of
comparison for what `examples/main.py` prints end to end, through a real subprocess.
