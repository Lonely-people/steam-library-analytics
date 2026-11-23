"""Game catalogue service: listing, search, filtering and CRUD.

Business rules enforced here (from PLAN.md / CLAUDE.md):

* A Steam-synced game cannot be deleted from the local library; it is
  hidden instead, so the next sync does not bring it back. A manually
  added game can be deleted outright.
* ``games.is_free_to_play`` (store flag) and
  ``library_entries.acquisition_type`` (how the user obtained it) stay
  separate and are never derived from one another.
* Deleting a game with purchase records requires an explicit flag, because
  purchase data is user-entered and not recoverable from Steam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from database.db import get_connection

SOURCE_STEAM = "steam"
SOURCE_MANUAL = "manual"

ACQUISITION_TYPES = ("unknown", "paid", "free_to_play", "free_claimed", "gift")
COMPLETION_STATUSES = ("unknown", "playing", "completed", "abandoned", "not_applicable")


class GameError(Exception):
    """Base class for game-service errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class GameValidationError(GameError):
    """Raised when request data fails validation."""


class GameNotFoundError(GameError):
    """Raised when a game id does not exist."""


class GameConflictError(GameError):
    """Raised when an operation is not allowed, e.g. deleting a Steam game."""


@dataclass(frozen=True)
class GameRecord:
    game_id: int
    steam_appid: int | None
    game_name: str
    developer: str | None
    image_url: str | None
    is_free_to_play: bool | None
    source: str
    play_minutes: int
    acquisition_type: str
    completion_status: str
    progress_percent: int | None
    purchase_records_complete: bool
    is_hidden: bool
    purchase_count: int


_LIST_SELECT = """
SELECT g.game_id, g.steam_appid, g.game_name, g.developer, g.image_url,
       g.is_free_to_play, g.source,
       COALESCE(e.play_minutes, 0), COALESCE(e.acquisition_type, 'unknown'),
       COALESCE(e.completion_status, 'unknown'), e.progress_percent,
       COALESCE(e.purchase_records_complete, FALSE),
       COALESCE(e.is_hidden, FALSE),
       COALESCE((SELECT count(*) FROM steam.purchases p
                 WHERE p.library_id = e.library_id), 0)
FROM steam.games g
LEFT JOIN steam.library_entries e ON e.game_id = g.game_id
"""


def _row_to_record(row) -> GameRecord:
    return GameRecord(
        game_id=row[0],
        steam_appid=row[1],
        game_name=row[2],
        developer=row[3],
        image_url=row[4],
        is_free_to_play=row[5],
        source=row[6],
        play_minutes=row[7],
        acquisition_type=row[8],
        completion_status=row[9],
        progress_percent=row[10],
        purchase_records_complete=row[11],
        is_hidden=row[12],
        purchase_count=row[13],
    )


def list_games(
    *,
    search: str | None = None,
    source: str | None = None,
    acquisition_type: str | None = None,
    completion_status: str | None = None,
    include_hidden: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GameRecord], int]:
    """Return (page of games, total matching count).

    Search is a case-insensitive substring match on the game name. Hidden
    games are excluded unless explicitly requested.
    """
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    conditions: list[str] = []
    params: list[Any] = []

    if not include_hidden:
        conditions.append("COALESCE(e.is_hidden, FALSE) = FALSE")
    if search:
        conditions.append("g.game_name ILIKE %s")
        params.append(f"%{search.strip()}%")
    if source:
        if source not in (SOURCE_STEAM, SOURCE_MANUAL):
            raise GameValidationError("invalid source filter")
        conditions.append("g.source = %s")
        params.append(source)
    if acquisition_type:
        if acquisition_type not in ACQUISITION_TYPES:
            raise GameValidationError("invalid acquisition_type filter")
        conditions.append("e.acquisition_type = %s")
        params.append(acquisition_type)
    if completion_status:
        if completion_status not in COMPLETION_STATUSES:
            raise GameValidationError("invalid completion_status filter")
        conditions.append("e.completion_status = %s")
        params.append(completion_status)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM ({_LIST_SELECT}{where}) AS filtered", params)
            total = cur.fetchone()[0]
            cur.execute(
                f"{_LIST_SELECT}{where} ORDER BY g.game_name LIMIT %s OFFSET %s",
                [*params, limit, offset],
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [_row_to_record(r) for r in rows], total


def get_game(game_id: int) -> GameRecord:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"{_LIST_SELECT} WHERE g.game_id = %s", (game_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        raise GameNotFoundError("game not found")
    return _row_to_record(row)


def _clean_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise GameValidationError("game_name is required")
    name = name.strip()
    if len(name) > 255:
        raise GameValidationError("game_name is too long (max 255)")
    return name


def _clean_optional_str(value: Any, *, max_len: int, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GameValidationError(f"{field} must be a string")
    value = value.strip()
    if not value:
        return None
    if len(value) > max_len:
        raise GameValidationError(f"{field} is too long (max {max_len})")
    return value


def create_game(data: dict[str, Any]) -> GameRecord:
    """Create a manual game plus its library entry in one transaction."""
    name = _clean_name(data.get("game_name"))
    developer = _clean_optional_str(data.get("developer"), max_len=255, field="developer")
    acquisition = data.get("acquisition_type", "unknown")
    if acquisition not in ACQUISITION_TYPES:
        raise GameValidationError("invalid acquisition_type")
    completion = data.get("completion_status", "unknown")
    if completion not in COMPLETION_STATUSES:
        raise GameValidationError("invalid completion_status")

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO steam.games (game_name, developer, source) "
                "VALUES (%s, %s, 'manual') RETURNING game_id",
                (name, developer),
            )
            game_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO steam.library_entries (game_id, acquisition_type, "
                "completion_status) VALUES (%s, %s, %s)",
                (game_id, acquisition, completion),
            )
    finally:
        conn.close()
    return get_game(game_id)


def _validate_progress(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise GameValidationError("progress_percent must be an integer or null")
    if not 0 <= value <= 100:
        raise GameValidationError("progress_percent must be between 0 and 100")
    return value


def update_game(game_id: int, data: dict[str, Any]) -> GameRecord:
    """Update user-maintained fields only.

    Steam-owned columns (steam_appid, source) are never writable here, and
    play_minutes is owned by sync.
    """
    current = get_game(game_id)

    name = _clean_name(data["game_name"]) if "game_name" in data else current.game_name
    developer = current.developer
    if "developer" in data:
        developer = _clean_optional_str(data["developer"], max_len=255, field="developer")

    acquisition = data.get("acquisition_type", current.acquisition_type)
    if acquisition not in ACQUISITION_TYPES:
        raise GameValidationError("invalid acquisition_type")
    completion = data.get("completion_status", current.completion_status)
    if completion not in COMPLETION_STATUSES:
        raise GameValidationError("invalid completion_status")
    progress = (
        _validate_progress(data.get("progress_percent"))
        if "progress_percent" in data
        else current.progress_percent
    )
    complete_flag = data.get("purchase_records_complete", current.purchase_records_complete)
    if not isinstance(complete_flag, bool):
        raise GameValidationError("purchase_records_complete must be a boolean")
    hidden = data.get("is_hidden", current.is_hidden)
    if not isinstance(hidden, bool):
        raise GameValidationError("is_hidden must be a boolean")

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE steam.games SET game_name = %s, developer = %s, "
                "updated_at = now() WHERE game_id = %s",
                (name, developer, game_id),
            )
            # Manual games created before their library entry exists are
            # covered by an upsert-like guard.
            cur.execute(
                "UPDATE steam.library_entries SET acquisition_type = %s, "
                "completion_status = %s, progress_percent = %s, "
                "purchase_records_complete = %s, is_hidden = %s, "
                "updated_at = now() WHERE game_id = %s",
                (acquisition, completion, progress, complete_flag, hidden, game_id),
            )
            if cur.rowcount == 0:
                cur.execute(
                    "INSERT INTO steam.library_entries (game_id, acquisition_type, "
                    "completion_status, progress_percent, purchase_records_complete, "
                    "is_hidden) VALUES (%s, %s, %s, %s, %s, %s)",
                    (game_id, acquisition, completion, progress, complete_flag, hidden),
                )
    finally:
        conn.close()
    return get_game(game_id)


def delete_game(game_id: int, *, force: bool = False) -> str:
    """Delete a manual game, or hide a Steam game.

    Returns ``'deleted'`` or ``'hidden'``. Raises GameConflictError when a
    manual game has purchase records and ``force`` is not set.
    """
    current = get_game(game_id)

    if current.source == SOURCE_STEAM:
        conn = get_connection()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE steam.library_entries SET is_hidden = TRUE, "
                    "updated_at = now() WHERE game_id = %s",
                    (game_id,),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        "INSERT INTO steam.library_entries (game_id, is_hidden) "
                        "VALUES (%s, TRUE)",
                        (game_id,),
                    )
        finally:
            conn.close()
        return "hidden"

    if current.purchase_count > 0 and not force:
        raise GameConflictError(
            "game has purchase records; resend with force=true to delete them too"
        )

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM steam.games WHERE game_id = %s", (game_id,))
    finally:
        conn.close()
    return "deleted"


def sync_logs(limit: int = 10) -> list[dict[str, Any]]:
    """Small pass-through so routes do not import the sync service directly."""
    from services.sync_service import latest_sync_logs

    return latest_sync_logs(limit=limit)
