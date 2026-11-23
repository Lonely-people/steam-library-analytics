"""Purchase-record routes and the purchases page."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, render_template, request

from services import purchase_service
from services.purchase_service import PurchaseError

bp = Blueprint("purchases", __name__)


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _json_default(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _purchase_to_dict(purchase: purchase_service.Purchase) -> dict[str, Any]:
    return {
        "purchase_id": purchase.purchase_id,
        "game_id": purchase.game_id,
        "game_name": purchase.game_name,
        "purchase_date": (
            purchase.purchase_date.isoformat() if purchase.purchase_date else None
        ),
        "paid_amount": str(purchase.paid_amount),
        "effective_amount": str(purchase.effective_amount),
        "purchase_type": purchase.purchase_type,
        "status": purchase.status,
        "notes": purchase.notes,
    }


def _cost_to_dict(summary: purchase_service.CostSummary) -> dict[str, Any]:
    per_hour = summary.cost_per_hour
    return {
        "game_id": getattr(summary, "game_id", None),
        "game_name": summary.game_name,
        "record_count": summary.record_count,
        "records_complete": summary.records_complete,
        "net_paid": str(summary.net_paid),
        "refunded_total": str(summary.refunded_total),
        "play_minutes": summary.play_minutes,
        "acquisition_type": summary.acquisition_type,
        "cost_state": summary.cost_state,
        "cost_per_hour": str(per_hour) if per_hour is not None else None,
    }


# --- page -------------------------------------------------------------------


@bp.get("/purchases")
def purchases_page():
    return render_template("purchases.html")


# --- API --------------------------------------------------------------------


@bp.get("/api/purchases")
def list_purchases():
    game_id = request.args.get("game_id")
    if game_id is not None:
        try:
            game_id = int(game_id)
        except ValueError:
            return _error("game_id must be an integer", 400)
    items = purchase_service.list_purchases(game_id=game_id)
    return jsonify({"items": [_purchase_to_dict(p) for p in items]})


@bp.post("/api/purchases")
def create_purchase():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("request body must be a JSON object", 400)
    try:
        purchase = purchase_service.create_purchase(data)
    except purchase_service.PurchaseValidationError as exc:
        return _error(exc.message, 400)
    return jsonify(_purchase_to_dict(purchase)), 201


@bp.put("/api/purchases/<int:purchase_id>")
def update_purchase(purchase_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("request body must be a JSON object", 400)
    try:
        purchase = purchase_service.update_purchase(purchase_id, data)
    except purchase_service.PurchaseNotFoundError as exc:
        return _error(exc.message, 404)
    except purchase_service.PurchaseValidationError as exc:
        return _error(exc.message, 400)
    return jsonify(_purchase_to_dict(purchase))


@bp.delete("/api/purchases/<int:purchase_id>")
def delete_purchase(purchase_id: int):
    try:
        purchase_service.delete_purchase(purchase_id)
    except purchase_service.PurchaseNotFoundError as exc:
        return _error(exc.message, 404)
    return jsonify({"deleted": purchase_id})


@bp.get("/api/games/<int:game_id>/cost")
def game_cost(game_id: int):
    try:
        summary = purchase_service.cost_summary(game_id)
    except purchase_service.PurchaseNotFoundError as exc:
        return _error(exc.message, 404)
    payload = _cost_to_dict(summary)
    payload["game_id"] = game_id
    return jsonify(payload)


def register_error_handlers(app) -> None:
    @app.errorhandler(PurchaseError)
    def _handle_purchase_error(exc: PurchaseError):
        return _error(exc.message, 400)
