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
