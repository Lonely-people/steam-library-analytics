"""S0 smoke test: the Flask app can be created and serves the minimal index page."""

import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_index_returns_minimal_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Steam 个人游戏库与游玩成本分析系统".encode() in response.data


def test_health_endpoint_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
