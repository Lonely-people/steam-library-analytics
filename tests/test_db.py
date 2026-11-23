"""Unit tests for the database helpers that do not need a live server."""

import psycopg2

from database import db


def test_connection_params_include_sslmode_and_timeout(monkeypatch):
    monkeypatch.setattr(db.Config, "DB_HOST", "127.0.0.1", raising=False)
    monkeypatch.setattr(db.Config, "DB_PORT", 15432, raising=False)
    monkeypatch.setattr(db.Config, "DB_PASSWORD", "super-secret", raising=False)

    params = db.connection_params()

    assert params["host"] == "127.0.0.1"
    assert params["port"] == 15432
    assert params["sslmode"] == db.Config.DB_SSLMODE
    assert params["connect_timeout"] == db.CONNECT_TIMEOUT_SECONDS


def test_describe_target_never_contains_password(monkeypatch):
    monkeypatch.setattr(db.Config, "DB_USER", "steam_app", raising=False)
    monkeypatch.setattr(db.Config, "DB_HOST", "127.0.0.1", raising=False)
    monkeypatch.setattr(db.Config, "DB_PORT", 15432, raising=False)
    monkeypatch.setattr(db.Config, "DB_NAME", "steam_library", raising=False)
    monkeypatch.setattr(db.Config, "DB_PASSWORD", "super-secret", raising=False)

    text = db.describe_target()

    assert "steam_app@127.0.0.1:15432/steam_library" == text
    assert "super-secret" not in text


def test_get_connection_passes_no_password_in_error_text(monkeypatch):
    # Point at a closed local port so psycopg2 fails quickly and confirm the
    # error we surface never contains the configured password.
    monkeypatch.setattr(db.Config, "DB_HOST", "127.0.0.1", raising=False)
    monkeypatch.setattr(db.Config, "DB_PORT", 1, raising=False)
    monkeypatch.setattr(db.Config, "DB_PASSWORD", "super-secret", raising=False)

    try:
        db.get_connection()
    except psycopg2.OperationalError as exc:
        assert "super-secret" not in str(exc)
    else:
        raise AssertionError("expected a connection failure on a closed port")
