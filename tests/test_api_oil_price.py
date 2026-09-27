import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base, get_db_session
from data_recorder.main import app
from data_recorder.models.verbrauch import HeizoelPreis


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {"verbrauch": None, "wertpapiere": None}
        },
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def test_poll_now_success(client):
    """Tests POST /api/oil-price/poll-now returns 200 when scraper succeeds."""
    mock_record = HeizoelPreis(
        id=1,
        datum=datetime.date(2026, 9, 27),
        plz="90579",
        menge_liter=2500,
        preis_pro_liter=Decimal("1.6562"),
    )

    with patch(
        "data_recorder.services.oil_price_service.OilPriceService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = mock_record
        response = client.post("/api/oil-price/poll-now")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert data["data"]["plz"] == "90579"
        assert data["data"]["menge_liter"] == 2500
        assert data["data"]["preis_pro_liter"] == 1.6562
        assert data["data"]["datum"] == "2026-09-27"


def test_poll_now_provider_offline(client):
    """Tests POST /api/oil-price/poll-now returns 502 when provider is unreachable."""
    with patch(
        "data_recorder.services.oil_price_service.OilPriceService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = None
        response = client.post("/api/oil-price/poll-now")
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == "error"
        assert "nicht erreichbar" in data["message"].lower() or "keine daten" in data["message"].lower()


def test_get_latest_success(client, test_db_session: Session):
    """Tests GET /api/oil-price/latest returns the most recent record."""
    older = HeizoelPreis(
        datum=datetime.date(2026, 9, 20),
        plz="90579",
        menge_liter=2500,
        preis_pro_liter=Decimal("1.6800"),
    )
    newer = HeizoelPreis(
        datum=datetime.date(2026, 9, 27),
        plz="90579",
        menge_liter=2500,
        preis_pro_liter=Decimal("1.6562"),
    )
    test_db_session.add_all([older, newer])
    test_db_session.commit()

    def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db
    try:
        response = client.get("/api/oil-price/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["datum"] == "2026-09-27"
        assert data["plz"] == "90579"
        assert data["preis_pro_liter"] == 1.6562
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def test_get_latest_not_found(client, test_db_session: Session):
    """Tests GET /api/oil-price/latest returns 404 when no records exist."""
    def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db
    try:
        response = client.get("/api/oil-price/latest")
        assert response.status_code == 404
        assert "Keine Heizölpreise" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db_session, None)
