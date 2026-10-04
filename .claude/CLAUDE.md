# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## What this is

`jobcheck`: validating rows of a pandas DataFrame with many small, independently named
checks that depend on each other, so a blank field produces one error rather than one from
every check that reads it. The README is the reference manual and `docs/` holds the rest;
read `docs/interfaces.md` before changing a public name. The package is `src/jobcheck/`.

The vocabulary is "check", never "test": a `test_*` name in an adopter's project is
collected by pytest, which turns the registry's duplicate-code guard into a mysterious test
failure. A brief rename to "test" was reverted for exactly this reason.

`git log` starts on 2026-09-09: the `.git` directory was lost and re-initialized. For
anything older, and for the bytecode recovery of the modules lost then (`lint`,
`parallel`, `params`), read `.agent/history.md`. It is history only; nothing in it
describes the current code.

## Commands

```sh
tests/run-tests.sh          # fast: unit, interface, regression, cheap pathological, plus ruff and mypy
tests/run-tests.sh long     # integration, load, concurrency, faults, scaling, catalogs, then the profile
tests/run-tests.sh all      # both, plus ruff, mypy and the profile
tests/run-tests.sh cov      # the fast suite with coverage, gated at 95%
tests/run-tests.sh perf     # timing against this machine's baseline (its own gate)
tests/run-tests.sh memory   # peak-memory ceilings (its own gate)
tests/run-tests.sh profile  # where the example runs spend their time
tests/run-tests.sh mutation # a clean mutmut run, gated at 94% (~4 min)
tests/run-tests.sh types    # ruff and mypy alone (ruff lints; nothing auto-formats)
scripts/install-hooks.sh
scripts/new_catalog_case.py <kind> <path> ...       # add one catalog case, output and all
scripts/regen_catalog.py, scripts/regen_golden.py   # regenerate committed fixtures
scripts/regen_docs.py [name]                        # the output shown in docs/ and the README, from what it prints
scripts/make_example_data.py                        # regenerate examples/data/*.csv
scripts/profile_examples.py                         # the profile, alone

```

Every mode runs from the project root whichever directory it is invoked from. Generated
files go under `.build/` -- coverage data, the pytest, ruff and mypy caches, the hypothesis
storage, the example profile, the machine's performance baseline -- except `mutants/`,
which `mutmut` hardcodes beside the project and which is transient.

This file is `.claude/CLAUDE.md`, and the handoff record is `.agent/HANDOFF.md` beside
saved reviews in `.agent/reviews/`. The project root carries source, docs and packaging
only, deliberately.

The long suite needs `hypothesis` and refuses to run without it rather than skipping the
property tests quietly; `PYTHON=/path/to/python` picks the interpreter, and the conda
`pytesting` environment is the one here that has `hypothesis` and `mutmut`. `ruff` lints
only: the gate never runs `--fix` or `ruff format`, and neither should an agent.

Python 3.10+ (`X | None` syntax throughout), pandas 2.1+ and PyYAML at runtime;
`pip install -e .[dev]` for the suite, which needs pytest, coverage, mypy, ruff, hypothesis and
mutmut. Tests are split by pytest markers (`fast`, `long`), not by directory.

## jobchain

`~/work/ai/jobchain` (branch `simplify`) calls this package. Everything it depends on is
listed in `jobchain/checks.py:_ENGINE_NAMES`; check a rename or removal here against that
list. `tests/test_differential_jobchain.py` restates what jobchain's suite asserts of the
engine and runs it against this tree. Nothing here imports jobchain, and nothing should:
the dependency runs one way.
