"""Row-validation framework.

Importing this package registers **no** checks: an entry point calls
`load_checks` with the files it wants, and `load_overrides` with the rule files
that switch individual checks off for chosen rows.
"""

from __future__ import annotations

__version__ = "0.2.0"
"""Pre-1.0: the API may change between versions. Check codes, status values and
the override YAML schema are permanent -- data written against them outlives the
code."""

from .context import RowContext
from .registry import (
    CHECKS,
    Check,
    MatchCriterion,
    OverrideRule,
    clear_registry,
    load_checks,
    load_overrides,
    loaded_check_files,
    register_check,
    restore,
    snapshot,
    validate_registry,
)
from .engine import (
    explain_row,
    resolve_enabled_state,
    root_causes,
    validate,
    validate_row,
)
from .registry_tables import (
    get_registry_table,
    list_rule_codes,
    print_override_rules,
    print_registry,
)
from .rules import check_override_columns
from .report import (
    build_report,
    escape_for_spreadsheet,
    print_report,
    print_row_explanation,
    print_summary,
    render_comments,
    render_report,
    root_cause_counts,
    row_explanation,
    summarize_outcomes,
    write_report,
)
from .results import (
    DISABLED,
    ERRORED,
    FAILED,
    PASS,
    PASSED,
    SKIPPED,
    Status,
    CheckOutcome,
    CheckResult,
    normalize_result,
    render_status,
)
from .tables import format_table, is_null

__all__ = [
    "CHECKS",
    "Check",
    "CheckOutcome",
    "CheckResult",
    "DISABLED",
    "ERRORED",
    "FAILED",
    "MatchCriterion",
    "OverrideRule",
    "PASS",
    "PASSED",
    "RowContext",
    "SKIPPED",
    "Status",
    "__version__",
    "build_report",
    "check_override_columns",
    "clear_registry",
    "escape_for_spreadsheet",
    "explain_row",
    "format_table",
    "get_registry_table",
    "is_null",
    "list_rule_codes",
    "load_checks",
    "load_overrides",
    "loaded_check_files",
    "normalize_result",
    "print_override_rules",
    "print_registry",
    "print_report",
    "print_row_explanation",
    "print_summary",
    "register_check",
    "render_comments",
    "render_report",
    "render_status",
    "resolve_enabled_state",
    "restore",
    "root_cause_counts",
    "root_causes",
    "row_explanation",
    "snapshot",
    "summarize_outcomes",
    "validate",
    "validate_registry",
    "validate_row",
    "write_report",
]
