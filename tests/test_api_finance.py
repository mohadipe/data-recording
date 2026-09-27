import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.api.routes_finance import get_hibiscus_db, get_wertpapiere_db
from data_recorder.core.database import Base, get_db_session
from data_recorder.main import app
from data_recorder.models.wertpapiere import Etf, WknWertDatum


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {
                "verbrauch": None,
                "wertpapiere": None,
                "hibiscus": None,
            }
        },
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session: Session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_wertpapiere_db] = override_db
    app.dependency_overrides[get_hibiscus_db] = override_db
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


def test_get_hibiscus_db_generator():
    """Tests default get_hibiscus_db generator yields session from get_db_session."""
    with patch("data_recorder.api.routes_finance.get_db_session") as mock_db:
        mock_db.return_value = ["mock_session_hib"]
        items = list(get_hibiscus_db())
        assert items == ["mock_session_hib"]


def test_scan_hibiscus_endpoint_success(client: TestClient):
    """Tests POST /api/finance/scan-hibiscus successfully returns ScanResult."""
    from data_recorder.services.hibiscus_service import ScanResult

    mock_res = ScanResult(
        scanned_count=5,
        imported_count=2,
        skipped_count=1,
        sparplaene_count=1,
        dividenden_count=1,
        details=[
            {
                "umsatz_id": 101,
                "wkn": "A1T8FV",
                "isin": "IE00B4L5Y983",
                "typ": "SPARPLAN",
                "datum": "2024-03-01",
                "betrag": 150.0,
            },
            {
                "umsatz_id": 102,
                "wkn": "A1JT1B",
                "isin": "IE00B8GKDB10",
                "typ": "DIVIDENDE",
                "datum": "2024-03-15",
                "betrag": 42.5,
            },
        ],
    )

    with patch(
        "data_recorder.services.hibiscus_service.HibiscusService.scan_and_import",
        return_value=mock_res,
    ) as mock_scan:
        response = client.post("/api/finance/scan-hibiscus")
        assert response.status_code == 200
        assert mock_scan.call_count == 1
        data = response.json()
        assert data["status"] == "ok"
        assert data["scanned_count"] == 5
        assert data["imported_count"] == 2
        assert data["sparplaene_count"] == 1
        assert data["dividenden_count"] == 1
        assert len(data["details"]) == 2
        assert data["details"][0]["wkn"] == "A1T8FV"
        assert data["details"][0]["typ"] == "SPARPLAN"
        assert data["details"][1]["wkn"] == "A1JT1B"
        assert data["details"][1]["typ"] == "DIVIDENDE"


def test_scan_hibiscus_endpoint_with_filters(client: TestClient):
    """Tests POST /api/finance/scan-hibiscus forwards account_filters."""
    from data_recorder.services.hibiscus_service import ScanResult

    mock_res = ScanResult(
        scanned_count=2,
        imported_count=1,
        skipped_count=0,
        sparplaene_count=1,
        dividenden_count=0,
        details=[],
    )

    with patch(
        "data_recorder.services.hibiscus_service.HibiscusService.scan_and_import",
        return_value=mock_res,
    ) as mock_scan:
        payload = {"account_filters": ["DEPOT123", "GIRO456"]}
        response = client.post("/api/finance/scan-hibiscus", json=payload)
        assert response.status_code == 200
        mock_scan.assert_called_once()
        _, kwargs = mock_scan.call_args
        assert kwargs.get("account_filters") == ["DEPOT123", "GIRO456"]
