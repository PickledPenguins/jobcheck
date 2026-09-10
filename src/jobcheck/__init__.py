"""Row-validation framework.

Importing this package registers **no** checks. Each entry point calls
:func:`jobcheck.load_checks` with the paths of the ``check_*.py`` files it
wants, and :func:`jobcheck.load_overrides` with the rule files that switch
individual checks off for chosen rows.
"""

from __future__ import annotations

__version__ = "0.2.0"
"""Pre-1.0: the API may change between versions. Check codes, status values and the
override YAML schema are the parts treated as permanent, since data written against
them outlives the code."""

from .context import RowContext, build_context
from .registry import (
    CHECKS,
    Check,
    MatchCriterion,
    OverrideRule,
    clear_registry,
    load_checks,
    load_overrides,
    loaded_files,
    register_check,
    validate_registry,
)
from .engine import (
    explain_row,
    resolve_enabled_state,
    root_cause,
    root_causes,
    validate,
    validate_row,
)
from .registry_tables import (
    get_registry_table,
    list_rule_codes,
    print_override_rules,
    print_registry,
    print_registry_with_overrides,
)
from .rules import check_rule_columns
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
    summarise_outcomes,
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
    normalise_result,
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
    "build_context",
    "build_report",
    "check_rule_columns",
    "clear_registry",
    "escape_for_spreadsheet",
    "explain_row",
    "format_table",
    "get_registry_table",
    "is_null",
    "list_rule_codes",
    "load_checks",
    "load_overrides",
    "loaded_files",
    "normalise_result",
    "print_override_rules",
    "print_registry",
    "print_registry_with_overrides",
    "print_report",
    "print_row_explanation",
    "print_summary",
    "register_check",
    "render_comments",
    "render_report",
    "render_status",
    "resolve_enabled_state",
    "root_cause",
    "root_cause_counts",
    "root_causes",
    "row_explanation",
    "summarise_outcomes",
    "validate",
    "validate_registry",
    "validate_row",
    "write_report",
]
