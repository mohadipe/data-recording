"""Tests for Meter Wizard API endpoints (zaehler listing, latest reading, and EXIF extraction)."""

import datetime
from decimal import Decimal
import io
import piexif
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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


def test_submit_reading_with_photo_success(
    client: TestClient, test_db_session: Session, monkeypatch
):
    """Verify POST /wizard/submit creates Messwert and triggers Paperless upload."""
    zaehler = Zaehler(
        id=5,
        geraete_nr="STROM-MAIN",
        einbau_dt=datetime.date(2020, 1, 1),
        ausbau_dt=datetime.date(2035, 1, 1),
        typ="STROM",
    )
    prior = Messwert(
        id=50,
        zaehler_id=5,
        datum=datetime.date(2026, 7, 1),
        wert=Decimal("12000.00"),
        einheit="KWH",
    )
    test_db_session.add_all([zaehler, prior])
    test_db_session.commit()

    upload_calls = []

    async def fake_upload(*args, **kwargs):
        upload_calls.append(kwargs)
        from data_recorder.services.paperless_service import PaperlessUploadResult

        return PaperlessUploadResult(success=True, task_uuid="task-123")

    from data_recorder.services.paperless_service import PaperlessService

    monkeypatch.setattr(PaperlessService, "upload_document", fake_upload)

    jpeg_bytes = make_jpeg_with_exif("2026:08:01 12:00:00")
    form_data = {
        "zaehler_id": "5",
        "datum": "2026-08-01",
        "wert": "12150.75",
        "einheit": "KWH",
    }
    files = {"foto": ("zaehler_foto.jpg", jpeg_bytes, "image/jpeg")}

    response = client.post("/wizard/submit", data=form_data, files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["zaehler_id"] == 5
    assert data["wert"] == 12150.75
    assert data["vorheriger_wert"] == 12000.00
    assert data["verbrauch"] == 150.75
    assert data["foto_uploaded"] is True

    # Verify database persistence
    saved = test_db_session.scalars(
        select(Messwert).where(
            Messwert.zaehler_id == 5, Messwert.datum == datetime.date(2026, 8, 1)
        )
    ).first()
    assert saved is not None
    assert saved.wert == Decimal("12150.75")
    assert saved.einheit == "KWH"

    # Verify Paperless upload was scheduled in background task
    assert len(upload_calls) == 1
    assert upload_calls[0]["filename"] == "zaehler_foto.jpg"
    assert "STROM" in upload_calls[0]["title"]


def test_submit_reading_without_photo(client: TestClient, test_db_session: Session):
    """Verify POST /wizard/submit works without photo attachment."""
    zaehler = Zaehler(
        id=6,
        geraete_nr="WASSER-01",
        einbau_dt=datetime.date(2020, 1, 1),
        ausbau_dt=datetime.date(2035, 1, 1),
        typ="WASSER",
    )
    test_db_session.add(zaehler)
    test_db_session.commit()

    form_data = {
        "zaehler_id": "6",
        "datum": "2026-08-01",
        "wert": "350.20",
    }
    response = client.post("/wizard/submit", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["zaehler_id"] == 6
    assert data["wert"] == 350.2
    assert data["einheit"] == "M3"
    assert data["foto_uploaded"] is False


def test_submit_reading_idempotent_update(client: TestClient, test_db_session: Session):
    """Verify submitting reading for existing zaehler and date updates value instead of failing."""
    zaehler = Zaehler(
        id=7,
        geraete_nr="STROM-IDEMP",
        einbau_dt=datetime.date(2020, 1, 1),
        ausbau_dt=datetime.date(2035, 1, 1),
        typ="STROM",
    )
    existing = Messwert(
        id=701,
        zaehler_id=7,
        datum=datetime.date(2026, 8, 1),
        wert=Decimal("100.00"),
        einheit="KWH",
    )
    test_db_session.add_all([zaehler, existing])
    test_db_session.commit()

    form_data = {
        "zaehler_id": "7",
        "datum": "2026-08-01",
        "wert": "105.50",
    }
    response = client.post("/wizard/submit", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["wert"] == 105.50

    # Ensure no duplicate row was created
    all_rows = test_db_session.scalars(
        select(Messwert).where(
            Messwert.zaehler_id == 7, Messwert.datum == datetime.date(2026, 8, 1)
        )
    ).all()
    assert len(all_rows) == 1
    assert all_rows[0].wert == Decimal("105.50")

