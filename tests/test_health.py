import pytest
from fastapi.testclient import TestClient

from data_recorder.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_payload(client):
    response = client.get("/health")
    data = response.json()
    assert data.get("status") == "ok"
    assert "version" in data
    assert data.get("version") == "0.1.0"
    assert "commit" in data
    assert data.get("commit") is None
    assert "build_date" in data
    assert data.get("build_date") is None


def test_health_endpoint_with_build_env(client, monkeypatch):
    from data_recorder.core.config import get_settings

    monkeypatch.setenv("APP_VERSION", "v0.2.0")
    monkeypatch.setenv("BUILD_COMMIT", "637fa7c")
    monkeypatch.setenv("BUILD_DATE", "10.10.2026")
    get_settings.cache_clear()

    try:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("version") == "v0.2.0"
        assert data.get("commit") == "637fa7c"
        assert data.get("build_date") == "10.10.2026"
    finally:
        get_settings.cache_clear()


def test_system_version_endpoint(client, monkeypatch):
    from data_recorder.core.config import get_settings

    monkeypatch.setenv("APP_VERSION", "v1.0.0")
    monkeypatch.setenv("BUILD_COMMIT", "abcdef1")
    monkeypatch.setenv("BUILD_DATE", "2026-10-10")
    get_settings.cache_clear()

    try:
        response = client.get("/api/system/version")
        assert response.status_code == 200
        data = response.json()
        assert data.get("app_name") == "data-recorder"
        assert data.get("version") == "v1.0.0"
        assert data.get("commit") == "abcdef1"
        assert data.get("build_date") == "2026-10-10"
        assert "environment" in data
    finally:
        get_settings.cache_clear()
