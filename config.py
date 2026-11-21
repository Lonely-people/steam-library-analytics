"""Application configuration, read from environment variables with safe defaults."""

import os

from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    """Flask and external service settings for local development."""

    FLASK_HOST = os.environ.get("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = _get_int("FLASK_PORT", 5000)
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = _get_int("DB_PORT", 15432)
    DB_NAME = os.environ.get("DB_NAME", "steam_library")
    DB_USER = os.environ.get("DB_USER", "steam_app")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_SSLMODE = os.environ.get("DB_SSLMODE", "prefer")

    STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")
    STEAM_ID64 = os.environ.get("STEAM_ID64", "")
    STEAM_HTTP_TIMEOUT = _get_int("STEAM_HTTP_TIMEOUT", 20)
