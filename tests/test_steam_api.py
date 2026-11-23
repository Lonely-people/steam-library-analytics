"""Tests for the Steam API adapter.

All payloads come from tests/fixtures and are SIMULATED data. Network calls
are monkeypatched, so no real Steam request is made here.
"""

import json
from pathlib import Path

import pytest
import requests

from services import steam_api

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code: int, payload=None, raise_json: bool = False):
        self.status_code = status_code
        self._payload = payload
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


def test_fixture_is_marked_as_simulated():
    payload = load_fixture("steam_owned_games.json")
    assert "SIMULATED" in payload["_fixture_note"]


def test_parse_owned_games_reads_expected_fields():
    result = steam_api.parse_owned_games(load_fixture("steam_owned_games.json"))

    assert result.steam_reported_count == 6
    assert len(result.games) == 6

    by_appid = {g.appid: g for g in result.games}
    assert by_appid[730].name == "Counter-Strike 2"
    assert by_appid[730].play_minutes == 842
    # Free-to-play title, never launched: 0 minutes must survive as 0.
    assert by_appid[440].play_minutes == 0
    assert by_appid[440].img_icon_url is not None
    # Name absent in the payload must become None, not a fabricated title.
    assert by_appid[999999].name is None
    # Icon absent stays absent.
    assert by_appid[1174180].img_icon_url is None


def test_parse_rejects_missing_response_object():
    with pytest.raises(steam_api.SteamResponseError):
        steam_api.parse_owned_games({})


def test_parse_rejects_non_dict_payload():
    with pytest.raises(steam_api.SteamResponseError):
        steam_api.parse_owned_games([])


def test_parse_rejects_game_without_integer_appid():
    payload = {"response": {"games": [{"name": "broken", "playtime_forever": 1}]}}
    with pytest.raises(steam_api.SteamResponseError):
        steam_api.parse_owned_games(payload)


def test_parse_rejects_negative_playtime():
    payload = {"response": {"games": [{"appid": 1, "playtime_forever": -5}]}}
    with pytest.raises(steam_api.SteamResponseError):
        steam_api.parse_owned_games(payload)


def test_private_profile_fixture_has_empty_response():
    payload = load_fixture("steam_private.json")
    # An empty response object is a real (rejectable) shape, not an empty library.
    with pytest.raises(steam_api.SteamResponseError):
        steam_api.parse_owned_games(payload)


def test_fetch_requires_configuration(monkeypatch):
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", "", raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "", raising=False)
    with pytest.raises(steam_api.SteamConfigError):
        steam_api.fetch_owned_games()


def test_fetch_rejects_placeholder_key(monkeypatch):
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", "REPLACE_ME", raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "76561198000000000", raising=False)
    with pytest.raises(steam_api.SteamConfigError):
        steam_api.fetch_owned_games()


def test_fetch_returns_parsed_games(monkeypatch):
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "76561198000000000", raising=False)
    monkeypatch.setattr(
        steam_api.requests,
        "get",
        lambda *a, **kw: FakeResponse(200, load_fixture("steam_owned_games.json")),
    )

    result = steam_api.fetch_owned_games()

    assert len(result.games) == 6
    assert result.games[0].appid == 440


def test_fetch_maps_403_to_auth_error(monkeypatch):
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "76561198000000000", raising=False)
    monkeypatch.setattr(steam_api.requests, "get", lambda *a, **kw: FakeResponse(403, {}))

    with pytest.raises(steam_api.SteamAuthError):
        steam_api.fetch_owned_games()


def test_fetch_maps_timeout_to_network_error(monkeypatch):
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "76561198000000000", raising=False)

    def boom(*args, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr(steam_api.requests, "get", boom)

    with pytest.raises(steam_api.SteamNetworkError):
        steam_api.fetch_owned_games()


def test_network_error_never_leaks_api_key(monkeypatch):
    secret = "very-secret-key-123"
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", secret, raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "76561198000000000", raising=False)

    def boom(*args, **kwargs):
        raise requests.ConnectionError(f"failed calling {args[0]}?key={secret}")

    monkeypatch.setattr(steam_api.requests, "get", boom)

    with pytest.raises(steam_api.SteamNetworkError) as exc_info:
        steam_api.fetch_owned_games()
    assert secret not in str(exc_info.value)


def test_non_json_body_is_a_response_error(monkeypatch):
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "76561198000000000", raising=False)
    monkeypatch.setattr(
        steam_api.requests, "get", lambda *a, **kw: FakeResponse(200, None, raise_json=True)
    )

    with pytest.raises(steam_api.SteamResponseError):
        steam_api.fetch_owned_games()


def test_request_params_enable_appinfo_and_free_games(monkeypatch):
    monkeypatch.setattr(steam_api.Config, "STEAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(steam_api.Config, "STEAM_ID64", "76561198000000000", raising=False)

    captured = {}

    def capture(url, params=None, timeout=None):
        captured.update(params)
        return FakeResponse(200, {"response": {"games": [], "game_count": 0}})

    monkeypatch.setattr(steam_api.requests, "get", capture)
    steam_api.fetch_owned_games()

    assert captured["include_appinfo"] == "true"
    assert captured["include_played_free_games"] == "true"
    assert captured["format"] == "json"
