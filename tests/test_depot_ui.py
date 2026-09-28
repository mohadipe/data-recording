"""Tests for the /depot Web-UI Jinja2 template and route."""

import datetime
from decimal import Decimal

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
    """In-memory SQLite test session for all schemas."""
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
    """FastAPI TestClient with overridden database dependencies."""
    def override_db():
        yield db_session

    app.dependency_overrides[get_wertpapiere_db] = override_db
    app.dependency_overrides[get_hibiscus_db] = override_db
    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_depot_page_returns_200_and_html(client: TestClient, db_session: Session):
    """Verify GET /depot returns 200, Content-Type text/html, and base elements."""
    response = client.get("/depot")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    html = response.text

    # Page title and navigation
    assert "<title>Depot" in html
    assert "href=\"/depot\"" in html or "href='/depot'" in html
    assert "Depot" in html

    # Core UI components
    assert "Gesamt-Depotwert" in html
    assert "Kurse jetzt aktualisieren" in html
    assert "Bestand erfassen" in html


def test_navigation_contains_depot_link(client: TestClient, db_session: Session):
    """Verify /depot link is present in header nav across pages with active styling."""
    # Check on /depot: link is active (brand-600)
    resp_depot = client.get("/depot")
    assert resp_depot.status_code == 200
    assert 'href="/depot"' in resp_depot.text
    assert "bg-brand-600" in resp_depot.text

    # Check on /wizard: /depot link is also present in nav
    resp_wizard = client.get("/wizard")
    assert resp_wizard.status_code == 200
    assert 'href="/depot"' in resp_wizard.text


def test_depot_renders_active_securities_and_holdings(client: TestClient, db_session: Session):
    """Verify active securities, shares, prices, and calculated total values are rendered."""
    etf1 = Etf(
        id=1,
        wkn="A0RPWH",
        isin="IE00B4L5Y983",
        name="iShares Core MSCI World",
        ticker_yahoo="EUNL.TG",
        aktiv=True,
    )
    etf2 = Etf(
        id=2,
        wkn="A1JX52",
        isin="IE00B3RBWM25",
        name="Vanguard FTSE All-World",
        ticker_yahoo="VWRL.TG",
        aktiv=True,
    )
    etf_inactive = Etf(
        id=3,
        wkn="INACT1",
        isin="DE0000000001",
        name="Inactive Fund",
        ticker_yahoo="INACT.TG",
        aktiv=False,
    )
    db_session.add_all([etf1, etf2, etf_inactive])
    db_session.commit()

    # Kurs für etf1
    k1 = WknKursDatum(
        wkn_id=1,
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("100.00"),
    )
    # Bestand für etf1: 50 Anteile -> Gesamtwert 5000.00 €
    b1 = WknBestandDatum(
        wkn_id=1,
        datum=datetime.date(2026, 9, 20),
        anteile=Decimal("50.0000"),
    )

    # Kurs für etf2
    k2 = WknKursDatum(
        wkn_id=2,
        datum=datetime.date(2026, 9, 26),
        kurs=Decimal("120.50"),
    )
    # Bestand für etf2: 10 Anteile -> Gesamtwert 1205.00 €
    b2 = WknBestandDatum(
        wkn_id=2,
        datum=datetime.date(2026, 9, 22),
        anteile=Decimal("10.0000"),
    )

    db_session.add_all([k1, b1, k2, b2])
    db_session.commit()

    response = client.get("/depot")
    assert response.status_code == 200
    html = response.text

    # Active securities present
    assert "iShares Core MSCI World" in html
    assert "A0RPWH" in html
    assert "EUNL.TG" in html

    assert "Vanguard FTSE All-World" in html
    assert "A1JX52" in html
    assert "VWRL.TG" in html

    # Inactive securities not rendered in holdings overview
    assert "Inactive Fund" not in html

    # Quotes and values present (50 * 100 = 5000; 10 * 120.50 = 1205 -> Total = 6205)
    assert "6.205" in html or "6205" in html
    assert "5.000" in html or "5000" in html
    assert "1.205" in html or "1205" in html

    # History entries rendered
    assert "Bestandshistorie" in html
    assert "btn-delete-holding" in html
    assert 'data-holding-id="1"' in html or 'data-holding-id=' in html

    # Modal and form elements
    assert 'id="holding-modal"' in html
    assert 'id="holding-form"' in html
    assert 'id="modal-wkn-id"' in html
    assert 'id="modal-datum"' in html
    assert 'id="modal-anteile"' in html
    assert 'id="btn-save-holding"' in html

    # Quick add buttons per security
    assert "btn-quick-add-holding" in html
    assert 'data-wkn-id="1"' in html
    assert 'data-wkn-id="2"' in html

    # Update prices trigger button
    assert 'id="btn-update-prices"' in html


def test_depot_fractional_shares_and_date_formatting(client: TestClient, db_session: Session):
    """Verify fractional share quantities and German date notations are formatted properly."""
    etf = Etf(
        id=10,
        wkn="DBX0AN",
        isin="LU0290358497",
        name="Xtrackers EUR Overnight Rate Swap",
        ticker_yahoo="XEON.TG",
        aktiv=True,
    )
    db_session.add(etf)
    db_session.commit()

    k = WknKursDatum(
        wkn_id=10,
        datum=datetime.date(2026, 9, 28),
        kurs=Decimal("142.345"),
    )
    b = WknBestandDatum(
        wkn_id=10,
        datum=datetime.date(2026, 9, 27),
        anteile=Decimal("12.3456"),
    )
    db_session.add_all([k, b])
    db_session.commit()

    response = client.get("/depot")
    assert response.status_code == 200
    html = response.text

    # Shares formatted with comma (12,3456)
    assert "12,3456" in html
    # German date notation (28.09.2026 and 27.09.2026)
    assert "28.09.2026" in html
    assert "27.09.2026" in html


def test_depot_empty_state(client: TestClient, db_session: Session):
    """Verify /depot handles empty database without crash."""
    response = client.get("/depot")
    assert response.status_code == 200
    html = response.text
    assert "0,00" in html or "0.00" in html or "0 €" in html
    assert "Keine aktiven Wertpapiere" in html
    assert "Noch keine Bestandshistorie" in html


def test_format_number_de_sign_handling():
    """Verify format_number_de preserves negative sign on fractions between -1 and 0."""
    from data_recorder.api.routes_finance import format_number_de
    assert format_number_de(Decimal("-0.5"), decimals=2) == "-0,50"
    assert format_number_de(Decimal("-0.05"), decimals=2) == "-0,05"
    assert format_number_de(Decimal("0"), decimals=2) == "0,00"
    assert format_number_de(Decimal("12.3456"), decimals=4) == "12,3456"


