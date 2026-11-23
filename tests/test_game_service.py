"""Unit tests for game-service helpers that need no database."""

import pytest

from services import game_service


def test_clean_name_strips_and_rejects_blank():
    assert game_service._clean_name("  Hades  ") == "Hades"
    with pytest.raises(game_service.GameValidationError):
        game_service._clean_name("   ")
    with pytest.raises(game_service.GameValidationError):
        game_service._clean_name(None)
    with pytest.raises(game_service.GameValidationError):
        game_service._clean_name("x" * 256)


def test_clean_optional_str_returns_none_for_blank():
    assert game_service._clean_optional_str("", max_len=10, field="developer") is None
    assert game_service._clean_optional_str("  ", max_len=10, field="developer") is None
    assert game_service._clean_optional_str("Nintendo", max_len=10, field="developer") == "Nintendo"


def test_clean_optional_str_rejects_too_long():
    with pytest.raises(game_service.GameValidationError):
        game_service._clean_optional_str("x" * 11, max_len=10, field="developer")


def test_validate_progress_bounds():
    assert game_service._validate_progress(None) is None
    assert game_service._validate_progress(0) == 0
    assert game_service._validate_progress(100) == 100
    for bad in (-1, 101, True, "50", 12.5):
        with pytest.raises(game_service.GameValidationError):
            game_service._validate_progress(bad)


def test_enum_constants_match_schema_checks():
    assert set(game_service.ACQUISITION_TYPES) == {
        "unknown", "paid", "free_to_play", "free_claimed", "gift",
    }
    assert set(game_service.COMPLETION_STATUSES) == {
        "unknown", "playing", "completed", "abandoned", "not_applicable",
    }


def test_list_select_joins_entries_and_counts_purchases():
    sql = game_service._LIST_SELECT
    assert "LEFT JOIN steam.library_entries" in sql
    assert "count(*)" in sql
