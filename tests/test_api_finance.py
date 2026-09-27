import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.api.routes_finance import get_wertpapiere_db
from data_recorder.core.database import Base, get_db_session
from data_recorder.main import app
from data_recorder.models.wertpapiere import Etf, WknWertDatum


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"verbrauch": None, "wertpapiere": None}},
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session: Session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_wertpapiere_db] = override_db
    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_update_prices_endpoint_success(client: TestClient, db_session: Session):
    """Tests POST /api/finance/update-prices when prices are successfully updated."""
    etf = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    mock_record = WknWertDatum(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        wert=Decimal("105.50"),
    )
    db_session.add(mock_record)
    db_session.commit()

    with patch(
        "data_recorder.services.stock_price_service.StockPriceService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = [mock_record]

        response = client.post("/api/finance/update-prices")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["updated_count"] == 1
        assert len(data["data"]) == 1
        item = data["data"][0]
        assert item["wkn_id"] == etf.id
        assert item["wert"] == 105.50
        assert item["datum"] == "2026-09-25"


def test_update_prices_endpoint_no_active_securities(client: TestClient):
    """Tests POST /api/finance/update-prices when no active securities exist."""
    with patch(
        "data_recorder.services.stock_price_service.StockPriceService.get_active_securities",
        return_value=[],
    ):
        with patch(
            "data_recorder.services.stock_price_service.StockPriceService.poll_and_save",
            new_callable=AsyncMock,
        ) as mock_poll:
            mock_poll.return_value = []
            response = client.post("/api/finance/update-prices")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["updated_count"] == 0
            assert data["data"] == []


def test_update_prices_endpoint_yahoo_api_failure(client: TestClient, db_session: Session):
    """Tests POST /api/finance/update-prices returns 502 Bad Gateway when active securities exist but all fail."""
    etf = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    with patch(
        "data_recorder.services.stock_price_service.StockPriceService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = []

        response = client.post("/api/finance/update-prices")
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == "error"
        assert "Yahoo Finance" in data["message"]


def test_get_latest_prices_endpoint(client: TestClient, db_session: Session):
    """Tests GET /api/finance/latest returns the most recent stock quotes."""
    etf = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    price = WknWertDatum(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        wert=Decimal("105.50"),
    )
    db_session.add(price)
    db_session.commit()

    response = client.get("/api/finance/latest")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["wkn_id"] == etf.id
    assert data[0]["wert"] == 105.50


def test_get_latest_prices_endpoint_empty(client: TestClient):
    """Tests GET /api/finance/latest returns 404 when no prices recorded yet."""
    response = client.get("/api/finance/latest")
    assert response.status_code == 404


def test_serialize_stock_record_without_etf_relation():
    """Tests _serialize_stock_record gracefully handles when etf relationship is None."""
    from data_recorder.api.routes_finance import _serialize_stock_record

    record = WknWertDatum(
        id=99,
        wkn_id=42,
        datum=datetime.date(2026, 9, 25),
        wert=Decimal("123.45"),
    )
    serialized = _serialize_stock_record(record)
    assert serialized.id == 99
    assert serialized.wkn_id == 42
    assert serialized.wkn is None
    assert serialized.name is None
    assert serialized.ticker is None
    assert serialized.wert == 123.45


def test_get_wertpapiere_db_generator():
    """Tests default get_wertpapiere_db generator yields session from get_db_session."""
    with patch("data_recorder.api.routes_finance.get_db_session") as mock_db:
        mock_db.return_value = ["mock_session"]
        items = list(get_wertpapiere_db())
        assert items == ["mock_session"]
