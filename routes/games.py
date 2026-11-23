"""Game and sync routes.

Routes only read HTTP input, call the service layer and shape the JSON
reply. All database access is parameterised inside the services.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from services import game_service
from services.game_service import GameError

bp = Blueprint("games", __name__, url_prefix="/api")


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _game_to_dict(game: game_service.GameRecord) -> dict[str, Any]:
    return {
        "game_id": game.game_id,
        "steam_appid": game.steam_appid,
        "game_name": game.game_name,
        "developer": game.developer,
        "image_url": game.image_url,
        "is_free_to_play": game.is_free_to_play,
        "source": game.source,
        "play_minutes": game.play_minutes,
        "acquisition_type": game.acquisition_type,
        "completion_status": game.completion_status,
        "progress_percent": game.progress_percent,
        "purchase_records_complete": game.purchase_records_complete,
        "is_hidden": game.is_hidden,
        "purchase_count": game.purchase_count,
    }


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes")


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@bp.get("/games")
def list_games():
    try:
        limit = _as_int(request.args.get("limit"), 50)
        offset = _as_int(request.args.get("offset"), 0)
        games, total = game_service.list_games(
            search=request.args.get("search"),
            source=request.args.get("source"),
            acquisition_type=request.args.get("acquisition_type"),
            completion_status=request.args.get("completion_status"),
            include_hidden=_as_bool(request.args.get("include_hidden")),
            limit=limit,
            offset=offset,
        )
    except game_service.GameValidationError as exc:
        return _error(exc.message, 400)

    return jsonify(
        {
            "items": [_game_to_dict(g) for g in games],
            "total": total,
            "limit": max(1, min(limit, 200)),
            "offset": max(0, offset),
        }
    )


@bp.post("/games")
def create_game():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("request body must be a JSON object", 400)
    try:
        game = game_service.create_game(data)
    except game_service.GameValidationError as exc:
        return _error(exc.message, 400)
    return jsonify(_game_to_dict(game)), 201


@bp.get("/games/<int:game_id>")
def get_game(game_id: int):
    try:
        game = game_service.get_game(game_id)
    except game_service.GameNotFoundError as exc:
        return _error(exc.message, 404)
    return jsonify(_game_to_dict(game))


@bp.put("/games/<int:game_id>")
def update_game(game_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("request body must be a JSON object", 400)
    try:
        game = game_service.update_game(game_id, data)
    except game_service.GameNotFoundError as exc:
        return _error(exc.message, 404)
    except game_service.GameValidationError as exc:
        return _error(exc.message, 400)
    return jsonify(_game_to_dict(game))


@bp.delete("/games/<int:game_id>")
def delete_game(game_id: int):
    try:
        outcome = game_service.delete_game(
            game_id, force=_as_bool(request.args.get("force"))
        )
    except game_service.GameNotFoundError as exc:
        return _error(exc.message, 404)
    except game_service.GameConflictError as exc:
        return _error(exc.message, 409)
    return jsonify({"outcome": outcome, "game_id": game_id})


@bp.get("/steam/sync-logs")
def sync_logs():
    limit = _as_int(request.args.get("limit"), 10)
    return jsonify({"items": game_service.sync_logs(limit=max(1, min(limit, 100)))})


@bp.post("/steam/sync")
def trigger_sync():
    from services import sync_service

    result = sync_service.sync_steam_library()
    payload = {
        "status": result.status,
        "fetched_count": result.fetched_count,
        "created_count": result.created_count,
        "updated_count": result.updated_count,
        "message": result.message,
        "sync_id": result.sync_id,
    }
    return jsonify(payload), (200 if result.status == "success" else 502)


def register_error_handlers(app) -> None:
    """Keep database exceptions out of HTTP responses."""

    @app.errorhandler(GameError)
    def _handle_game_error(exc: GameError):
        return _error(exc.message, 400)
