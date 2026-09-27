"""Service for handling temporarily buffered photos received via PWA Web Share Target.

Provides secure storage with UUIDs, metadata extraction (EXIF capture date),
HEIC to JPEG preview transcoding, and automated cleanup of expired temporary files.
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from data_recorder.core.config import get_settings
from data_recorder.services.exif_service import extract_capture_datetime

logger = logging.getLogger(__name__)

# Register pillow_heif for HEIC support if available
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    logger.debug("pillow_heif not available in shared_photo_service")

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
    ".webp",
}

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
    "image/webp",
    "application/octet-stream",
}


@dataclass
class SharedPhotoMetadata:
    id: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    capture_date: str  # YYYY-MM-DD
    capture_datetime: str  # ISO string
    has_exif: bool
    is_heic: bool
    created_at: str  # ISO string
    preview_filename: str | None = None


class SharedPhotoService:
    """Manages temporary storage and processing for images shared to the PWA."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        if storage_dir is None:
            settings = get_settings()
            self.storage_dir = Path(settings.SHARED_UPLOADS_DIR)
        else:
            self.storage_dir = Path(storage_dir)

        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_shared_photo(
        self,
        file_content: bytes,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> SharedPhotoMetadata:
        """Validates, stores, extracts EXIF, and generates preview for a shared photo.

        Args:
            file_content: Raw image bytes.
            filename: Original filename from the client (optional).
            content_type: Declared MIME type (optional).

        Returns:
            SharedPhotoMetadata describing the stored image.

        Raises:
            ValueError: If file is empty, corrupted, or unsupported format.
        """
        if not file_content:
            raise ValueError("Leere Bilddatei erhalten.")

        # Determine extension
        orig_name = filename or "shared_photo.jpg"
        ext = Path(orig_name).suffix.lower()
        if not ext or ext not in ALLOWED_IMAGE_EXTENSIONS:
            # Fallback by sniffing image format with PIL
            try:
                with Image.open(io.BytesIO(file_content)) as img:
                    fmt = (img.format or "").upper()
                    if fmt in ("JPEG", "JPG"):
                        ext = ".jpg"
                    elif fmt == "PNG":
                        ext = ".png"
                    elif fmt == "WEBP":
                        ext = ".webp"
                    elif fmt in ("HEIF", "HEIC"):
                        ext = ".heic"
                    else:
                        raise ValueError(f"Nicht unterstütztes Bildformat: {fmt}")
            except (UnidentifiedImageError, OSError, Exception) as exc:
                raise ValueError("Ungültige oder beschädigte Bilddatei.") from exc

        # Validate that PIL can open the image
        is_heic = ext in (".heic", ".heif")
        try:
            with Image.open(io.BytesIO(file_content)) as img:
                img_format = (img.format or "").upper()
                if img_format in ("HEIF", "HEIC"):
                    is_heic = True
        except (UnidentifiedImageError, OSError, Exception) as exc:
            raise ValueError("Ungültige oder beschädigte Bilddatei.") from exc

        photo_id = uuid.uuid4().hex
        stored_file_path = self.storage_dir / f"{photo_id}{ext}"
        stored_file_path.write_bytes(file_content)

        # Extract EXIF capture date
        sentinel = datetime.datetime(1970, 1, 1)
        extracted_dt = extract_capture_datetime(file_content, fallback=sentinel)
        if extracted_dt != sentinel:
            capture_dt = extracted_dt
            has_exif = True
        else:
            capture_dt = datetime.datetime.now()
            has_exif = False

        capture_date_str = capture_dt.strftime("%Y-%m-%d")

        # Generate JPEG preview for HEIC
        preview_filename = None
        if is_heic:
            try:
                with Image.open(io.BytesIO(file_content)) as img:
                    rgb_img = img.convert("RGB")
                    preview_path = self.storage_dir / f"{photo_id}_preview.jpg"
                    rgb_img.save(preview_path, format="JPEG", quality=85)
                    preview_filename = preview_path.name
            except Exception as exc:
                logger.warning("Could not convert HEIC to JPEG preview: %s", exc)

        mime = content_type or ("image/heic" if is_heic else f"image/{ext.lstrip('.')}")
        if mime == "image/jpg":
            mime = "image/jpeg"

        meta = SharedPhotoMetadata(
            id=photo_id,
            original_filename=orig_name,
            content_type=mime,
            file_size_bytes=len(file_content),
            capture_date=capture_date_str,
            capture_datetime=capture_dt.isoformat(),
            has_exif=has_exif,
            is_heic=is_heic,
            created_at=datetime.datetime.now().isoformat(),
            preview_filename=preview_filename,
        )

        meta_path = self.storage_dir / f"{photo_id}.json"
        meta_path.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")
        return meta

    def get_shared_photo_meta(self, photo_id: str) -> SharedPhotoMetadata | None:
        """Loads metadata for a given photo ID if it exists."""
        meta_path = self.storage_dir / f"{photo_id}.json"
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return SharedPhotoMetadata(**data)
        except Exception as exc:
            logger.warning("Failed to read metadata for %s: %s", photo_id, exc)
            return None

    def get_shared_photo_bytes(
        self,
        photo_id: str,
        prefer_preview: bool = False,
    ) -> tuple[bytes, str] | None:
        """Returns the file bytes and mime-type for the photo.

        If prefer_preview is True and a JPEG preview exists (e.g. for HEIC),
        the JPEG preview is returned instead.
        """
        meta = self.get_shared_photo_meta(photo_id)
        if not meta:
            return None

        if prefer_preview and meta.preview_filename:
            preview_path = self.storage_dir / meta.preview_filename
            if preview_path.exists():
                return preview_path.read_bytes(), "image/jpeg"

        # Otherwise find original
        ext = Path(meta.original_filename).suffix.lower()
        if not ext:
            ext = ".heic" if meta.is_heic else ".jpg"
        orig_path = self.storage_dir / f"{photo_id}{ext}"
        if not orig_path.exists():
            # Fallback search for any file matching photo_id
            for p in self.storage_dir.glob(f"{photo_id}.*"):
                if p.suffix != ".json":
                    return p.read_bytes(), meta.content_type
            return None

        return orig_path.read_bytes(), meta.content_type

    def delete_shared_photo(self, photo_id: str) -> bool:
        """Removes the photo files and metadata from disk."""
        meta = self.get_shared_photo_meta(photo_id)
        deleted = False

        if meta and meta.preview_filename:
            preview_path = self.storage_dir / meta.preview_filename
            if preview_path.exists():
                try:
                    preview_path.unlink()
                except OSError:
                    pass

        # Delete any files starting with photo_id
        for p in self.storage_dir.glob(f"{photo_id}*"):
            try:
                p.unlink()
                deleted = True
            except OSError:
                pass

        return deleted

    def cleanup_old_photos(self, max_age_hours: int = 24) -> int:
        """Deletes shared photos older than max_age_hours.

        Returns:
            Number of cleaned up photo sets.
        """
        now = datetime.datetime.now()
        cutoff = now - datetime.timedelta(hours=max_age_hours)
        cleaned = 0

        for meta_file in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                created_dt = datetime.datetime.fromisoformat(data["created_at"])
                if created_dt < cutoff:
                    photo_id = data.get("id")
                    if photo_id:
                        self.delete_shared_photo(photo_id)
                        cleaned += 1
            except Exception as exc:
                logger.warning("Error inspecting file %s during cleanup: %s", meta_file, exc)

        return cleaned
