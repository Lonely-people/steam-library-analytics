"""Unit tests for sync-service helpers that do not need a database.

Transaction and idempotency behaviour is exercised against the real
openGauss instance by tests/sync_check.py; these tests cover pure logic.
"""

from services import sync_service
from services.steam_api import OwnedGame


def test_icon_url_builds_steam_media_path():
    game = OwnedGame(appid=440, name="TF2", playtime_forever=0, img_icon_url="abc123")

    assert (
        sync_service._icon_url(game)
        == "https://media.steampowered.com/steamcommunity/public/images/apps/440/abc123.jpg"
    )


def test_icon_url_is_none_when_missing():
    game = OwnedGame(appid=1, name="x", playtime_forever=0, img_icon_url=None)

    assert sync_service._icon_url(game) is None


def test_upsert_sql_uses_openGauss_syntax():
    # openGauss rejects ON CONFLICT; guard against a future accidental revert.
    assert "ON CONFLICT" not in sync_service.UPSERT_GAME_SQL
    assert "ON DUPLICATE KEY UPDATE" in sync_service.UPSERT_GAME_SQL
    assert "ON DUPLICATE KEY UPDATE" in sync_service.UPSERT_ENTRY_SQL


def test_game_upsert_preserves_existing_image_when_new_one_missing():
    assert "COALESCE(EXCLUDED.image_url, steam.games.image_url)" in (
        sync_service.UPSERT_GAME_SQL
    )


def test_entry_upsert_only_touches_steam_owned_fields():
    # User-maintained columns must never appear in the sync upsert.
    for column in (
        "acquisition_type",
        "completion_status",
        "progress_percent",
        "purchase_records_complete",
        "is_hidden",
    ):
        assert column not in sync_service.UPSERT_ENTRY_SQL
