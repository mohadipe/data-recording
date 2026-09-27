import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from data_recorder.main import app
from data_recorder.models.verbrauch import WaermepumpeStundenwert


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_poll_now_success(client):
    """Tests POST /api/ebus/poll-now returns 200 when poll succeeds."""
    mock_record = WaermepumpeStundenwert(
        id=1,
        zeitstempel=datetime.datetime(2026, 9, 27, 11, 0, 0),
        aussentemperatur=Decimal("14.50"),
        vorlauf_temp=Decimal("32.80"),
        ruecklauf_temp=Decimal("28.40"),
        ertrag_gesamt_kwh=Decimal("18260.50"),
        strom_gesamt_kwh=Decimal("4801.80"),
        ertrag_heizen_kwh=Decimal("15420.50"),
        strom_heizen_kwh=Decimal("3855.10"),
        ertrag_warmwasser_kwh=Decimal("2840.00"),
        strom_warmwasser_kwh=Decimal("946.70"),
        cop_aktuell=Decimal("3.80"),
    )

    with patch(
        "data_recorder.services.ebus_service.EbusService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = mock_record
        response = client.post("/api/ebus/poll-now")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert data["data"]["cop_aktuell"] == 3.8
        assert data["data"]["aussentemperatur"] == 14.5
        assert data["data"]["ertrag_gesamt_kwh"] == 18260.5


def test_poll_now_ebusd_offline(client):
    """Tests POST /api/ebus/poll-now returns 502 with error status when ebusd is unreachable."""
    with patch(
        "data_recorder.services.ebus_service.EbusService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = None
        response = client.post("/api/ebus/poll-now")
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == "error"
        assert "eBUS-Daemon" in data["message"]


def test_get_latest_empty(client):
    """Tests GET /api/ebus/latest returns 404 when no data exists."""
    from data_recorder.core.database import Base, get_db_session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"verbrauch": None, "wertpapiere": None}},
    )
    Base.metadata.create_all(bind=test_engine)

    def override_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    try:
        response = client.get("/api/ebus/latest")
        assert response.status_code == 404
        assert "Keine eBUS-Messwerte" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_get_latest_success(client):
    """Tests GET /api/ebus/latest returns the most recent record."""
    from data_recorder.core.database import Base, get_db_session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"verbrauch": None, "wertpapiere": None}},
    )
    Base.metadata.create_all(bind=test_engine)

    with Session(test_engine) as session:
        wp1 = WaermepumpeStundenwert(
            zeitstempel=datetime.datetime(2026, 9, 27, 10, 0, 0),
            cop_aktuell=Decimal("3.50"),
            ertrag_gesamt_kwh=Decimal("18200.00"),
        )
        wp2 = WaermepumpeStundenwert(
            zeitstempel=datetime.datetime(2026, 9, 27, 11, 0, 0),
            cop_aktuell=Decimal("3.80"),
            ertrag_gesamt_kwh=Decimal("18260.50"),
        )
        session.add_all([wp1, wp2])
        session.commit()

    def override_db():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    try:
        response = client.get("/api/ebus/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["cop_aktuell"] == 3.8
        assert data["ertrag_gesamt_kwh"] == 18260.5
        assert "2026-09-27T11:00:00" in data["zeitstempel"]
    finally:
        app.dependency_overrides.clear()

