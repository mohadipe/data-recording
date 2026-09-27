"""Tests for PWA Web Share Target and shared photo endpoints."""

import datetime
import io
from decimal import Decimal
from unittest.mock import MagicMock, patch

import piexif
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base, get_db_session
from data_recorder.main import app
from data_recorder.models.verbrauch import Zaehler
from data_recorder.services.shared_photo_service import SharedPhotoService


def make_test_jpeg(date_str: str = "2026:07:15 09:45:00") -> bytes:
    """Helper creating JPEG with DateTimeOriginal EXIF tag."""
    img = Image.new("RGB", (60, 60), color="blue")
    buf = io.BytesIO()
    exif_dict = {
        "0th": {},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: date_str.encode("utf-8")},
        "GPS": {},
        "1st": {},
    }
    exif_bytes = piexif.dump(exif_dict)
    img.save(buf, format="JPEG", exif=exif_bytes)
    return buf.getvalue()


@pytest.fixture
def test_db_session():
    """In-memory SQLite database session."""
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
def client(test_db_session: Session, tmp_path):
    """FastAPI TestClient with temporary shared upload directory and test DB."""
    def override_get_db_session():
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    # Override shared photo directory to tmp_path
    with patch("data_recorder.api.routes_wizard.SharedPhotoService") as mock_service_cls:
        service_instance = SharedPhotoService(storage_dir=tmp_path)
        mock_service_cls.return_value = service_instance
        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()


def test_post_wizard_share_valid_photo(client: TestClient):
    """POST /wizard/share stores photo and responds with HTTP 303 redirect."""
    photo_bytes = make_test_jpeg("2026:07:15 09:45:00")
    files = {"foto": ("strom_keller.jpg", photo_bytes, "image/jpeg")}

    response = client.post("/wizard/share", files=files, follow_redirects=False)

    assert response.status_code == 303
    location = response.headers.get("location")
    assert location is not None
    assert location.startswith("/wizard?shared_photo_id=")

    # Extract ID
    photo_id = location.split("shared_photo_id=")[-1]
    assert len(photo_id) >= 16

    # Test GET /api/wizard/shared-photo/{id}/meta
    meta_res = client.get(f"/api/wizard/shared-photo/{photo_id}/meta")
    assert meta_res.status_code == 200
    meta_data = meta_res.json()
    assert meta_data["id"] == photo_id
    assert meta_data["capture_date"] == "2026-07-15"
    assert meta_data["has_exif"] is True

    # Test GET /api/wizard/shared-photo/{id}
    img_res = client.get(f"/api/wizard/shared-photo/{photo_id}")
    assert img_res.status_code == 200
    assert img_res.content == photo_bytes


def test_post_wizard_share_empty_file_redirects_error(client: TestClient):
    """POST /wizard/share with empty payload redirects to wizard with error code."""
    files = {"foto": ("empty.jpg", b"", "image/jpeg")}
    response = client.post("/wizard/share", files=files, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers.get("location") == "/wizard?error=empty_file"


def test_post_wizard_share_corrupt_file_redirects_error(client: TestClient):
    """POST /wizard/share with invalid non-image payload redirects to error."""
    files = {"foto": ("corrupted.jpg", b"SOME_CORRUPTED_TEXT", "image/jpeg")}
    response = client.post("/wizard/share", files=files, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers.get("location") == "/wizard?error=invalid_image"


def test_get_shared_photo_not_found(client: TestClient):
    """GET /api/wizard/shared-photo/nonexistent returns 404."""
    response = client.get("/api/wizard/shared-photo/00000000000000000000")
    assert response.status_code == 404


def test_get_wizard_page_with_shared_photo_prefill(client: TestClient, test_db_session: Session):
    """GET /wizard?shared_photo_id=... prefills photo preview and EXIF date."""
    z = Zaehler(
        id=1,
        geraete_nr="EMH-TEST-01",
        einbau_dt=datetime.date(2020, 1, 1),
        ausbau_dt=datetime.date(2035, 1, 1),
        typ="STROM",
    )
    test_db_session.add(z)
    test_db_session.commit()

    photo_bytes = make_test_jpeg("2026:05:22 11:00:00")
    files = {"foto": ("shared.jpg", photo_bytes, "image/jpeg")}
    share_resp = client.post("/wizard/share", files=files, follow_redirects=False)
    redirect_url = share_resp.headers["location"]

    wizard_resp = client.get(redirect_url)
    assert wizard_resp.status_code == 200
    html = wizard_resp.text
    # Should include shared photo id or preview
    assert "shared_photo_id" in html or "shared.jpg" in html


def test_submit_reading_with_shared_photo_id(client: TestClient, test_db_session: Session):
    """POST /wizard/submit using shared_photo_id forwards photo to Paperless and cleans up temp file."""
    z = Zaehler(
        id=5,
        geraete_nr="WASSER-05",
        einbau_dt=datetime.date(2020, 1, 1),
        ausbau_dt=datetime.date(2035, 1, 1),
        typ="WASSER",
    )
    test_db_session.add(z)
    test_db_session.commit()

    photo_bytes = make_test_jpeg("2026:06:10 08:30:00")
    files = {"foto": ("wasser_uhr.jpg", photo_bytes, "image/jpeg")}
    share_resp = client.post("/wizard/share", files=files, follow_redirects=False)
    photo_id = share_resp.headers["location"].split("shared_photo_id=")[-1]

    with patch("data_recorder.services.paperless_service.PaperlessService.upload_document") as mock_upload:
        mock_upload.return_value = {"id": 123, "status": "ok"}

        payload = {
            "zaehler_id": "5",
            "datum": "2026-06-10",
            "wert": "450.75",
            "einheit": "M3",
            "shared_photo_id": photo_id,
        }
        submit_res = client.post("/wizard/submit", data=payload)
        assert submit_res.status_code == 200
        data = submit_res.json()
        assert data["success"] is True
        assert data["foto_uploaded"] is True
        assert data["wert"] == 450.75

        # Verify paperless upload was queued with photo bytes
        assert mock_upload.called
        call_kwargs = mock_upload.call_args.kwargs
        assert call_kwargs["file_content"] == photo_bytes
        assert "wasser_uhr.jpg" in call_kwargs["filename"]
