"""Row-validation framework.

Importing this package registers **no** checks: an entry point calls
`load_checks` with the files it wants, and `load_rules` with the rule files
that switch individual checks on or off for chosen rows.
"""

from __future__ import annotations

__version__ = "0.2.0"
"""Pre-1.0: the API may change between versions. Check codes, status values and
the rule YAML schema are permanent -- data written against them outlives the
code."""

from .context import RowContext
from .registry import (
    clear_registry,
    load_checks,
    load_setup,
    load_rules,
    register_check,
    warn_blocking_rules,
)
from .engine import validate
from .rules import Rule, warn_missing_rule_columns, warn_shadowed_rules
from .views import (
    build_report,
    explain_row,
    registry_table,
    rules_table,
    summarize_outcomes,
)
from .results import OK, CheckOutcome, Outcome, Status, Verdict
from .tables import is_null

__all__ = [
    "CheckOutcome",
    "OK",
    "Outcome",
    "RowContext",
    "Rule",
    "Status",
    "Verdict",
    "build_report",
    "clear_registry",
    "explain_row",
    "is_null",
    "load_checks",
    "load_rules",
    "load_setup",
    "register_check",
    "registry_table",
    "rules_table",
    "summarize_outcomes",
    "validate",
    "__version__",
    "warn_blocking_rules",
    "warn_missing_rule_columns",
    "warn_shadowed_rules",
]
