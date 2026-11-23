"""S1 verification: connect to the real openGauss instance and run SELECT 1.

Run from the project root with the tunnel already established:

    uv run python tests/db_check.py

The output hides the password. Any connection failure is reported with
the sanitized target and a short error category, then exits non-zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running this file directly from the project root; pytest injects the
# root via pyproject's pythonpath, a plain script does not.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from database.db import describe_target, run_select_one, transaction


def _server_version() -> str:
    with transaction() as cur:
        cur.execute("SELECT version()")
        row = cur.fetchone()
    return row[0] if row else "unknown"


def main() -> int:
    print(f"target: {describe_target()}")
    try:
        value = run_select_one("SELECT 1")
    except psycopg2.OperationalError as exc:
        # OperationalError messages can contain host/user but not the password.
        first_line = str(exc).strip().splitlines()[0]
        print(f"connection failed: {first_line}", file=sys.stderr)
        return 1
    except psycopg2.Error as exc:
        print(f"query failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(f"SELECT 1 -> {value}")
    print(f"server version -> {_server_version()}")
    return 0 if value == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
