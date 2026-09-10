# recovery/

The bytecode of the sources this repository lost, and the interface read out of it.

## Why this directory exists

The `.git` directory was removed by mistake on 2026-09-09 and the repository was
re-initialised, so the history before that date is gone. The project was also
renamed in the same evening — package `jobcheck` to `jobcheck`, the
"check" vocabulary to "test" — and that rename is not in the log either.

Four modules and eleven test modules that existed before the accident exist
nowhere as source. What survived them is `__pycache__`, which the `.gitignore`
rules for `*.pyc` would have let a routine clean destroy. That is what this
directory is: the only copy, put where git can see it.

| Directory | What it holds |
|---|---|
| `bytecode/jobcheck/` | Every `.pyc` from `src/jobcheck/__pycache__` — both generations, `cpython-312` (compiled 09-03 to 09-07, the check-era source) and `cpython-314` (09-09 23:47). |
| `bytecode/tests/` | The `cpython-312` generation of `tests/__pycache__`: the eleven lost test modules, and the pre-shrink versions of the ones that survived. |
| `bytecode/examples_checks/` | `examples/checks/__pycache__`, whose sources are also gone. The current `examples/example_suites/` supersedes them. |

`recovered-api.md` and `recovered-tests-api.md` are generated:

```sh
scripts/read_bytecode_api.py recovery/bytecode/jobcheck > recovery/recovered-api.md
scripts/read_bytecode_api.py recovery/bytecode/tests   > recovery/recovered-tests-api.md
```

A `.pyc` keeps the source's byte size in its header and every code object in its
body, so names, parameters, annotations and docstrings all survive — the
statements do not. No decompiler available here reads 3.12 bytecode
(`uncompyle6` and `decompyle3` stop at 3.8; `pycdc` would have to be built), and
`dis` under 3.14 cannot disassemble a 3.12 code object either, though `marshal`
loads it fine. Reconstruction so far has meant reading the interface and writing
the body again.

## What was lost, and what was decided about each

| Module | Source was | Decision |
|---|---|---|
| `run` | 10,756 B | **Rebuilt** as `src/jobcheck/run.py`. It was the whole-frame entry point (`validate`, `iter_traces`, `ValidationRun`, `RowTrace`, `RunStats`) and the library had no successor to it. |
| `registry.load_checks` | part of `registry` | **Rebuilt** as `load_test_files`, for the caller that has paths rather than an importable package. |
| `lint` | 14,326 B | **Kept as bytecode, not rebuilt.** Warnings about rule files that parse but can never fire, fire everywhere, or were superseded — deliberately separate from the loader, which raises. Worth rebuilding when someone wants rule-file linting; nothing calls it today. Its test module was 37,624 B, so it was real, finished work. |
| `parallel` | 15,072 B | **Kept as bytecode, not rebuilt.** Ran a frame's rows across worker processes, rebuilding the registry in each worker because the engine's closures cannot be pickled. Rebuild it when a frame is big enough to need it, and measure first: the docstring records that threads lost to processes on 4,000 rows of the example suite. |
| `params` | 7,173 B | **Kept as bytecode, not rebuilt.** A flat namespace of named values a rule file could change per row, declared in Python so a typo is caught at load time. A design decision as much as a feature; do not rebuild it without deciding the override format should carry values as well as on/off. |
| `engine`, `registry_tables` | 12,198 B, 7,163 B | Nothing to do: both were folded into today's `registry.py`. |

Do not delete `bytecode/` while any of the three unrebuilt modules might be
wanted. Deleting it is the decision that they never come back.

## The lineage question this evidence does not settle

Two readings fit the file sizes equally well: one continuous line that renamed
check to test on 09-09 and dropped four modules in the same pass, or an earlier
line of development restored after the accident with later work on top. Two
details lean towards the second — the check-era `params` bytecode already
defines `TestParams`, and the check-era `run` already imports `TestRecord` — so
"test" was in use before the evening of the rename.

The other direction has evidence too: the check-era rule format
(`RULE_KEYS = {name, action, codes, column, pattern}`, matched with
`fnmatchcase`) is simpler than today's `match:` list of regex criteria, which
means the current tree is ahead on that file format.

`tests/test_differential_jobchain.py` is the standing experiment on this
question: it restates what jobchain's suite asserted of the check-era engine and
runs it against this one.
