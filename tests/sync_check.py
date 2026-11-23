"""S4 verification against the real openGauss database.

Runs a scripted scenario using SIMULATED game data (never a real Steam
request) and inspects the database between steps:

  1. first sync: rows created, counts match
  2. second sync with changed playtime: no duplicate rows, playtime updated
  3. user-maintained fields (acquisition type, completion, progress,
     purchases) survive a re-sync
  4. a Steam failure (private profile) leaves every local row untouched and
     writes a failed log entry

Everything it creates is tagged with a high appid range and removed at the
end, so the real library is left untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from database.db import transaction
from services import steam_api, sync_service
from services.steam_api import OwnedGame, OwnedGamesResult

APPID_A = 990100001
APPID_B = 990100002


def _fake_fetch(games):
    def fetch(timeout=None):
        return OwnedGamesResult(games=games, steam_reported_count=len(games))

    return fetch


def _fake_fail(timeout=None):
    raise steam_api.SteamAuthError("Steam denied access (simulated failure)")


def counts() -> tuple[int, int, int]:
    with transaction() as cur:
        cur.execute("SELECT count(*) FROM steam.games WHERE steam_appid IN (%s, %s)", (APPID_A, APPID_B))
        games = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM steam.library_entries e "
            "JOIN steam.games g ON g.game_id = e.game_id "
            "WHERE g.steam_appid IN (%s, %s)",
            (APPID_A, APPID_B),
        )
        entries = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM steam.purchases")
        purchases = cur.fetchone()[0]
    return games, entries, purchases


def cleanup() -> None:
    with transaction() as cur:
        cur.execute("DELETE FROM steam.games WHERE steam_appid IN (%s, %s)", (APPID_A, APPID_B))
        cur.execute(
            "DELETE FROM steam.sync_logs WHERE message LIKE '%%simulated%%' "
            "OR sync_id IN (SELECT sync_id FROM steam.sync_logs ORDER BY sync_id DESC LIMIT 3)"
        )


def main() -> int:
    cleanup()

    print("=== step 1: first sync ===")
    steam_api.fetch_owned_games = _fake_fetch(
        [
            OwnedGame(appid=APPID_A, name="Sim Game A", playtime_forever=60, img_icon_url="abc"),
            OwnedGame(appid=APPID_B, name="Sim Game B", playtime_forever=0),
        ]
    )
    r1 = sync_service.sync_steam_library()
    print(f"status={r1.status} fetched={r1.fetched_count} created={r1.created_count} "
          f"updated={r1.updated_count} log={r1.sync_id}")
    print(f"db counts (games, entries, purchases) = {counts()}")
    assert r1.status == "success" and r1.created_count == 2, "first sync should create 2"
    assert counts()[:2] == (2, 2)

    print("\n=== step 2: set user-maintained fields ===")
    with transaction() as cur:
        cur.execute(
            "UPDATE steam.library_entries e SET acquisition_type='paid', "
            "completion_status='playing', progress_percent=42, "
            "purchase_records_complete=TRUE "
            "FROM steam.games g WHERE g.game_id=e.game_id AND g.steam_appid=%s",
            (APPID_A,),
        )
        cur.execute(
            "INSERT INTO steam.purchases (library_id, purchase_date, paid_amount) "
            "SELECT e.library_id, DATE '2026-01-10', 99.00 FROM steam.library_entries e "
            "JOIN steam.games g ON g.game_id=e.game_id WHERE g.steam_appid=%s",
            (APPID_A,),
        )
    print("set acquisition=paid, completion=playing, progress=42, 1 purchase")

    print("\n=== step 3: second sync with increased playtime ===")
    steam_api.fetch_owned_games = _fake_fetch(
        [
            OwnedGame(appid=APPID_A, name="Sim Game A", playtime_forever=180),
            OwnedGame(appid=APPID_B, name="Sim Game B", playtime_forever=15),
        ]
    )
    r2 = sync_service.sync_steam_library()
    print(f"status={r2.status} fetched={r2.fetched_count} created={r2.created_count} "
          f"updated={r2.updated_count} log={r2.sync_id}")
    print(f"db counts (games, entries, purchases) = {counts()}")
    assert r2.status == "success" and r2.updated_count == 2 and r2.created_count == 0
    assert counts()[:2] == (2, 2), "re-sync must not duplicate rows"

    with transaction() as cur:
        cur.execute(
            "SELECT play_minutes, acquisition_type, completion_status, progress_percent, "
            "purchase_records_complete FROM steam.library_entries e "
            "JOIN steam.games g ON g.game_id=e.game_id WHERE g.steam_appid=%s",
            (APPID_A,),
        )
        row = cur.fetchone()
    print(f"game A after re-sync: play={row[0]} acquisition={row[1]} "
          f"completion={row[2]} progress={row[3]} records_complete={row[4]}")
    assert row[0] == 180, "play time should be refreshed"
    assert row[1:4] == ("paid", "playing", 42), "user fields must be preserved"
    assert row[4] is True

    print("\n=== step 4: failed sync must not delete data ===")
    before = counts()
    steam_api.fetch_owned_games = _fake_fail
    r3 = sync_service.sync_steam_library()
    after = counts()
    print(f"status={r3.status} message={r3.message} log={r3.sync_id}")
    print(f"counts before={before} after={after}")
    assert r3.status == "failed"
    assert before == after, "a failed sync must leave local data intact"

    with transaction() as cur:
        cur.execute(
            "SELECT status, fetched_count, message FROM steam.sync_logs WHERE sync_id=%s",
            (r3.sync_id,),
        )
        log = cur.fetchone()
    print(f"failure log row: status={log[0]} fetched={log[1]} message={log[2]}")
    assert log[0] == "failed"

    print("\n=== cleanup ===")
    cleanup()
    print(f"after cleanup, counts = {counts()}")
    print("\nall S4 checks passed (simulated data, real database)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except psycopg2.Error as exc:
        print(f"DB ERROR: {type(exc).__name__}: {str(exc).splitlines()[0]}", file=sys.stderr)
        raise SystemExit(2)
