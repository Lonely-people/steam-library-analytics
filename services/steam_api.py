"""Steam Web API adapter for the owned-games endpoint.

Only the public endpoint is used; the API key never appears in exceptions,
logs or returned error text. The adapter returns plain data and raises
typed errors so callers (sync service, HTTP routes) can decide the response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from config import Config

STEAM_OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

# Steam returns 403 for a private profile and also for a key without access.
PRIVATE_PROFILE_STATUS = 403


class SteamAPIError(Exception):
    """Base class for Steam adapter failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SteamConfigError(SteamAPIError):
    """Raised when the API key or SteamID64 is missing."""


class SteamAuthError(SteamAPIError):
    """Raised when Steam rejects the key or the profile is not visible."""


class SteamNetworkError(SteamAPIError):
    """Raised on timeouts or transport failures."""


class SteamResponseError(SteamAPIError):
    """Raised when the payload does not match the expected shape."""


@dataclass(frozen=True)
class OwnedGame:
    """One game from the GetOwnedGames response."""

    appid: int
    name: str | None
    playtime_forever: int
    img_icon_url: str | None = None

    @property
    def play_minutes(self) -> int:
        """Playtime in minutes; Steam already reports minutes."""
        return self.playtime_forever


@dataclass(frozen=True)
class OwnedGamesResult:
    """Parsed result plus the raw game count reported by Steam."""

    games: list[OwnedGame]
    steam_reported_count: int | None = field(default=None)


def build_params() -> dict[str, str]:
    """Request parameters for GetOwnedGames."""
    return {
        "key": Config.STEAM_API_KEY,
        "steamid": Config.STEAM_ID64,
        "include_appinfo": "true",
        "include_played_free_games": "true",
        "format": "json",
    }


def _ensure_configured() -> None:
    key = (Config.STEAM_API_KEY or "").strip()
    steamid = (Config.STEAM_ID64 or "").strip()
    if not key or key == "REPLACE_ME":
        raise SteamConfigError("Steam API key is not configured")
    if not steamid or steamid == "REPLACE_ME":
        raise SteamConfigError("SteamID64 is not configured")


def parse_owned_games(payload: Any) -> OwnedGamesResult:
    """Validate and convert a GetOwnedGames JSON payload.

    A missing ``response`` key or a missing ``games`` list is a real error:
    an empty library must arrive as ``games: []``. Treating a malformed
    payload as "empty library" would risk wiping local data later.
    """
    if not isinstance(payload, dict):
        raise SteamResponseError("Steam response is not a JSON object")

    response = payload.get("response")
    if not isinstance(response, dict):
        raise SteamResponseError("Steam response is missing the 'response' object")

    if "game_count" not in response and "games" not in response:
        raise SteamResponseError("Steam response has neither 'games' nor 'game_count'")

    raw_games = response.get("games", [])
    if not isinstance(raw_games, list):
        raise SteamResponseError("Steam 'games' field is not a list")

    games: list[OwnedGame] = []
    for item in raw_games:
        if not isinstance(item, dict):
            raise SteamResponseError("Steam 'games' entry is not an object")
        appid = item.get("appid")
        if not isinstance(appid, int):
            raise SteamResponseError("Steam game entry is missing an integer 'appid'")

        playtime = item.get("playtime_forever", 0)
        if not isinstance(playtime, int) or playtime < 0:
            raise SteamResponseError(f"Invalid playtime for appid {appid}")

        games.append(
            OwnedGame(
                appid=appid,
                name=item.get("name") if isinstance(item.get("name"), str) else None,
                playtime_forever=playtime,
                img_icon_url=(
                    item.get("img_icon_url")
                    if isinstance(item.get("img_icon_url"), str)
                    else None
                ),
            )
        )

    count = response.get("game_count")
    return OwnedGamesResult(
        games=games,
        steam_reported_count=count if isinstance(count, int) else None,
    )


def fetch_owned_games(timeout: int | None = None) -> OwnedGamesResult:
    """Fetch and parse the user's owned games from Steam.

    Raises SteamConfigError, SteamAuthError, SteamNetworkError or
    SteamResponseError. Error messages never include the API key.
    """
    _ensure_configured()
    effective_timeout = timeout or Config.STEAM_HTTP_TIMEOUT

    try:
        response = requests.get(
            STEAM_OWNED_GAMES_URL,
            params=build_params(),
            timeout=effective_timeout,
        )
    except requests.Timeout as exc:
        raise SteamNetworkError("Steam request timed out") from exc
    except requests.RequestException as exc:
        # Only the exception class is surfaced; the URL (which carries the
        # key as a query parameter) is intentionally not included.
        raise SteamNetworkError(f"Steam request failed ({type(exc).__name__})") from exc

    if response.status_code == PRIVATE_PROFILE_STATUS:
        raise SteamAuthError(
            "Steam denied access; check the API key and the profile's game-details privacy"
        )
    if response.status_code == 401:
        raise SteamAuthError("Steam rejected the API key")
    if response.status_code >= 400:
        raise SteamAPIError(f"Steam returned HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise SteamResponseError("Steam returned a non-JSON body") from exc

    return parse_owned_games(payload)
