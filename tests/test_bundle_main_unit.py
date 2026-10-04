"""The bundle entry point, driven in this process.

`tests/examples/bundles/` runs it as a subprocess and compares its output byte
for byte; these reach the branches a recorded run cannot show -- the argument
that names a different bundle -- and keep the shipped bundle itself under check,
since an entry point nobody imports is an example nobody has run.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

import bundle_main
from conftest import PROJECT_ROOT
from jobcheck import registry as reg

pytestmark = pytest.mark.fast


def test_the_entry_point_prints_the_registry_with_each_check_s_file(
    fresh_registry: None, capsys: Any
) -> None:
    """The member files show through the checks they registered; the bundle
    itself registers nothing, so it is not among them."""

    bundle_main.main([])
    out = capsys.readouterr().out
    assert out.startswith("== Registry ==")
    assert "source_file" in out.splitlines()[1]
    for member in ("check_row_shape.py", "check_age.py", "check_dates.py", "check_email.py"):
        assert member in out
    assert "all_checks.py" not in out


def test_an_argument_names_a_different_bundle(fresh_registry: None, capsys: Any,
                                              tmp_path: Path) -> None:
    (tmp_path / "check_one.py").write_text(
        "from jobcheck import OK, register_check\n"
        "@register_check('ONLY_ONE', 'the only check in this bundle')\n"
        "def only_one(row): return OK\n"
    )
    bundle = tmp_path / "small_bundle.py"
    bundle.write_text(
        "import os\n"
        "from jobcheck import load_checks\n"
        "load_checks(['check_one.py'], base_dir=os.path.dirname(os.path.abspath(__file__)))\n"
    )

    bundle_main.main([str(bundle)])

    assert [check.code for check in reg._CHECKS] == ["ONLY_ONE"]
    assert "ONLY_ONE" in capsys.readouterr().out


def test_no_argument_means_the_shipped_bundle() -> None:
    assert bundle_main.DEFAULT_BUNDLE == os.path.join(
        PROJECT_ROOT, "examples/checks/all_checks.py")
    assert bundle_main.build_parser().parse_args([]).bundle == bundle_main.DEFAULT_BUNDLE


def test_help_answers_rather_than_being_read_as_a_bundle_path(capsys: Any) -> None:
    """Regression: `--help` was element zero of `sys.argv[1:]`, so it reached
    `load_checks` and came back as `No check file at '--help'` with a traceback
    and exit 1 -- at the one command a reader tries first."""

    with pytest.raises(SystemExit) as excinfo:
        bundle_main.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    # The program name is argv[0], which is pytest here; the catalog's
    # subprocess run is what pins the real one.
    assert out.startswith("usage: ")
    assert "[PATH]" in out
    assert "the bundle to load" in out

