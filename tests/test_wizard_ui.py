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


def test_wizard_gallery_and_camera_buttons(client: TestClient, test_db_session: Session):
    """Verify wizard provides separate touch buttons for camera and gallery."""
    response = client.get("/wizard")
    assert response.status_code == 200
    html = response.text

    assert "Foto aufnehmen" in html
    assert "Aus Galerie" in html
    assert "foto-camera-input" in html
    assert "foto-gallery-input" in html
    assert "capture=\"environment\"" in html
    assert "image/heic" in html or "heic" in html


def test_wizard_error_banner(client: TestClient, test_db_session: Session):
    """Verify error query parameter renders friendly German alert banner."""
    response = client.get("/wizard?error=invalid_image")
    assert response.status_code == 200
    html = response.text
    assert "wizard-error-banner" in html
    assert "Das geteilte Bildformat wird nicht unterstützt" in html


def test_zaehler_management_page_renders(client: TestClient, test_db_session: Session):
    """Verify GET /zaehler renders the meter overview, creation modal, and ausbau modal."""
    active_m = Zaehler(
        id=1,
        geraete_nr="1 EMH00 0988 6538",
        einbau_dt=datetime.date(2020, 6, 25),
        ausbau_dt=datetime.date(2036, 6, 25),
        typ="STROM",
    )
    old_m = Zaehler(
        id=2,
        geraete_nr="55215647",
        einbau_dt=datetime.date(2017, 2, 28),
        ausbau_dt=datetime.date(2020, 5, 31),
        typ="STROM",
    )
    test_db_session.add_all([active_m, old_m])
    test_db_session.commit()

    resp = client.get("/zaehler")
    assert resp.status_code == 200
    html = resp.text

    assert "Zähler-Verwaltung" in html
    assert "1 EMH00 0988 6538" in html
    assert "55215647" in html
    assert "create-modal" in html
    assert "ausbau-modal" in html
    assert "edit-modal" in html
    assert "Neuer Zähler" in html
    assert "Ausbauen" in html


def test_wizard_heat_meter_dual_rendering(client: TestClient, test_db_session: Session):
    """Verify wizard renders dual inputs for WAERME meters."""
    heat_m = Zaehler(
        id=6,
        geraete_nr="24389158",
        einbau_dt=datetime.date(2025, 3, 1),
        ausbau_dt=datetime.date(2031, 3, 1),
        typ="WAERME",
    )
    mw_kwh = Messwert(
        id=601,
        zaehler_id=6,
        datum=datetime.date(2026, 8, 1),
        wert=Decimal("1408.00"),
        einheit="KWH",
    )
    mw_m3 = Messwert(
        id=602,
        zaehler_id=6,
        datum=datetime.date(2026, 8, 1),
        wert=Decimal("584.00"),
        einheit="M3",
    )
    test_db_session.add_all([heat_m, mw_kwh, mw_m3])
    test_db_session.commit()

    resp = client.get("/wizard")
    assert resp.status_code == 200
    html = resp.text

    assert "24389158" in html
    assert "WAERME" in html
    assert "dual-reading-section" in html
    assert "wert_kwh" in html
    assert "wert_m3" in html
    assert "1.408" in html or "1408" in html
    assert "584" in html


