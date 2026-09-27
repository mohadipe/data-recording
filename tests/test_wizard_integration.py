"""End-to-end integration tests for the mobile meter reading wizard."""

import datetime
from decimal import Decimal
import io
from pathlib import Path
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
from data_recorder.services.paperless_service import PaperlessService, PaperlessUploadResult


def create_jpeg_with_exif(date_str: str = "2026:08:15 09:45:00") -> bytes:
    img = Image.new("RGB", (40, 40), color="blue")
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
def test_db():
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
def client(test_db: Session):
    def override_db():
        yield test_db

    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_end_to_end_wizard_workflow_with_exif_photo_and_paperless(
    client: TestClient, test_db: Session, monkeypatch
):
    """Full workflow: Select meter -> Extract EXIF date -> Plausibility check -> Submit -> Paperless dispatch."""
    # Seed active meters
    strom = Zaehler(
        id=1,
        geraete_nr="1 EMH00 0988 6538",
        einbau_dt=datetime.date(2020, 6, 25),
        ausbau_dt=datetime.date(2030, 6, 25),
        typ="STROM",
    )
    wasser = Zaehler(
        id=2,
        geraete_nr="200042394A",
        einbau_dt=datetime.date(2020, 11, 30),
        ausbau_dt=datetime.date(2030, 11, 30),
        typ="WASSER",
    )
    # Previous reading for strom
    m_prior = Messwert(
        id=101,
        zaehler_id=1,
        datum=datetime.date(2026, 7, 1),
        wert=Decimal("12450.00"),
        einheit="KWH",
    )
    test_db.add_all([strom, wasser, m_prior])
    test_db.commit()

    # Track Paperless upload calls
    paperless_calls = []

    async def mock_upload(self, *args, **kwargs):
        paperless_calls.append(kwargs)
        return PaperlessUploadResult(success=True, task_uuid="paperless-task-uuid-42")

    monkeypatch.setattr(PaperlessService, "upload_document", mock_upload)

    # 1. Step 1: Open Wizard UI
    res_page = client.get("/wizard")
    assert res_page.status_code == 200
    assert "1 EMH00 0988 6538" in res_page.text
    assert "200042394A" in res_page.text

    # 2. Step 1 -> 2: Upload photo and extract EXIF date
    photo_bytes = create_jpeg_with_exif("2026:08:01 14:15:30")
    res_exif = client.post(
        "/api/wizard/extract-date",
        files={"foto": ("strom_receipt.jpg", photo_bytes, "image/jpeg")},
    )
    assert res_exif.status_code == 200
    exif_data = res_exif.json()
    assert exif_data["success"] is True
    assert exif_data["date"] == "2026-08-01"
    assert exif_data["has_exif"] is True

    # 3. Step 2: Fetch latest reading for plausibility check
    res_latest = client.get("/api/zaehler/1/latest")
    assert res_latest.status_code == 200
    latest_data = res_latest.json()
    assert latest_data["last_wert"] == 12450.00
    assert latest_data["einheit"] == "KWH"
    assert "12.450" in latest_data["formatted_last_reading"]

    # 4. Step 3: Submit new reading (12.580 kWh, consumption +130 kWh)
    submit_data = {
        "zaehler_id": "1",
        "datum": exif_data["date"],
        "wert": "12580.00",
        "einheit": "KWH",
    }
    submit_files = {"foto": ("strom_receipt.jpg", photo_bytes, "image/jpeg")}
    res_submit = client.post("/wizard/submit", data=submit_data, files=submit_files)
    assert res_submit.status_code == 200
    submit_resp = res_submit.json()

    assert submit_resp["success"] is True
    assert submit_resp["zaehler_id"] == 1
    assert submit_resp["wert"] == 12580.00
    assert submit_resp["vorheriger_wert"] == 12450.00
    assert submit_resp["verbrauch"] == 130.00
    assert submit_resp["foto_uploaded"] is True
    assert submit_resp["next_zaehler_id"] == 2  # Link to Wasser meter

    # Verify DB state
    persisted = test_db.scalars(
        select(Messwert).where(
            Messwert.zaehler_id == 1, Messwert.datum == datetime.date(2026, 8, 1)
        )
    ).first()
    assert persisted is not None
    assert persisted.wert == Decimal("12580.00")
    assert persisted.einheit == "KWH"

    # Verify Paperless background upload
    assert len(paperless_calls) == 1
    call = paperless_calls[0]
    assert call["filename"] == "strom_receipt.jpg"
    assert "STROM 1 EMH00 0988 6538" in call["title"]
    assert call["created"] == datetime.datetime(2026, 8, 1, 0, 0)


def test_end_to_end_negative_consumption_warning_flow(
    client: TestClient, test_db: Session
):
    """Plausibility check handles negative consumption when entered value is less than prior reading."""
    waerme = Zaehler(
        id=3,
        geraete_nr="WAERME-001",
        einbau_dt=datetime.date(2021, 1, 1),
        ausbau_dt=datetime.date(2031, 1, 1),
        typ="WAERME",
    )
    prior = Messwert(
        id=201,
        zaehler_id=3,
        datum=datetime.date(2026, 7, 1),
        wert=Decimal("5000.00"),
        einheit="KWH",
    )
    test_db.add_all([waerme, prior])
    test_db.commit()

    # User enters 4950 (negative delta of -50 kWh)
    submit_data = {
        "zaehler_id": "3",
        "datum": "2026-08-01",
        "wert": "4950.00",
    }
    res = client.post("/wizard/submit", data=submit_data)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["vorheriger_wert"] == 5000.00
    assert data["wert"] == 4950.00
    assert data["verbrauch"] == -50.00


def test_paperless_upload_offline_resilience(
    client: TestClient, test_db: Session, tmp_path: Path, monkeypatch
):
    """Zero Crash Policy: Paperless failure must never crash or reject the reading submission."""
    zaehler = Zaehler(
        id=4,
        geraete_nr="WASSER-FAILOVER",
        einbau_dt=datetime.date(2021, 1, 1),
        ausbau_dt=datetime.date(2031, 1, 1),
        typ="WASSER",
    )
    test_db.add(zaehler)
    test_db.commit()

    # Point failed_uploads_dir to tmp_path
    monkeypatch.setenv("FAILED_UPLOADS_DIR", str(tmp_path))
    from data_recorder.core.config import get_settings
    get_settings.cache_clear()

    # Simulate Paperless server returning HTTP 503 or throwing error
    async def failing_upload(self, *args, **kwargs):
        # Trigger real fallback mechanism of PaperlessService
        return await self._archive_locally(
            kwargs["file_content"], kwargs["filename"], {"error": "Paperless offline (503)"}
        )

    monkeypatch.setattr(PaperlessService, "upload_document", failing_upload)

    photo_bytes = create_jpeg_with_exif("2026:08:01 10:00:00")
    submit_data = {
        "zaehler_id": "4",
        "datum": "2026-08-01",
        "wert": "75.50",
    }
    submit_files = {"foto": ("water.jpg", photo_bytes, "image/jpeg")}

    res = client.post("/wizard/submit", data=submit_data, files=submit_files)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Check reading was stored in DB
    saved = test_db.scalars(select(Messwert).where(Messwert.zaehler_id == 4)).first()
    assert saved is not None
    assert saved.wert == Decimal("75.50")
