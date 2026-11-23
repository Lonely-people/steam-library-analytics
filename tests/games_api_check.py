"""S5 API verification against the real database and Flask test client.

Uses the Flask test client (no network) but the real openGauss database.
All writes use manual games with a recognisable name prefix and are removed
at the end.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

from app import create_app
from database.db import transaction

PREFIX = "__S5_CHECK__"


def cleanup() -> None:
    with transaction() as cur:
        cur.execute("DELETE FROM steam.games WHERE game_name LIKE %s", (f"{PREFIX}%",))


def show(label: str, response) -> dict:
    body = response.get_json()
    print(f"{label:44s} HTTP {response.status_code} -> "
          f"{json.dumps(body, ensure_ascii=False, default=str)[:120]}")
    return body


def main() -> int:
    cleanup()
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    print("=== create ===")
    r = client.post("/api/games", json={
        "game_name": f"{PREFIX} Hades",
        "developer": "Supergiant Games",
        "acquisition_type": "paid",
        "completion_status": "playing",
    })
    body = show("POST /api/games", r)
    assert r.status_code == 201
    game_id = body["game_id"]
    assert body["source"] == "manual" and body["play_minutes"] == 0

    r = client.post("/api/games", json={"game_name": f"{PREFIX} Celeste"})
    body2 = show("POST /api/games (minimal)", r)
    assert r.status_code == 201 and body2["acquisition_type"] == "unknown"
    game_id2 = body2["game_id"]

    print("\n=== validation errors ===")
    r = client.post("/api/games", json={"game_name": "   "})
    show("POST empty name", r)
    assert r.status_code == 400

    r = client.post("/api/games", json={"game_name": f"{PREFIX} Bad", "acquisition_type": "nope"})
    show("POST invalid acquisition_type", r)
    assert r.status_code == 400

    r = client.post("/api/games", data="not json", content_type="application/json")
    show("POST non-JSON body", r)
    assert r.status_code == 400

    print("\n=== read + search + filter ===")
    r = client.get(f"/api/games/{game_id}")
    show("GET /api/games/<id>", r)
    assert r.status_code == 200 and body["game_name"] == f"{PREFIX} Hades"

    r = client.get("/api/games", query_string={"search": "hades"})
    found = show("GET ?search=hades (case-insensitive)", r)
    assert any(i["game_id"] == game_id for i in found["items"])

    r = client.get("/api/games", query_string={"search": PREFIX})
    found = show("GET ?search=__S5_CHECK__", r)
    assert found["total"] == 2

    r = client.get("/api/games", query_string={"acquisition_type": "paid"})
    found = show("GET ?acquisition_type=paid", r)
    assert all(i["acquisition_type"] == "paid" for i in found["items"])

    r = client.get("/api/games", query_string={"acquisition_type": "bogus"})
    show("GET invalid filter", r)
    assert r.status_code == 400

    r = client.get("/api/games/999999999")
    show("GET missing game", r)
    assert r.status_code == 404

    print("\n=== update ===")
    r = client.put(f"/api/games/{game_id}", json={
        "game_name": f"{PREFIX} Hades II",
        "completion_status": "completed",
        "progress_percent": 100,
        "purchase_records_complete": True,
    })
    body = show("PUT user fields", r)
    assert r.status_code == 200
    assert body["game_name"] == f"{PREFIX} Hades II"
    assert body["completion_status"] == "completed" and body["progress_percent"] == 100
    # untouched fields keep their old values
    assert body["acquisition_type"] == "paid" and body["developer"] == "Supergiant Games"

    r = client.put(f"/api/games/{game_id}", json={"progress_percent": 150})
    show("PUT progress=150", r)
    assert r.status_code == 400

    r = client.put(f"/api/games/{game_id}", json={"steam_appid": 123})
    body = show("PUT attempt to set steam_appid (ignored)", r)
    assert r.status_code == 200 and body["steam_appid"] is None

    print("\n=== hide / delete ===")
    r = client.put(f"/api/games/{game_id2}", json={"is_hidden": True})
    show("PUT is_hidden=true", r)
    r = client.get("/api/games", query_string={"search": PREFIX})
    show("GET default (hidden excluded)", r)
    assert all(i["game_id"] != game_id2 for i in r.get_json()["items"])
    r = client.get("/api/games", query_string={"search": PREFIX, "include_hidden": "true"})
    show("GET include_hidden=true", r)
    assert any(i["game_id"] == game_id2 for i in r.get_json()["items"])

    with transaction() as cur:
        cur.execute(
            "INSERT INTO steam.purchases (library_id, purchase_date, paid_amount) "
            "SELECT library_id, DATE '2026-02-01', 50 FROM steam.library_entries "
            "WHERE game_id = %s",
            (game_id,),
        )
    r = client.delete(f"/api/games/{game_id}")
    show("DELETE manual game with purchases", r)
    assert r.status_code == 409

    r = client.delete(f"/api/games/{game_id}", query_string={"force": "true"})
    show("DELETE forced", r)
    assert r.status_code == 200 and r.get_json()["outcome"] == "deleted"

    r = client.delete(f"/api/games/{game_id2}")
    show("DELETE second manual game", r)
    assert r.status_code == 200 and r.get_json()["outcome"] == "deleted"

    print("\n=== steam game cannot be deleted, only hidden ===")
    with transaction() as cur:
        cur.execute(
            "INSERT INTO steam.games (steam_appid, game_name, source) "
            "VALUES (990500001, %s, 'steam') RETURNING game_id",
            (f"{PREFIX} Synced Game",),
        )
        steam_game_id = cur.fetchone()[0]
    r = client.delete(f"/api/games/{steam_game_id}")
    show("DELETE steam game", r)
    assert r.status_code == 200 and r.get_json()["outcome"] == "hidden"
    r = client.get(f"/api/games/{steam_game_id}")
    assert r.get_json()["is_hidden"] is True
    with transaction() as cur:
        cur.execute("SELECT count(*) FROM steam.games WHERE game_id=%s", (steam_game_id,))
        assert cur.fetchone()[0] == 1

    print("\n=== sync logs endpoint ===")
    r = client.get("/api/steam/sync-logs")
    show("GET /api/steam/sync-logs", r)
    assert r.status_code == 200 and isinstance(r.get_json()["items"], list)

    print("\n=== cleanup ===")
    cleanup()
    with transaction() as cur:
        cur.execute("DELETE FROM steam.games WHERE steam_appid = 990500001")
    print("done")
    print("\nall S5 API checks passed (real database)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
