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
    CHECKS,
    Check,
    MatchCriterion,
    Rule,
    clear_registry,
    load_checks,
    load_rules,
    loaded_check_files,
    register_check,
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
    print_rules,
    print_registry,
)
from .rules import warn_missing_rule_columns, warn_shadowed_rules
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
    OK,
    PASSED,
    SKIPPED,
    Status,
    CheckOutcome,
    Verdict,
    normalize_verdict,
    render_status,
)
from .tables import format_table, is_null

__all__ = [
    "CHECKS",
    "Check",
    "CheckOutcome",
    "DISABLED",
    "ERRORED",
    "FAILED",
    "MatchCriterion",
    "OK",
    "PASSED",
    "RowContext",
    "Rule",
    "SKIPPED",
    "Status",
    "Verdict",
    "build_report",
    "clear_registry",
    "escape_for_spreadsheet",
    "explain_row",
    "format_table",
    "get_registry_table",
    "is_null",
    "list_rule_codes",
    "load_checks",
    "load_rules",
    "loaded_check_files",
    "normalize_verdict",
    "print_registry",
    "print_report",
    "print_row_explanation",
    "print_rules",
    "print_summary",
    "register_check",
    "render_comments",
    "render_report",
    "render_status",
    "resolve_enabled_state",
    "root_cause_counts",
    "root_causes",
    "row_explanation",
    "summarize_outcomes",
    "validate",
    "validate_registry",
    "validate_row",
    "__version__",
    "warn_missing_rule_columns",
    "warn_shadowed_rules",
    "write_report",
]
