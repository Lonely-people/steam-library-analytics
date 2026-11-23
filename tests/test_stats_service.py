"""Unit tests for statistics helpers that need no database."""

from decimal import Decimal

from services import stats_service


def test_money_normalises_to_two_decimals():
    assert stats_service._money(None) == "0.00"
    assert stats_service._money(0) == "0.00"
    assert stats_service._money(Decimal(12)) == "12.00"
    assert stats_service._money(Decimal("12.345")) == "12.35"


def test_rate_returns_none_for_zero_denominator():
    assert stats_service._rate(0, 0) is None
    assert stats_service._rate(1, 0) is None


def test_rate_computes_percentage():
    assert stats_service._rate(1, 4) == 25.0
    assert stats_service._rate(1, 3) == 33.33


def test_completed_statuses_exclude_unknown_and_not_applicable():
    assert set(stats_service._COMPLETED_STATUSES) == {"playing", "completed", "abandoned"}
    assert "unknown" not in stats_service._COMPLETED_STATUSES
    assert "not_applicable" not in stats_service._COMPLETED_STATUSES


def test_net_paid_sql_excludes_refunds():
    assert "status = 'paid'" in stats_service._NET_PAID_SQL


def test_visible_entries_scope_is_non_hidden():
    assert "is_hidden" in stats_service._VISIBLE_ENTRIES
    assert "FALSE" in stats_service._VISIBLE_ENTRIES
