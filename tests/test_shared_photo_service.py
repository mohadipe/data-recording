"""Unit tests for SharedPhotoService."""

import datetime
import io
import json
from pathlib import Path

import piexif
import pytest
from PIL import Image

from data_recorder.services.shared_photo_service import SharedPhotoService


def make_test_jpeg(date_str: str | None = None) -> bytes:
    """Helper to generate in-memory JPEG with optional EXIF."""
    img = Image.new("RGB", (50, 50), color="blue")
    buf = io.BytesIO()
    if date_str:
        exif_dict = {
            "0th": {},
            "Exif": {piexif.ExifIFD.DateTimeOriginal: date_str.encode("utf-8")},
            "GPS": {},
            "1st": {},
        }
        exif_bytes = piexif.dump(exif_dict)
        img.save(buf, format="JPEG", exif=exif_bytes)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


def make_test_png() -> bytes:
    """Helper to generate in-memory PNG."""
    img = Image.new("RGBA", (40, 40), color="green")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_test_heic() -> bytes:
    """Helper to generate in-memory HEIF/HEIC image."""
    img = Image.new("RGB", (30, 30), color="purple")
    buf = io.BytesIO()
    img.save(buf, format="HEIF")
    return buf.getvalue()



@pytest.fixture
def temp_service(tmp_path: Path) -> SharedPhotoService:
    """Fixture providing SharedPhotoService using an isolated temporary directory."""
    return SharedPhotoService(storage_dir=tmp_path)


def test_save_jpeg_with_exif(temp_service: SharedPhotoService):
    """Verify JPEG with EXIF gets parsed and stored properly."""
    content = make_test_jpeg("2026:07:20 14:15:00")
    meta = temp_service.save_shared_photo(
        file_content=content,
        filename="zaehler_keller.jpg",
        content_type="image/jpeg",
    )

    assert meta.id
    assert meta.capture_date == "2026-07-20"
    assert meta.has_exif is True
    assert meta.is_heic is False
    assert meta.original_filename == "zaehler_keller.jpg"
    assert meta.content_type == "image/jpeg"

    # Test retrieval
    loaded_meta = temp_service.get_shared_photo_meta(meta.id)
    assert loaded_meta is not None
    assert loaded_meta.capture_date == "2026-07-20"

    retrieved = temp_service.get_shared_photo_bytes(meta.id)
    assert retrieved is not None
    retrieved_bytes, mime = retrieved
    assert retrieved_bytes == content
    assert mime == "image/jpeg"


def test_save_png_without_exif_fallback_to_today(temp_service: SharedPhotoService):
    """Verify PNG without EXIF defaults capture date to today."""
    content = make_test_png()
    today_str = datetime.date.today().isoformat()

    meta = temp_service.save_shared_photo(
        file_content=content,
        filename="screenshot.png",
        content_type="image/png",
    )

    assert meta.has_exif is False
    assert meta.capture_date == today_str
    assert meta.content_type == "image/png"


def test_save_heic_generates_jpeg_preview(temp_service: SharedPhotoService):
    """Verify HEIC images trigger automatic JPEG preview conversion."""
    content = make_test_heic()
    meta = temp_service.save_shared_photo(
        file_content=content,
        filename="iphone_meter.heic",
        content_type="image/heic",
    )

    assert meta.is_heic is True
    assert meta.preview_filename is not None
    assert meta.preview_filename.endswith("_preview.jpg")

    # Retrieve preview
    preview_res = temp_service.get_shared_photo_bytes(meta.id, prefer_preview=True)
    assert preview_res is not None
    preview_bytes, preview_mime = preview_res
    assert preview_mime == "image/jpeg"
    with Image.open(io.BytesIO(preview_bytes)) as preview_img:
        assert preview_img.format == "JPEG"



def test_save_empty_file_raises_error(temp_service: SharedPhotoService):
    """Verify empty byte stream raises ValueError."""
    with pytest.raises(ValueError, match="Leere Bilddatei"):
        temp_service.save_shared_photo(b"", "empty.jpg")


def test_save_invalid_corrupt_file_raises_error(temp_service: SharedPhotoService):
    """Verify corrupted non-image bytes raise ValueError."""
    corrupt_data = b"NOT_AN_IMAGE_FILE_RANDOM_TEXT"
    with pytest.raises(ValueError, match="Ungültige oder beschädigte Bilddatei"):
        temp_service.save_shared_photo(corrupt_data, "bad.jpg")


def test_delete_shared_photo(temp_service: SharedPhotoService):
    """Verify deleting a shared photo removes all associated files."""
    content = make_test_jpeg()
    meta = temp_service.save_shared_photo(content, "test.jpg")
    assert temp_service.get_shared_photo_meta(meta.id) is not None

    deleted = temp_service.delete_shared_photo(meta.id)
    assert deleted is True
    assert temp_service.get_shared_photo_meta(meta.id) is None
    assert temp_service.get_shared_photo_bytes(meta.id) is None


def test_cleanup_old_photos(temp_service: SharedPhotoService, tmp_path: Path):
    """Verify cleanup_old_photos removes expired items while preserving recent ones."""
    # 1. Fresh photo
    content = make_test_jpeg()
    fresh_meta = temp_service.save_shared_photo(content, "fresh.jpg")

    # 2. Old photo (simulate 48 hours ago)
    old_meta = temp_service.save_shared_photo(content, "old.jpg")
    old_json_path = tmp_path / f"{old_meta.id}.json"
    old_data = json.loads(old_json_path.read_text(encoding="utf-8"))
    past_time = datetime.datetime.now() - datetime.timedelta(hours=48)
    old_data["created_at"] = past_time.isoformat()
    old_json_path.write_text(json.dumps(old_data), encoding="utf-8")

    # Run cleanup with 24 hours threshold
    cleaned_count = temp_service.cleanup_old_photos(max_age_hours=24)
    assert cleaned_count == 1

    # Verify fresh remains and old is deleted
    assert temp_service.get_shared_photo_meta(fresh_meta.id) is not None
    assert temp_service.get_shared_photo_meta(old_meta.id) is None
