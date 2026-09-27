"""Tests for Meter Wizard API endpoints (zaehler listing, latest reading, and EXIF extraction)."""

import datetime
from decimal import Decimal
import io
import piexif
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base, get_db_session
from data_recorder.main import app
from data_recorder.models.verbrauch import Messwert, Zaehler


def make_jpeg_with_exif(date_str: str = "2026:08:15 10:30:00") -> bytes:
    """Helper to generate in-memory JPEG with EXIF DateTimeOriginal."""
    img = Image.new("RGB", (30, 30), color="blue")
    exif_dict = {
        "0th": {},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: date_str.encode("utf-8")},
        "GPS": {},
        "1st": {},
    }
    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    return buf.getvalue()


@pytest.fixture
def test_db_session():
    """Isolated in-memory SQLite session with verbrauch schema translation."""
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
    """FastAPI TestClient with overridden get_db_session dependency."""
    def override_get_db_session():
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_zaehler_list(client: TestClient, test_db_session: Session):
    """Verify GET /api/zaehler returns active meters with latest readings."""
    # Active meter with reading
    z1 = Zaehler(
        id=1,
        geraete_nr="STROM-001",
        einbau_dt=datetime.date(2020, 1, 1),
        ausbau_dt=datetime.date(2035, 12, 31),
        typ="STROM",
    )
    m1 = Messwert(
        id=1,
        zaehler_id=1,
        datum=datetime.date(2026, 8, 1),
        wert=Decimal("12450.50"),
        einheit="KWH",
    )
    # Active meter without reading
    z2 = Zaehler(
        id=2,
        geraete_nr="WASSER-002",
        einbau_dt=datetime.date(2021, 5, 1),
        ausbau_dt=datetime.date(2030, 5, 1),
        typ="WASSER",
    )
    # Inactive / decommissioned meter
    z3 = Zaehler(
        id=3,
        geraete_nr="OLD-003",
        einbau_dt=datetime.date(2010, 1, 1),
        ausbau_dt=datetime.date(2020, 1, 1),
        typ="WAERME",
    )

    test_db_session.add_all([z1, m1, z2, z3])
    test_db_session.commit()

    response = client.get("/api/zaehler")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Only active meters

    ids = [item["id"] for item in data]
    assert 1 in ids
    assert 2 in ids
    assert 3 not in ids

    meter_1 = next(item for item in data if item["id"] == 1)
    assert meter_1["geraete_nr"] == "STROM-001"
    assert meter_1["typ"] == "STROM"
    assert meter_1["last_wert"] == 12450.5
    assert meter_1["last_datum"] == "2026-08-01"
    assert meter_1["einheit"] == "KWH"

    meter_2 = next(item for item in data if item["id"] == 2)
    assert meter_2["geraete_nr"] == "WASSER-002"
    assert meter_2["typ"] == "WASSER"
    assert meter_2["last_wert"] is None
    assert meter_2["einheit"] == "M3"


def test_get_zaehler_latest_found(client: TestClient, test_db_session: Session):
    """Verify GET /api/zaehler/{id}/latest returns meter details and latest reading."""
    zaehler = Zaehler(
        id=10,
        geraete_nr="WAERME-99",
        einbau_dt=datetime.date(2022, 1, 1),
        ausbau_dt=datetime.date(2032, 1, 1),
        typ="WAERME",
    )
    m1 = Messwert(
        id=101,
        zaehler_id=10,
        datum=datetime.date(2026, 7, 1),
        wert=Decimal("5000.00"),
        einheit="KWH",
    )
    m2 = Messwert(
        id=102,
        zaehler_id=10,
        datum=datetime.date(2026, 8, 1),
        wert=Decimal("5120.00"),
        einheit="KWH",
    )
    test_db_session.add_all([zaehler, m1, m2])
    test_db_session.commit()

    response = client.get("/api/zaehler/10/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["zaehler_id"] == 10
    assert data["geraete_nr"] == "WAERME-99"
    assert data["last_wert"] == 5120.0
    assert data["last_datum"] == "2026-08-01"
    assert data["einheit"] == "KWH"
    assert "01.08.2026" in data["formatted_last_reading"]


def test_get_zaehler_latest_not_found(client: TestClient):
    """Verify GET /api/zaehler/{id}/latest returns 404 if meter does not exist."""
    response = client.get("/api/zaehler/9999/latest")
    assert response.status_code == 404
    assert "nicht gefunden" in response.json()["detail"].lower()


def test_extract_date_with_exif(client: TestClient):
    """Verify POST /api/wizard/extract-date extracts EXIF timestamp from image upload."""
    jpeg_bytes = make_jpeg_with_exif("2026:08:24 16:45:00")
    files = {"foto": ("receipt.jpg", jpeg_bytes, "image/jpeg")}

    response = client.post("/api/wizard/extract-date", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["date"] == "2026-08-24"
    assert data["has_exif"] is True


def test_extract_date_without_exif_fallback(client: TestClient):
    """Verify POST /api/wizard/extract-date falls back to today if image has no EXIF."""
    img = Image.new("RGB", (20, 20), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    files = {"foto": ("receipt.png", png_bytes, "image/png")}
    response = client.post("/api/wizard/extract-date", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["date"] == datetime.date.today().isoformat()
    assert data["has_exif"] is False
