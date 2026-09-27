"""Tests for the Mobile Web-UI Jinja2 template and wizard rendering."""

import datetime
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base, get_db_session
from data_recorder.main import app
from data_recorder.models.verbrauch import Messwert, Zaehler


@pytest.fixture
def test_db_session():
    """In-memory SQLite test session."""
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


@pytest.fixture
def client(test_db_session: Session):
    """FastAPI TestClient with overridden get_db_session."""
    def override_get_db_session():
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_wizard_page_renders_html_and_elements(client: TestClient, test_db_session: Session):
    """Verify GET / and GET /wizard return 200, valid HTML with mobile meta, camera input, and active meters."""
    z1 = Zaehler(
        id=1,
        geraete_nr="1 EMH00 0988 6538",
        einbau_dt=datetime.date(2020, 1, 1),
        ausbau_dt=datetime.date(2030, 1, 1),
        typ="STROM",
    )
    m1 = Messwert(
        id=10,
        zaehler_id=1,
        datum=datetime.date(2026, 8, 1),
        wert=Decimal("12450.00"),
        einheit="KWH",
    )
    test_db_session.add_all([z1, m1])
    test_db_session.commit()

    for path in ("/", "/wizard"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        html = response.text

        # Mobile viewport & PWA meta
        assert "viewport" in html
        assert "manifest.json" in html
        assert "apple-touch-icon" in html

        # Wizard steps
        assert "Schritt 1" in html
        assert "Schritt 2" in html
        assert "Schritt 3" in html

        # Active meter in HTML
        assert "1 EMH00 0988 6538" in html
        assert "STROM" in html

        # Camera file input with capture="environment"
        assert 'type="file"' in html
        assert 'capture="environment"' in html or 'capture=\'environment\'' in html
        assert 'accept="image/*"' in html or 'accept=\'image/*\'' in html


def test_wizard_preselected_meter(client: TestClient, test_db_session: Session):
    """Verify query parameter ?zaehler_id=... selects the requested meter."""
    z1 = Zaehler(
        id=42,
        geraete_nr="WASSER-SPECIAL",
        einbau_dt=datetime.date(2021, 1, 1),
        ausbau_dt=datetime.date(2031, 1, 1),
        typ="WASSER",
    )
    test_db_session.add(z1)
    test_db_session.commit()

    response = client.get("/wizard?zaehler_id=42")
    assert response.status_code == 200
    html = response.text
    assert "WASSER-SPECIAL" in html
