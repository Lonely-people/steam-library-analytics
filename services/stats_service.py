"""Statistics aggregation, following the definitions in PLAN.md §7.

Definitions used here (not invented in the frontend):

* Library scope = non-hidden games.
* Unstarted rate = non-hidden games with 0 minutes / all non-hidden games.
* Uncompleted rate = only games the user explicitly classified; ``unknown``
  and ``not_applicable`` are excluded from the denominator.
* Genre share: a multi-genre game's minutes are split evenly across its
  genres so the total is not double counted; no genre means "uncategorised".
* Cost per hour and the idle-spend figures only include games whose purchase
  records are explicitly marked complete, with net paid > 0.
* Yearly spend groups by calendar year of purchase_date and counts only
  non-refunded amounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from database.db import get_connection

# Non-hidden scope reused by several aggregates.
_VISIBLE_ENTRIES = "COALESCE(e.is_hidden, FALSE) = FALSE"

# Net paid per library entry: refunds contribute nothing.
_NET_PAID_SQL = (
    "COALESCE((SELECT SUM(CASE WHEN p.status = 'paid' THEN p.paid_amount ELSE 0 END) "
    "FROM steam.purchases p WHERE p.library_id = e.library_id), 0)"
)

_COMPLETED_STATUSES = ("playing", "completed", "abandoned")


def _money(value: Any) -> str:
    # Money is displayed, so half-up matches what users expect; Python's
    # default (ROUND_HALF_EVEN) would turn 12.345 into 12.34.
    return str(Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator * 100.0 / denominator, 2)


@dataclass(frozen=True)
class Overview:
    total_games: int
    total_minutes: int
    known_spend: str
    incomplete_cost_games: int
    unstarted_count: int
    unstarted_rate: float | None
    completion_determined: int
    uncompleted_count: int
    uncompleted_rate: float | None
    status_unknown_count: int
    visible_games: int
    hidden_games: int


def overview() -> Overview:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"""
                SELECT
                    count(*) AS visible_games,
                    COALESCE(SUM(COALESCE(e.play_minutes, 0)), 0) AS total_minutes,
                    count(*) FILTER (WHERE COALESCE(e.play_minutes, 0) = 0) AS unstarted,
                    count(*) FILTER (WHERE e.purchase_records_complete = TRUE) AS complete_games,
                    count(*) FILTER (WHERE e.completion_status IN
                        ('playing','completed','abandoned')) AS determined,
                    count(*) FILTER (WHERE e.completion_status IN
                        ('playing','abandoned')) AS uncompleted,
                    count(*) FILTER (WHERE e.completion_status = 'unknown') AS unknown_status,
                    COALESCE(SUM(CASE WHEN e.purchase_records_complete = TRUE THEN
                        (SELECT COALESCE(SUM(CASE WHEN p.status='paid'
                            THEN p.paid_amount ELSE 0 END), 0)
                         FROM steam.purchases p WHERE p.library_id = e.library_id)
                        ELSE 0 END), 0) AS known_spend,
                    count(*) FILTER (WHERE COALESCE(e.purchase_records_complete, FALSE) = FALSE)
                        AS incomplete_games
                FROM steam.library_entries e
                JOIN steam.games g ON g.game_id = e.game_id
                WHERE {_VISIBLE_ENTRIES}
            """)
            row = cur.fetchone()

            cur.execute(
                "SELECT count(*) FROM steam.library_entries e "
                "JOIN steam.games g ON g.game_id = e.game_id "
                "WHERE COALESCE(e.is_hidden, FALSE) = TRUE"
            )
            hidden = cur.fetchone()[0]
    finally:
        conn.close()

    (visible, total_minutes, unstarted, _complete, determined, uncompleted,
     unknown_status, known_spend, incomplete) = row

    return Overview(
        total_games=int(visible),
        visible_games=int(visible),
        hidden_games=int(hidden),
        total_minutes=int(total_minutes),
        known_spend=_money(known_spend),
        incomplete_cost_games=int(incomplete),
        unstarted_count=int(unstarted),
        unstarted_rate=_rate(int(unstarted), int(visible)),
        completion_determined=int(determined),
        uncompleted_count=int(uncompleted),
        uncompleted_rate=_rate(int(uncompleted), int(determined)),
        status_unknown_count=int(unknown_status),
    )


def genre_breakdown() -> list[dict[str, Any]]:
    """Play minutes per genre, splitting multi-genre games evenly.

    A game with no genre contributes to a synthetic "uncategorised" bucket
    (genre_id 0) so the chart still accounts for all playtime.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"""
                SELECT e.game_id, COALESCE(e.play_minutes, 0) AS minutes,
                       gr.genre_id, gr.name_zh, gr.name_en
                FROM steam.library_entries e
                LEFT JOIN steam.game_genres gg ON gg.game_id = e.game_id
                LEFT JOIN steam.genres gr ON gr.genre_id = gg.genre_id
                WHERE {_VISIBLE_ENTRIES}
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    # Count genres per game inside the fetched rows so the split uses the
    # same data the chart displays.
    genre_count: dict[int, int] = {}
    for game_id, _minutes, genre_id, _zh, _en in rows:
        if genre_id is not None:
            genre_count[game_id] = genre_count.get(game_id, 0) + 1

    totals: dict[int, dict[str, Any]] = {}
    for game_id, minutes, genre_id, name_zh, name_en in rows:
        key = int(genre_id) if genre_id is not None else 0
        bucket = totals.setdefault(key, {
            "genre_id": key,
            "name_zh": name_zh if genre_id is not None else "",
            "name_en": name_en if genre_id is not None else "",
            "minutes": 0.0,
        })
        divisor = genre_count.get(game_id, 0) or 1
        bucket["minutes"] += float(minutes) / divisor

    items = sorted(totals.values(), key=lambda b: b["minutes"], reverse=True)
    for item in items:
        item["minutes"] = round(item["minutes"], 2)
    return items


def cost_ranking(*, order: str = "expensive") -> dict[str, list[dict[str, Any]]]:
    """Paid per-hour ranking, plus the idle-spend board and zero-cost list.

    Only games with complete purchase records participate. Games with no
    playtime cannot have a per-hour cost, so they are reported separately
    as idle spend rather than ranked with a division by zero.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"""
                SELECT g.game_id, g.game_name,
                       COALESCE(e.play_minutes, 0) AS minutes,
                       {_NET_PAID_SQL} AS net_paid
                FROM steam.library_entries e
                JOIN steam.games g ON g.game_id = e.game_id
                WHERE {_VISIBLE_ENTRIES}
                  AND e.purchase_records_complete = TRUE
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    ranked = []
    idle = []
    zero_cost = []
    for game_id, name, minutes, net_paid in rows:
        net = Decimal(net_paid or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        minutes = int(minutes)
        if net <= 0:
            zero_cost.append({
                "game_id": game_id,
                "game_name": name,
                "play_minutes": minutes,
                "net_paid": _money(net),
            })
            continue
        if minutes <= 0:
            idle.append({
                "game_id": game_id,
                "game_name": name,
                "net_paid": _money(net),
            })
            continue
        per_hour = (net * 60 / minutes).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ranked.append({
            "game_id": game_id,
            "game_name": name,
            "play_minutes": minutes,
            "net_paid": _money(net),
            "cost_per_hour": _money(per_hour),
        })

    ranked.sort(key=lambda r: Decimal(r["cost_per_hour"]), reverse=(order != "cheap"))
    idle.sort(key=lambda r: Decimal(r["net_paid"]), reverse=True)
    zero_cost.sort(key=lambda r: r["game_name"])
    return {
        "ranked": ranked,
        "idle": idle,
        "zero_cost": zero_cost,
        "idle_total": _money(sum((Decimal(r["net_paid"]) for r in idle), Decimal(0))),
    }


def yearly_spend() -> list[dict[str, Any]]:
    """Net paid per calendar year, excluding refunds; undated rows are omitted."""
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT EXTRACT(YEAR FROM p.purchase_date)::int AS year,
                       SUM(p.paid_amount) AS paid,
                       SUM(CASE WHEN p.status = 'refunded' THEN p.paid_amount ELSE 0 END)
                           AS refunded,
                       count(*) AS records
                FROM steam.purchases p
                WHERE p.purchase_date IS NOT NULL
                GROUP BY EXTRACT(YEAR FROM p.purchase_date)
                ORDER BY year
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    items = []
    for year, paid, refunded, records in rows:
        net = Decimal(paid or 0) - Decimal(refunded or 0)
        items.append({
            "year": int(year),
            "net_paid": _money(net),
            "refunded": _money(refunded),
            "records": int(records),
        })
    return items


def undated_purchase_count() -> int:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM steam.purchases WHERE purchase_date IS NULL")
            return cur.fetchone()[0]
    finally:
        conn.close()
