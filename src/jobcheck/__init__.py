"""Row-validation framework.

Importing this package registers **no** checks. Each entry point calls
:func:`jobcheck.load_suites` to choose which suites of checks it wants;
``check_*.py`` files sitting directly in your package are always loaded.
"""

from __future__ import annotations

__version__ = "0.1.0"
"""Pre-1.0: the API may change between versions. Check codes, status values and the
override YAML schema are the parts treated as permanent, since data written against
them outlives the code."""

from .context import RowContext, build_context
from .registry import (
    BASE_SUITE,
    CHECKS,
    Check,
    CheckGroup,
    MatchCriterion,
    OverrideRule,
    check_group,
    clear_registry,
    load_checks,
    load_overrides,
    load_overrides_from_dir,
    load_overrides_from_files,
    load_suites,
    loaded_files,
    loaded_suites,
    register_check,
    validate_registry,
)
from .engine import (
    explain_row,
    resolve_enabled_state,
    root_cause,
    root_causes,
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
    collect_outcomes,
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
    all_statuses,
    clear_extra_statuses,
    normalise_result,
    register_status,
    render_status,
    status_name,
)
from .run import RowTrace, RunStats, ValidationRun, iter_traces, validate
from .tables import format_table, is_null

__all__ = [
    "BASE_SUITE",
    "CHECKS",
    "Check",
    "CheckGroup",
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
    "RowTrace",
    "RunStats",
    "SKIPPED",
    "Status",
    "ValidationRun",
    "__version__",
    "all_statuses",
    "build_context",
    "build_report",
    "check_group",
    "check_rule_columns",
    "clear_extra_statuses",
    "clear_registry",
    "collect_outcomes",
    "escape_for_spreadsheet",
    "explain_row",
    "format_table",
    "get_registry_table",
    "is_null",
    "iter_traces",
    "list_rule_codes",
    "load_checks",
    "load_overrides",
    "load_overrides_from_dir",
    "load_overrides_from_files",
    "load_suites",
    "loaded_files",
    "loaded_suites",
    "normalise_result",
    "print_override_rules",
    "print_registry",
    "print_registry_with_overrides",
    "print_report",
    "print_row_explanation",
    "print_summary",
    "register_check",
    "register_status",
    "render_comments",
    "render_report",
    "render_status",
    "resolve_enabled_state",
    "root_cause",
    "root_cause_counts",
    "root_causes",
    "row_explanation",
    "status_name",
    "summarise_outcomes",
    "validate",
    "validate_registry",
    "validate_row",
    "write_report",
]
