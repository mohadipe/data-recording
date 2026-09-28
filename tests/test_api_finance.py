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
from data_recorder.models.wertpapiere import Etf, WknBestandDatum, WknKursDatum


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

    mock_record = WknKursDatum(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("105.50"),
    )
    mock_record.etf = etf
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
        assert item["kurs"] == 105.50
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

    price = WknKursDatum(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("105.50"),
    )
    db_session.add(price)
    db_session.commit()

    response = client.get("/api/finance/latest")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["wkn_id"] == etf.id
    assert data[0]["kurs"] == 105.50
    assert data[0]["wert"] == 105.50

    # Also test the alias /latest-prices
    response_alias = client.get("/api/finance/latest-prices")
    assert response_alias.status_code == 200
    assert response_alias.json() == data


def test_get_latest_prices_endpoint_empty(client: TestClient):
    """Tests GET /api/finance/latest returns 404 when no prices recorded yet."""
    response = client.get("/api/finance/latest")
    assert response.status_code == 404


def test_serialize_stock_record_without_etf_relation():
    """Tests _serialize_stock_record gracefully handles when etf relationship is None."""
    from data_recorder.api.routes_finance import _serialize_stock_record

    record = WknKursDatum(
        id=99,
        wkn_id=42,
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("123.45"),
    )
    serialized = _serialize_stock_record(record)
    assert serialized.id == 99
    assert serialized.wkn_id == 42
    assert serialized.wkn is None
    assert serialized.name is None
    assert serialized.ticker is None
    assert serialized.kurs == 123.45
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


def test_holdings_crud_endpoints(client: TestClient, db_session: Session):
    """Tests GET, POST, DELETE on /api/finance/holdings."""
    etf1 = Etf(wkn="A0RPWH", isin="IE00B4L5Y983", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    etf2 = Etf(wkn="A1T8FV", isin="IE00B5BMR087", name="S&P 500", ticker_yahoo="SXR8.TG", aktiv=True)
    etf_inactive = Etf(wkn="INACT1", isin="IE0000000001", name="Inactive Fund", aktiv=False)
    db_session.add_all([etf1, etf2, etf_inactive])
    db_session.commit()

    # Add quote for etf1 and etf2
    k1 = WknKursDatum(wkn_id=etf1.id, datum=datetime.date(2026, 9, 25), kurs=Decimal("100.0000"))
    k2 = WknKursDatum(wkn_id=etf2.id, datum=datetime.date(2026, 9, 25), kurs=Decimal("50.0000"))
    db_session.add_all([k1, k2])
    db_session.commit()

    # 1. GET /api/finance/holdings initially (no holdings recorded yet)
    resp = client.get("/api/finance/holdings")
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 2  # Only active ETFs
    h1 = next(h for h in holdings if h["wkn_id"] == etf1.id)
    assert h1["anteile"] == 0.0
    assert h1["bestand_datum"] is None
    assert h1["kurs"] == 100.0
    assert h1["kurs_datum"] == "2026-09-25"
    assert h1["gesamtwert"] == 0.0

    # 2. POST /api/finance/holdings validation error for negative anteile
    invalid_resp = client.post("/api/finance/holdings", json={"wkn_id": etf1.id, "datum": "2026-09-28", "anteile": -5.0})
    assert invalid_resp.status_code == 422
    # 404 for unknown wkn_id
    not_found_resp = client.post("/api/finance/holdings", json={"wkn_id": 9999, "datum": "2026-09-28", "anteile": 10.0})
    assert not_found_resp.status_code == 404

    # Test complete sale with anteile = 0 is valid
    zero_resp = client.post("/api/finance/holdings", json={"wkn_id": etf2.id, "datum": "2026-09-28", "anteile": 0})
    assert zero_resp.status_code in (200, 201)
    assert zero_resp.json()["anteile"] == 0.0

    # 3. POST /api/finance/holdings successfully creates holding
    create_resp = client.post(
        "/api/finance/holdings",
        json={"wkn_id": etf1.id, "datum": "2026-09-28", "anteile": 10.5},
    )
    assert create_resp.status_code in (200, 201)
    created = create_resp.json()
    assert created["wkn_id"] == etf1.id
    assert created["wkn"] == "A0RPWH"
    assert created["anteile"] == 10.5
    assert created["datum"] == "2026-09-28"
    holding_id = created["id"]

    # 4. Check GET /api/finance/holdings reflects updated holding and calculated gesamtwert
    resp2 = client.get("/api/finance/holdings")
    assert resp2.status_code == 200
    h1_updated = next(h for h in resp2.json() if h["wkn_id"] == etf1.id)
    assert h1_updated["anteile"] == 10.5
    assert h1_updated["bestand_datum"] == "2026-09-28"
    assert h1_updated["kurs"] == 100.0
    assert h1_updated["gesamtwert"] == 1050.0  # 10.5 * 100.0

    # 5. POST /api/finance/holdings idempotent update for same (wkn_id, datum)
    update_resp = client.post(
        "/api/finance/holdings",
        json={"wkn_id": etf1.id, "datum": "2026-09-28", "anteile": 15.0},
    )
    assert update_resp.status_code in (200, 201)
    updated = update_resp.json()
    assert updated["id"] == holding_id
    assert updated["anteile"] == 15.0

    resp3 = client.get("/api/finance/holdings")
    h1_v3 = next(h for h in resp3.json() if h["wkn_id"] == etf1.id)
    assert h1_v3["anteile"] == 15.0
    assert h1_v3["gesamtwert"] == 1500.0

    # 6. DELETE /api/finance/holdings/{id}
    del_resp = client.delete(f"/api/finance/holdings/{holding_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ok"

    # Delete non-existent returns 404
    del_404 = client.delete(f"/api/finance/holdings/{holding_id}")
    assert del_404.status_code == 404

    # Holding is gone
    resp4 = client.get("/api/finance/holdings")
    h1_v4 = next(h for h in resp4.json() if h["wkn_id"] == etf1.id)
    assert h1_v4["anteile"] == 0.0
    assert h1_v4["bestand_datum"] is None
    assert h1_v4["gesamtwert"] == 0.0


def test_holdings_history_endpoint(client: TestClient, db_session: Session):
    """Tests GET /api/finance/holdings/history with ordering and filtering."""
    etf1 = Etf(wkn="A0RPWH", name="MSCI World", aktiv=True)
    etf2 = Etf(wkn="A1T8FV", name="S&P 500", aktiv=True)
    db_session.add_all([etf1, etf2])
    db_session.commit()

    b1 = WknBestandDatum(wkn_id=etf1.id, datum=datetime.date(2026, 8, 1), anteile=Decimal("10.0"))
    b2 = WknBestandDatum(wkn_id=etf1.id, datum=datetime.date(2026, 9, 1), anteile=Decimal("20.0"))
    b3 = WknBestandDatum(wkn_id=etf2.id, datum=datetime.date(2026, 8, 15), anteile=Decimal("5.0"))
    db_session.add_all([b1, b2, b3])
    db_session.commit()

    # Query all history
    resp = client.get("/api/finance/holdings/history")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3
    # Ordered by date descending: 2026-09-01, 2026-08-15, 2026-08-01
    assert items[0]["datum"] == "2026-09-01"
    assert items[0]["wkn_id"] == etf1.id
    assert items[0]["anteile"] == 20.0
    assert items[0]["wkn"] == "A0RPWH"
    assert items[0]["name"] == "MSCI World"
    assert items[1]["datum"] == "2026-08-15"
    assert items[1]["wkn_id"] == etf2.id
    assert items[2]["datum"] == "2026-08-01"
    assert items[2]["wkn_id"] == etf1.id

    # Query filtered by wkn_id
    resp_filtered = client.get(f"/api/finance/holdings/history?wkn_id={etf2.id}")
    assert resp_filtered.status_code == 200
    filtered_items = resp_filtered.json()
    assert len(filtered_items) == 1
    assert filtered_items[0]["wkn_id"] == etf2.id
    assert filtered_items[0]["anteile"] == 5.0
