"""Steam library synchronisation into openGauss.

Design constraints from PLAN.md that this module enforces:

* Game and library-entry writes happen in a single transaction: either
  every game of a sync is written or none of them.
* A failed or empty upstream result must never delete local rows.
* Only Steam-owned fields are updated on existing rows; user-maintained
  fields (acquisition type, completion status, progress, purchases) are
  preserved.
* Every attempt is recorded in sync_logs, including failures, with no key
  or password in the message.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import psycopg2

from database.db import get_connection
from services import steam_api
from services.steam_api import OwnedGame

logger = logging.getLogger(__name__)

# openGauss does not support PostgreSQL's ON CONFLICT, so upserts use the
# MySQL-style ON DUPLICATE KEY UPDATE that its A compatibility mode accepts.
# The conflict is resolved on the UNIQUE steam_appid column, so game_id is
# preserved for existing games.
UPSERT_GAME_SQL = """
INSERT INTO steam.games (steam_appid, game_name, image_url, source)
VALUES (%s, %s, %s, 'steam')
ON DUPLICATE KEY UPDATE
    game_name = EXCLUDED.game_name,
    image_url = COALESCE(EXCLUDED.image_url, steam.games.image_url),
    updated_at = now()
RETURNING game_id
"""

UPSERT_ENTRY_SQL = """
INSERT INTO steam.library_entries (game_id, play_minutes, last_synced_at)
VALUES (%s, %s, now())
ON DUPLICATE KEY UPDATE
    play_minutes = EXCLUDED.play_minutes,
    last_synced_at = now(),
    updated_at = now()
"""


@dataclass
class SyncResult:
    """Outcome of a sync attempt."""

    status: str  # 'success' | 'failed'
    fetched_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    message: str | None = None
    sync_id: int | None = None


def _icon_url(game: OwnedGame) -> str | None:
    if not game.img_icon_url:
        return None
    return (
        "https://media.steampowered.com/steamcommunity/public/images/apps/"
        f"{game.appid}/{game.img_icon_url}.jpg"
    )


def _record_running_log() -> int:
    """Commit a 'running' log row before touching game data."""
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO steam.sync_logs (status) VALUES ('running') RETURNING sync_id"
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _finish_log(sync_id: int, status: str, fetched_count: int, message: str | None) -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE steam.sync_logs "
                "SET status = %s, fetched_count = %s, message = %s, "
                "sync_finished_at = now() WHERE sync_id = %s",
                (status, fetched_count, message, sync_id),
            )
    finally:
        conn.close()


def upsert_games(cur, games: Iterable[OwnedGame]) -> tuple[int, int]:
    """Write games + library entries on an existing cursor.

    Returns (created, updated) counts, where ``created`` counts games that
    did not exist before this sync.
    """
    created = 0
    updated = 0
    for game in games:
        cur.execute(
            "SELECT game_id FROM steam.games WHERE steam_appid = %s",
            (game.appid,),
        )
        if cur.fetchone() is None:
            created += 1
        else:
            updated += 1

        cur.execute(UPSERT_GAME_SQL, (game.appid, game.name, _icon_url(game)))
        game_id = cur.fetchone()[0]
        cur.execute(UPSERT_ENTRY_SQL, (game_id, game.play_minutes))
    return created, updated


def sync_steam_library() -> SyncResult:
    """Fetch owned games from Steam and persist them.

    The running log row is committed first so a crash mid-sync still leaves
    a trace. Game writes then run in their own transaction; on any failure
    that transaction is rolled back and the log is marked failed in a
    separate commit, so partial data never survives.
    """
    sync_id = _record_running_log()

    try:
        fetched = steam_api.fetch_owned_games()
    except steam_api.SteamAPIError as exc:
        _finish_log(sync_id, "failed", 0, exc.message)
        logger.warning("steam sync failed: %s", exc.message)
        return SyncResult(status="failed", message=exc.message, sync_id=sync_id)

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            created, updated = upsert_games(cur, fetched.games)
    except psycopg2.Error as exc:
        message = f"database write failed ({type(exc).__name__})"
        _finish_log(sync_id, "failed", 0, message)
        logger.error("steam sync db failure: %s", message)
        return SyncResult(status="failed", message=message, sync_id=sync_id)
    finally:
        conn.close()

    _finish_log(sync_id, "success", len(fetched.games), None)
    return SyncResult(
        status="success",
        fetched_count=len(fetched.games),
        created_count=created,
        updated_count=updated,
        sync_id=sync_id,
    )


def latest_sync_logs(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent sync log rows (newest first) for display."""
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT sync_id, sync_started_at, sync_finished_at, status, "
                "fetched_count, message FROM steam.sync_logs "
                "ORDER BY sync_id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "sync_id": r[0],
            "sync_started_at": r[1],
            "sync_finished_at": r[2],
            "status": r[3],
            "fetched_count": r[4],
            "message": r[5],
        }
        for r in rows
    ]
