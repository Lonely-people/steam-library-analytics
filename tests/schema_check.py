"""S2 verification: apply schema.sql and inspect the real openGauss structure.

Run from the project root with the SSH tunnel established:

    uv run python tests/schema_check.py

Applying the schema is idempotent (CREATE ... IF NOT EXISTS) and only touches
the dedicated ``steam`` schema inside ``steam_library``; it never drops data.
Constraint behaviour is exercised inside savepoints that are rolled back, so
no test rows survive.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "database" / "schema.sql"


def apply_schema(conn) -> None:
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn, conn.cursor() as cur:
        cur.execute(script)


def show_structure(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'steam' ORDER BY table_name"
        )
        tables = [r[0] for r in cur.fetchall()]
        print("tables:", ", ".join(tables))

        for table in tables:
            cur.execute(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = 'steam' AND table_name = %s "
                "ORDER BY ordinal_position",
                (table,),
            )
            print(f"\n[{table}]")
            for name, dtype, nullable, default in cur.fetchall():
                null_mark = "NULL" if nullable == "YES" else "NOT NULL"
                default_mark = f" DEFAULT {default}" if default else ""
                print(f"  {name:26s} {dtype:20s} {null_mark}{default_mark}")

        cur.execute(
            "SELECT conrelid::regclass::text, conname, contype "
            "FROM pg_constraint c "
            "JOIN pg_namespace n ON n.oid = c.connamespace "
            "WHERE n.nspname = 'steam' "
            "ORDER BY conrelid::regclass::text, conname"
        )
        print("\nconstraints:")
        names = {"p": "PRIMARY KEY", "u": "UNIQUE", "f": "FOREIGN KEY", "c": "CHECK"}
        for rel, name, ctype in cur.fetchall():
            print(f"  {rel:28s} {name:34s} {names.get(ctype, ctype)}")

        cur.execute(
            "SELECT indexname, tablename FROM pg_indexes "
            "WHERE schemaname = 'steam' ORDER BY tablename, indexname"
        )
        print("\nindexes:")
        for index, table in cur.fetchall():
            print(f"  {index:40s} on {table}")


def check_constraints(conn) -> int:
    """Attempt invalid rows inside savepoints; expect each to be rejected."""
    failures = 0
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO steam.games (game_name, steam_appid) "
            "VALUES ('__schema_check__', 990000001) RETURNING game_id"
        )
        game_id = cur.fetchone()[0]

        cases = [
            ("negative play_minutes",
             "INSERT INTO steam.library_entries (game_id, play_minutes) VALUES (%s, -5)"),
            ("progress over 100",
             "INSERT INTO steam.library_entries (game_id, progress_percent) VALUES (%s, 101)"),
            ("invalid acquisition_type",
             "INSERT INTO steam.library_entries (game_id, acquisition_type) VALUES (%s, 'bogus')"),
            ("invalid completion_status",
             "INSERT INTO steam.library_entries (game_id, completion_status) VALUES (%s, 'bogus')"),
            ("negative paid_amount",
             "INSERT INTO steam.purchases (library_id, paid_amount) VALUES (%s, -1)"),
            ("invalid purchase_type",
             "INSERT INTO steam.purchases (library_id, paid_amount, purchase_type) VALUES (%s, 10, 'bogus')"),
            ("invalid purchase status",
             "INSERT INTO steam.purchases (library_id, paid_amount, status) VALUES (%s, 10, 'bogus')"),
            ("invalid source",
             "INSERT INTO steam.games (game_name, source) VALUES ('x', 'bogus')"),
        ]
        # library_id sentinel: 0 does not exist, still exercises CHECK on that column
        for label, sql in cases:
            cur.execute("SAVEPOINT chk")
            arg = 0 if "library_id" in sql else game_id
            try:
                cur.execute(sql, (arg,))
                print(f"  {label:30s} -> NOT REJECTED (BAD)")
                failures += 1
            except Exception as exc:  # noqa: BLE001 - report any rejection
                print(f"  {label:30s} -> {type(exc).__name__} ({getattr(exc, 'pgcode', '?')})")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT chk")
                cur.execute("RELEASE SAVEPOINT chk")

        # Uniqueness and FK violations need real parent rows.
        cur.execute(
            "INSERT INTO steam.library_entries (game_id) VALUES (%s) RETURNING library_id",
            (game_id,),
        )
        library_id = cur.fetchone()[0]

        unique_cases = [
            ("duplicate steam_appid",
             "INSERT INTO steam.games (game_name, steam_appid) VALUES ('dup', 990000001)", ()),
            ("duplicate library game_id",
             "INSERT INTO steam.library_entries (game_id) VALUES (%s)", (game_id,)),
            ("invalid purchase library_id",
             "INSERT INTO steam.purchases (library_id, paid_amount) VALUES (%s, 1)", (999999999,)),
            ("purchase_date with time-of-day",
             ("INSERT INTO steam.purchases (library_id, purchase_date, paid_amount) "
              "VALUES (%s, TIMESTAMP '2026-03-15 14:37:59', 10)"), (library_id,)),
        ]
        for label, sql, params in unique_cases:
            cur.execute("SAVEPOINT uniq")
            try:
                cur.execute(sql, params)
                print(f"  {label:30s} -> NOT REJECTED (BAD)")
                failures += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  {label:30s} -> {type(exc).__name__} ({getattr(exc, 'pgcode', '?')})")
            finally:
                cur.execute("ROLLBACK TO SAVEPOINT uniq")
                cur.execute("RELEASE SAVEPOINT uniq")

        # A date-only value must still be accepted by the day-granularity check.
        cur.execute("SAVEPOINT okday")
        try:
            cur.execute(
                "INSERT INTO steam.purchases (library_id, purchase_date, paid_amount) "
                "VALUES (%s, DATE '2026-03-15', 10)",
                (library_id,),
            )
            print(f"  {'purchase_date at midnight':30s} -> accepted (expected)")
        except Exception as exc:  # noqa: BLE001
            print(f"  {'purchase_date at midnight':30s} -> {type(exc).__name__} (BAD)")
            failures += 1
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT okday")
            cur.execute("RELEASE SAVEPOINT okday")

        # Everything created for this check is rolled back at the end.
        conn.rollback()
    return failures


def main() -> int:
    conn = get_connection()
    try:
        apply_schema(conn)
        show_structure(conn)
        print("\nconstraint checks (all expected to be rejected):")
        failures = check_constraints(conn)
    finally:
        conn.close()

    if failures:
        print(f"\n{failures} constraint(s) did NOT reject invalid data", file=sys.stderr)
        return 1
    print("\nall constraint checks rejected invalid data as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
