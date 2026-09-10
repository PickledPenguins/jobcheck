"""Unit tests: RowContext and the build_context integration stub."""

from __future__ import annotations

import pandas as pd
import pytest

from pandas_row_validation import RowContext, build_context

pytestmark = pytest.mark.fast


def test_row_context_defaults_to_four_empty_dicts() -> None:
    context = RowContext()
    assert (context.flags, context.paths, context.state, context.extra) == ({}, {}, {}, {})


def test_row_context_instances_do_not_share_their_dicts() -> None:
    first = RowContext()
    first.flags["x"] = 1
    assert RowContext().flags == {}


def test_build_context_flags_a_legacy_source_system() -> None:
    context = build_context(pd.Series({"source_system": "LEGACY_A"}))
    assert context.flags == {"legacy": True}


def test_build_context_does_not_flag_other_source_systems() -> None:
    assert build_context(pd.Series({"source_system": "MODERN"})).flags == {"legacy": False}


def test_build_context_handles_a_null_source_system() -> None:
    assert build_context(pd.Series({"source_system": None})).flags == {"legacy": False}


def test_build_context_without_the_column_sets_no_flag() -> None:
    assert build_context(pd.Series({"age": 30})).flags == {}


def test_build_context_leaves_the_other_buckets_empty() -> None:
    context = build_context(pd.Series({"source_system": "LEGACY_A"}))
    assert (context.paths, context.state, context.extra) == ({}, {}, {})
