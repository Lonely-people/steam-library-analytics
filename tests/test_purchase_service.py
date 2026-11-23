"""Unit tests for purchase-service validation that need no database."""

from decimal import Decimal

import pytest

from services import purchase_service


def test_parse_date_accepts_iso_and_null():
    assert purchase_service._parse_date("2025-03-14").isoformat() == "2025-03-14"
    assert purchase_service._parse_date(None) is None
    assert purchase_service._parse_date("") is None


@pytest.mark.parametrize("bad", ["2025-13-40", "14/03/2025", "2025-03-14T10:00:00"])
def test_parse_date_rejects_invalid(bad):
    with pytest.raises(purchase_service.PurchaseValidationError):
        purchase_service._parse_date(bad)


def test_parse_amount_rules():
    assert purchase_service._parse_amount("19.99") == Decimal("19.99")
    assert purchase_service._parse_amount(0) == Decimal("0.00")
    for bad in ("-1", "1.234", "", None, True, "abc"):
        with pytest.raises(purchase_service.PurchaseValidationError):
            purchase_service._parse_amount(bad)


def test_clean_type_and_status():
    assert purchase_service._clean_type(None) == "base"
    assert purchase_service._clean_type("dlc") == "dlc"
    assert purchase_service._clean_status(None) == "paid"
    assert purchase_service._clean_status("refunded") == "refunded"
    with pytest.raises(purchase_service.PurchaseValidationError):
        purchase_service._clean_type("bundle")
    with pytest.raises(purchase_service.PurchaseValidationError):
        purchase_service._clean_status("pending")


def test_cost_state_unknown_when_records_incomplete():
    summary = purchase_service.CostSummary(
        library_id=1, game_name="X", records_complete=False, record_count=0,
        net_paid=Decimal("0.00"), refunded_total=Decimal("0.00"),
        play_minutes=0, acquisition_type="paid",
    )
    assert summary.cost_state == "unknown", "missing records must not mean free"
    assert summary.cost_per_hour is None


def test_cost_state_free_for_zero_cost_complete_record():
    summary = purchase_service.CostSummary(
        library_id=1, game_name="X", records_complete=True, record_count=0,
        net_paid=Decimal("0.00"), refunded_total=Decimal("0.00"),
        play_minutes=10, acquisition_type="free_to_play",
    )
    assert summary.cost_state == "free"


def test_cost_per_hour_avoids_division_by_zero():
    summary = purchase_service.CostSummary(
        library_id=1, game_name="X", records_complete=True, record_count=1,
        net_paid=Decimal("60.00"), refunded_total=Decimal("0.00"),
        play_minutes=0, acquisition_type="paid",
    )
    assert summary.cost_per_hour is None


def test_cost_per_hour_calculation_and_scale():
    summary = purchase_service.CostSummary(
        library_id=1, game_name="X", records_complete=True, record_count=1,
        net_paid=Decimal("98.00"), refunded_total=Decimal("0.00"),
        play_minutes=120, acquisition_type="paid",
    )
    assert summary.cost_per_hour == Decimal("49.00")


def test_amounts_are_normalised_to_two_decimals():
    # Decimal("0") has scale 0, which is exactly what SUM() over no rows
    # returns; the dataclass must normalise it.
    summary = purchase_service.CostSummary(
        library_id=1, game_name="X", records_complete=True, record_count=0,
        net_paid=Decimal("0"), refunded_total=Decimal("0"),  # noqa: FURB157
        play_minutes=0, acquisition_type="free_to_play",
    )
    assert str(summary.net_paid) == "0.00"
    assert str(summary.refunded_total) == "0.00"


def test_refunded_purchase_has_zero_effective_amount():
    purchase = purchase_service.Purchase(
        purchase_id=1, library_id=1, game_id=1, game_name="X", purchase_date=None,
        paid_amount=Decimal("68.00"), purchase_type="base", status="refunded", notes=None,
    )
    assert purchase.effective_amount == Decimal("0.00")
