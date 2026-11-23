"""Statistics API and the analytics/dashboard pages."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from services import stats_service

bp = Blueprint("statistics", __name__)


@bp.get("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@bp.get("/analytics")
def analytics_page():
    return render_template("analytics.html")


@bp.get("/api/stats/overview")
def overview():
    return jsonify(stats_service.overview().__dict__)


@bp.get("/api/stats/genres")
def genres():
    return jsonify({"items": stats_service.genre_breakdown()})


@bp.get("/api/stats/costs")
def costs():
    order = request.args.get("order", "expensive")
    if order not in ("expensive", "cheap"):
        return jsonify({"error": "order must be expensive or cheap"}), 400
    return jsonify(stats_service.cost_ranking(order=order))


@bp.get("/api/stats/yearly")
def yearly():
    items = stats_service.yearly_spend()
    return jsonify({
        "items": items,
        "undated_records": stats_service.undated_purchase_count(),
    })
