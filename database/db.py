"""openGauss connection, transaction and parameterized-query helpers.

Secrets stay in ``config.Config``; nothing here ever formats a connection
string that includes the password, so error messages can be shown safely.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg2

from config import Config

# Keep the handshake short so a missing SSH tunnel fails fast instead of
# hanging the Flask request or the verification script.
CONNECT_TIMEOUT_SECONDS = 10


def connection_params() -> dict[str, Any]:
    """Build psycopg2 connection arguments from the current config."""
    return {
        "host": Config.DB_HOST,
        "port": Config.DB_PORT,
        "dbname": Config.DB_NAME,
        "user": Config.DB_USER,
        "password": Config.DB_PASSWORD,
        "sslmode": Config.DB_SSLMODE,
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "application_name": "steam_library",
    }


def describe_target() -> str:
    """Return a human-readable, password-free description of the target."""
    return f"{Config.DB_USER}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"


def get_connection() -> psycopg2.extensions.connection:
    """Open a new database connection using the configured target."""
    return psycopg2.connect(**connection_params())


@contextmanager
def transaction() -> Iterator[psycopg2.extensions.cursor]:
    """Yield a cursor inside a transaction; commit on success, roll back on error.

    psycopg2's connection context manager commits when the block exits
    normally and rolls back on any exception, so callers only need to
    issue parameterized statements on the cursor.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def run_select_one(sql: str, params: tuple[Any, ...] = ()) -> Any:
    """Execute a single-row SELECT and return the first column value."""
    with transaction() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return row[0] if row else None
