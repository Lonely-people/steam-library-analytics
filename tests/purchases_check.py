"""S6 verification: purchase CRUD and cost semantics on the real database.

Covers the cases the cost rules hinge on: paid, refunded, zero-cost,
unknown-cost, and no-division-by-zero for unplayed games.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from database.db import transaction

PREFIX = "__S6_CHECK__"


def cleanup() -> None:
    with transaction() as cur:
        cur.execute("DELETE FROM steam.games WHERE game_name LIKE %s", (f"{PREFIX}%",))


def main() -> int:
    cleanup()
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    def create_game(name, **extra):
        payload = {"game_name": f"{PREFIX} {name}"}
        payload.update(extra)
        r = client.post("/api/games", json=payload)
        assert r.status_code == 201, r.get_json()
        return r.get_json()["game_id"]

    paid_id = create_game("Paid", acquisition_type="paid")
    free_id = create_game("Free", acquisition_type="free_to_play")
    unknown_id = create_game("Unknown", acquisition_type="paid")
    refund_id = create_game("Refund", acquisition_type="paid")

    print("=== create purchase ===")
    r = client.post("/api/purchases", json={
        "game_id": paid_id, "purchase_date": "2025-03-14",
        "paid_amount": "128.00", "purchase_type": "base", "status": "paid",
        "notes": "spring sale",
    })
    print("POST /api/purchases ->", r.status_code, r.get_json())
    assert r.status_code == 201
    p1 = r.get_json()

    print("\n=== validation ===")
    cases = [
        ("negative amount", {"game_id": paid_id, "paid_amount": "-1"}),
        ("three decimals", {"game_id": paid_id, "paid_amount": "1.234"}),
        ("bad date", {"game_id": paid_id, "paid_amount": "10", "purchase_date": "2025-13-40"}),
        ("bad type", {"game_id": paid_id, "paid_amount": "10", "purchase_type": "bundle"}),
        ("bad status", {"game_id": paid_id, "paid_amount": "10", "status": "pending"}),
        ("missing amount", {"game_id": paid_id}),
        ("unknown game", {"game_id": 999999999, "paid_amount": "10"}),
    ]
    for label, payload in cases:
        r = client.post("/api/purchases", json=payload)
        print(f"  {label:20s} -> HTTP {r.status_code} {r.get_json().get('error')}")
        assert r.status_code == 400, label

    print("\n=== date with time-of-day is rejected ===")
    with transaction() as cur:
        cur.execute(
            "SELECT library_id FROM steam.library_entries WHERE game_id = %s", (paid_id,)
        )
        lid = cur.fetchone()[0]
    from database.db import get_connection
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SAVEPOINT t")
            try:
                cur.execute(
                    "INSERT INTO steam.purchases (library_id, purchase_date, paid_amount) "
                    "VALUES (%s, TIMESTAMP '2025-03-14 10:30:00', 10)", (lid,))
                print("  time-of-day -> NOT REJECTED (BAD)")
                raise AssertionError("date check missing")
            except Exception as exc:  # noqa: BLE001
                print(f"  time-of-day -> {type(exc).__name__} ({getattr(exc,'pgcode','?')})")
                cur.execute("ROLLBACK TO SAVEPOINT t")
                cur.execute("RELEASE SAVEPOINT t")
    finally:
        conn.close()

    print("\n=== update ===")
    r = client.put(f"/api/purchases/{p1['purchase_id']}", json={"paid_amount": "98.00"})
    print("PUT amount 128 -> 98:", r.status_code, r.get_json()["paid_amount"])
    assert r.status_code == 200 and r.get_json()["paid_amount"] == "98.00"

    r = client.put("/api/purchases/999999999", json={"paid_amount": "1"})
    print("PUT missing ->", r.status_code)
    assert r.status_code == 404

    print("\n=== refunded record ===")
    r = client.post("/api/purchases", json={
        "game_id": refund_id, "purchase_date": "2025-05-01",
        "paid_amount": "68.00", "status": "paid",
    })
    assert r.status_code == 201
    rid = r.get_json()["purchase_id"]
    r = client.put(f"/api/purchases/{rid}", json={"status": "refunded"})
    print("mark refunded:", r.status_code, r.get_json()["effective_amount"])
    assert r.get_json()["effective_amount"] == "0.00"

    print("\n=== zero-cost game (free, records complete) ===")
    client.put(f"/api/games/{free_id}", json={"purchase_records_complete": True})
    r = client.get(f"/api/games/{free_id}/cost")
    free_cost = r.get_json()
    print("free cost ->", free_cost)
    assert free_cost["cost_state"] == "free" and free_cost["net_paid"] == "0.00"
    assert free_cost["cost_per_hour"] is None

    print("\n=== unknown cost (no records, not complete) ===")
    r = client.get(f"/api/games/{unknown_id}/cost")
    unknown_cost = r.get_json()
    print("unknown cost ->", unknown_cost)
    assert unknown_cost["cost_state"] == "unknown", "empty records must not mean free"
    assert unknown_cost["cost_per_hour"] is None

    print("\n=== paid game with playtime -> cost per hour ===")
    client.put(f"/api/games/{paid_id}", json={"purchase_records_complete": True})
    with transaction() as cur:
        cur.execute(
            "UPDATE steam.library_entries SET play_minutes = 120 WHERE game_id = %s",
            (paid_id,),
        )
    r = client.get(f"/api/games/{paid_id}/cost")
    paid_cost = r.get_json()
    print("paid cost ->", paid_cost)
    # 98.00 for 120 minutes = 49.00 per hour
    assert paid_cost["net_paid"] == "98.00"
    assert paid_cost["cost_per_hour"] == "49.00"
    assert paid_cost["cost_state"] == "paid"

    print("\n=== paid but never played -> no division by zero ===")
    with transaction() as cur:
        cur.execute(
            "UPDATE steam.library_entries SET play_minutes = 0 WHERE game_id = %s",
            (paid_id,),
        )
    r = client.get(f"/api/games/{paid_id}/cost")
    print("zero playtime -> cost_per_hour =", r.get_json()["cost_per_hour"])
    assert r.get_json()["cost_per_hour"] is None

    print("\n=== list + delete ===")
    r = client.get("/api/purchases", query_string={"game_id": paid_id})
    print("list for game ->", len(r.get_json()["items"]), "record(s)")
    assert len(r.get_json()["items"]) == 1
    r = client.delete(f"/api/purchases/{p1['purchase_id']}")
    print("DELETE ->", r.status_code)
    assert r.status_code == 200
    r = client.delete(f"/api/purchases/{p1['purchase_id']}")
    print("DELETE again ->", r.status_code)
    assert r.status_code == 404

    print("\n=== cleanup ===")
    cleanup()
    print("done")
    print("\nall S6 checks passed (real database)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
