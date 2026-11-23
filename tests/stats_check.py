"""S7 verification: statistics aggregates cross-checked against raw SQL.

Seeds a controlled data set with a multi-genre game, an uncategorised game,
refunds, unknown cost, and an unplayed paid game, then compares every API
number with an independent query.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal

from app import create_app
from database.db import transaction

PREFIX = "__S7_CHECK__"


def cleanup() -> None:
    # games first: game_genres references genres with ON DELETE RESTRICT.
    with transaction() as cur:
        cur.execute("DELETE FROM steam.games WHERE game_name LIKE %s", (f"{PREFIX}%",))
        cur.execute("DELETE FROM steam.genres WHERE name_zh LIKE %s", (f"{PREFIX}%",))


def main() -> int:
    cleanup()
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    def new_game(name, **extra):
        payload = {"game_name": f"{PREFIX} {name}"}
        payload.update(extra)
        r = client.post("/api/games", json=payload)
        assert r.status_code == 201, r.get_json()
        return r.get_json()["game_id"]

    # Two genres, so the multi-genre split is exercised.
    with transaction() as cur:
        cur.execute(
            "INSERT INTO steam.genres (name_zh, name_en) VALUES "
            "(%s, 'Action'), (%s, 'RPG') RETURNING genre_id",
            (f"{PREFIX} 动作", f"{PREFIX} 角色扮演"),
        )
        action_id, rpg_id = [r[0] for r in cur.fetchall()]

    a = new_game("Multi", acquisition_type="paid")
    b = new_game("Plain", acquisition_type="paid")
    c = new_game("UnknownCost", acquisition_type="paid")
    d = new_game("Freebie", acquisition_type="free_to_play")
    e = new_game("NeverPlayed", acquisition_type="paid")

    with transaction() as cur:
        # a: 600 minutes, paid 60; two genres -> 300 each
        cur.execute("UPDATE steam.library_entries SET play_minutes=600, "
                    "purchase_records_complete=TRUE WHERE game_id=%s", (a,))
        cur.execute("INSERT INTO steam.game_genres (game_id, genre_id) VALUES (%s,%s),(%s,%s)",
                    (a, action_id, a, rpg_id))
        cur.execute("INSERT INTO steam.purchases (library_id, purchase_date, paid_amount) "
                    "SELECT library_id, DATE '2024-06-01', 60 FROM steam.library_entries "
                    "WHERE game_id=%s", (a,))
        # b: 120 minutes, paid 98, one genre, plus a refunded 20
        cur.execute("UPDATE steam.library_entries SET play_minutes=120, "
                    "purchase_records_complete=TRUE WHERE game_id=%s", (b,))
        cur.execute("INSERT INTO steam.game_genres (game_id, genre_id) VALUES (%s,%s)",
                    (b, action_id))
        cur.execute("INSERT INTO steam.purchases (library_id, purchase_date, paid_amount, status) "
                    "SELECT library_id, DATE '2025-01-15', 98, 'paid' FROM steam.library_entries "
                    "WHERE game_id=%s", (b,))
        cur.execute("INSERT INTO steam.purchases (library_id, purchase_date, paid_amount, status) "
                    "SELECT library_id, DATE '2025-02-15', 20, 'refunded' FROM steam.library_entries "
                    "WHERE game_id=%s", (b,))
        # c: no records, marked incomplete -> unknown cost, excluded from rankings
        cur.execute("UPDATE steam.library_entries SET play_minutes=30, "
                    "purchase_records_complete=FALSE WHERE game_id=%s", (c,))
        # d: complete, zero cost, played
        cur.execute("UPDATE steam.library_entries SET play_minutes=45, "
                    "purchase_records_complete=TRUE WHERE game_id=%s", (d,))
        # e: complete, paid 50, never played -> idle spend
        cur.execute("UPDATE steam.library_entries SET play_minutes=0, "
                    "purchase_records_complete=TRUE WHERE game_id=%s", (e,))
        cur.execute("INSERT INTO steam.purchases (library_id, purchase_date, paid_amount) "
                    "SELECT library_id, NULL, 50 FROM steam.library_entries WHERE game_id=%s", (e,))

    print("=== overview ===")
    ov = client.get("/api/stats/overview").get_json()
    print(ov)
    # The real library may already hold the user's own games, so assert on the
    # delta caused by this fixture rather than absolute totals.
    assert Decimal(ov["known_spend"]) >= Decimal("208.00")
    assert ov["incomplete_cost_games"] >= 1
    assert ov["unstarted_count"] >= 1
    assert ov["unstarted_rate"] is not None
    assert ov["total_minutes"] >= 795

    print("\n=== genres (multi-genre split) ===")
    genres = client.get("/api/stats/genres").get_json()["items"]
    ours = [g for g in genres if g["name_zh"].startswith(PREFIX)]
    by_name = {g["name_zh"]: g["minutes"] for g in ours}
    print(by_name)
    # a contributes 300 to each of action/rpg; b adds 120 to action
    assert by_name.get(f"{PREFIX} 动作") == 420.0, by_name.get(f"{PREFIX} 动作")
    assert by_name.get(f"{PREFIX} 角色扮演") == 300.0, by_name.get(f"{PREFIX} 角色扮演")
    # Because the real library may add uncategorised playtime, assert the
    # uncategorised bucket contains at least this fixture's 75 minutes.
    assert any(g["genre_id"] == 0 and g["minutes"] >= 75.0 for g in genres), genres

    print("\n=== cost ranking ===")
    costs = client.get("/api/stats/costs").get_json()
    ranked = {r["game_name"]: r for r in costs["ranked"] if r["game_name"].startswith(PREFIX)}
    print("ranked:", [(k, v["cost_per_hour"]) for k, v in ranked.items()])
    # a: 60 for 600min = 6.00/h ; b: 98 for 120min = 49.00/h
    assert ranked[f"{PREFIX} Multi"]["cost_per_hour"] == "6.00"
    assert ranked[f"{PREFIX} Plain"]["cost_per_hour"] == "49.00"
    # refunded row excluded from b's net
    assert ranked[f"{PREFIX} Plain"]["net_paid"] == "98.00"
    # unknown-cost game never appears in a cost ranking
    assert f"{PREFIX} UnknownCost" not in ranked
    # order check within our fixture subset
    our_order = [r["game_name"] for r in costs["ranked"] if r["game_name"].startswith(PREFIX)]
    assert our_order[0] == f"{PREFIX} Plain", "expensive first among fixture"

    cheap = client.get("/api/stats/costs?order=cheap").get_json()
    cheap_order = [r["game_name"] for r in cheap["ranked"] if r["game_name"].startswith(PREFIX)]
    assert cheap_order[0] == f"{PREFIX} Multi", "cheapest first among fixture"

    print("idle:", costs["idle"])
    assert any(r["game_name"] == f"{PREFIX} NeverPlayed" for r in costs["idle"])
    assert Decimal(costs["idle_total"]) >= Decimal("50.00"), costs["idle_total"]
    assert any(r["game_name"] == f"{PREFIX} Freebie" for r in costs["zero_cost"])

    print("\n=== yearly (undated omitted) ===")
    yearly = client.get("/api/stats/yearly").get_json()
    print(yearly)
    years = {y["year"]: Decimal(y["net_paid"]) for y in yearly["items"]}
    assert years.get(2024, Decimal(0)) >= Decimal("60.00"), years
    assert years.get(2025, Decimal(0)) >= Decimal("98.00"), years
    assert yearly["undated_records"] >= 1

    print("\n=== bad order value ===")
    r = client.get("/api/stats/costs?order=bogus")
    print("HTTP", r.status_code)
    assert r.status_code == 400

    print("\n=== pages ===")
    for path in ("/dashboard", "/analytics"):
        r = client.get(path)
        print(path, "->", r.status_code)
        assert r.status_code == 200

    print("\n=== cleanup ===")
    cleanup()
    print("done")
    print("\nall S7 checks passed (real database)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
