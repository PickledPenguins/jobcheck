"""Row-validation framework.

Importing this package registers **no** checks: an entry point calls
`load_checks` with the files it wants, and `load_rules` with the rule files
that switch individual checks off for chosen rows.
"""

from __future__ import annotations

__version__ = "0.2.0"
"""Pre-1.0: the API may change between versions. Check codes, status values and
the rule YAML schema are permanent -- data written against them outlives the
code."""

from .context import RowContext
from .registry import (
    Check,
    Rule,
    clear_registry,
    load_checks,
    load_setup,
    load_rules,
    loaded_check_files,
    register_check,
    validate_registry,
)
from .engine import (
    explain_row,
    root_causes,
    validate,
    validate_row,
)
from .registry_tables import registry_table, rules_table
from .rules import warn_missing_rule_columns, warn_shadowed_rules
from .report import (
    REPORT_COLUMNS,
    build_report,
    render_comments,
    row_explanation,
    summarize_outcomes,
)
from .results import (
    DISABLED,
    ERRORED,
    FAILED,
    OK,
    PASSED,
    SKIPPED,
    Status,
    CheckOutcome,
    Verdict,
    render_status,
)
from .tables import is_null, render

__all__ = [
    "Check",
    "CheckOutcome",
    "DISABLED",
    "ERRORED",
    "FAILED",
    "OK",
    "PASSED",
    "REPORT_COLUMNS",
    "RowContext",
    "Rule",
    "SKIPPED",
    "Status",
    "Verdict",
    "build_report",
    "clear_registry",

    "explain_row",
    "is_null",
    "load_checks",
    "load_rules",
    "load_setup",
    "loaded_check_files",
    "register_check",
    "registry_table",
    "render",
    "render_comments",
    "render_status",
    "root_causes",
    "row_explanation",
    "rules_table",
    "summarize_outcomes",
    "validate",
    "validate_registry",
    "validate_row",
    "__version__",
    "warn_missing_rule_columns",
    "warn_shadowed_rules",
]
