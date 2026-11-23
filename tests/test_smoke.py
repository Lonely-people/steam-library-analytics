"""Smoke test: the Flask app can be created and serves the library page."""

import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_root_redirects_to_library(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/library")


def test_library_page_renders(client):
    response = client.get("/library")
    assert response.status_code == 200
    assert b"library.js" in response.data
    assert b"i18n.js" in response.data


def test_health_endpoint_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
