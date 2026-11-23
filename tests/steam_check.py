"""S3 check against the real Steam Web API.

Run after filling STEAM_API_KEY and STEAM_ID64 in .env:

    uv run python tests/steam_check.py

It makes one real GetOwnedGames request and prints only aggregate counts and
the first few app IDs/names. It never prints the API key, the request URL, or
the full raw payload. If credentials are missing it stops without a request.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import steam_api


def main() -> int:
    try:
        result = steam_api.fetch_owned_games()
    except steam_api.SteamConfigError as exc:
        print(f"not configured: {exc.message}")
        print("Fill STEAM_API_KEY and STEAM_ID64 in .env, then rerun.")
        return 2
    except steam_api.SteamAuthError as exc:
        print(f"access denied: {exc.message}")
        return 3
    except steam_api.SteamNetworkError as exc:
        print(f"network error: {exc.message}")
        return 4
    except steam_api.SteamResponseError as exc:
        print(f"unexpected response: {exc.message}")
        return 5
    except steam_api.SteamAPIError as exc:
        print(f"steam error: {exc.message}")
        return 6

    print(f"steam game_count -> {result.steam_reported_count}")
    print(f"parsed games     -> {len(result.games)}")
    if result.steam_reported_count is not None and result.steam_reported_count != len(result.games):
        print("warning: reported count differs from parsed count")

    zero_minutes = sum(1 for g in result.games if g.play_minutes == 0)
    unnamed = sum(1 for g in result.games if g.name is None)
    print(f"zero-minute games -> {zero_minutes}")
    print(f"unnamed games     -> {unnamed}")
    print("first entries:")
    for game in result.games[:5]:
        print(f"  appid={game.appid:<10} minutes={game.play_minutes:<8} name={game.name}")

    if not result.games:
        print("\nnote: the API returned no games. This can mean a private profile;")
        print("it does NOT prove the account owns nothing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
