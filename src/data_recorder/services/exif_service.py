"""EXIF metadata extraction service for meter reading receipts.

Extracts DateTimeOriginal or DateTimeDigitized from JPEG, PNG, and HEIC images
with automatic fallback to the current timestamp.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import IFD

logger = logging.getLogger(__name__)

# Register HEIF opener with Pillow if pillow-heif is available
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    logger.debug("pillow_heif is not installed; HEIC support might be limited.")

# EXIF Tag Constants
TAG_DATE_TIME = 306  # 0x0132
TAG_DATE_TIME_ORIGINAL = 36867  # 0x9003
TAG_DATE_TIME_DIGITIZED = 36868  # 0x9004


def parse_exif_date_string(date_str: str | None) -> datetime | None:
    """Parses an EXIF date/time string into a Python datetime object.

    Supports:
    - Standard EXIF: "YYYY:MM:DD HH:MM:SS"
    - Standard with subseconds: "YYYY:MM:DD HH:MM:SS.fff"
    - ISO formats: "YYYY-MM-DD HH:MM:SS", "YYYY-MM-DDTHH:MM:SS"
    """
    if not date_str or not isinstance(date_str, str):
        return None

    cleaned = date_str.strip()
    if not cleaned or cleaned.startswith("0000:00:00") or cleaned.startswith("0000-00-00"):
        return None

    # Normalise delimiters: "YYYY:MM:DD" -> "YYYY-MM-DD"
    # Matches patterns like 2026:05:15 or 2026-05-15
    match = re.match(
        r"^(\d{4})[:\-](\d{2})[:\-](\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?",
        cleaned,
    )
    if not match:
        return None

    year, month, day, hour, minute, second, micro = match.groups()
    try:
        microsecond = 0
        if micro:
            # Pad or truncate microseconds to 6 digits
            microsecond = int(micro[:6].ljust(6, "0"))
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
            microsecond,
        )
    except (ValueError, TypeError):
        return None


def extract_capture_datetime(
    image_source: str | Path | bytes | BinaryIO,
    fallback: datetime | None = None,
) -> datetime:
    """Extracts the capture timestamp (DateTimeOriginal or DateTimeDigitized) from an image.

    Args:
        image_source: Path to file, bytes, or file-like binary stream.
        fallback: Datetime to return if EXIF data is absent or unreadable.
                  Defaults to datetime.now() if None.

    Returns:
        A datetime object representing the picture creation timestamp.
    """
    default_timestamp = fallback if fallback is not None else datetime.now()

    try:
        if isinstance(image_source, (str, Path)):
            stream = open(image_source, "rb")
            should_close = True
        elif isinstance(image_source, bytes):
            stream = io.BytesIO(image_source)
            should_close = False
        else:
            stream = image_source
            should_close = False

        try:
            with Image.open(stream) as img:
                exif = img.getexif()
                if exif:
                    # 1. Check IFD.Exif for DateTimeOriginal and DateTimeDigitized
                    try:
                        exif_ifd = exif.get_ifd(IFD.Exif)
                    except Exception:  # pragma: no cover
                        exif_ifd = {}

                    dt_orig_raw = exif_ifd.get(TAG_DATE_TIME_ORIGINAL)
                    if dt_orig_raw:
                        val = dt_orig_raw.decode("utf-8") if isinstance(dt_orig_raw, bytes) else str(dt_orig_raw)
                        parsed = parse_exif_date_string(val)
                        if parsed:
                            return parsed

                    dt_digitized_raw = exif_ifd.get(TAG_DATE_TIME_DIGITIZED)
                    if dt_digitized_raw:
                        val = dt_digitized_raw.decode("utf-8") if isinstance(dt_digitized_raw, bytes) else str(dt_digitized_raw)
                        parsed = parse_exif_date_string(val)
                        if parsed:
                            return parsed

                    # 2. Check base 0th IFD for DateTime
                    dt_base_raw = exif.get(TAG_DATE_TIME)
                    if dt_base_raw:
                        val = dt_base_raw.decode("utf-8") if isinstance(dt_base_raw, bytes) else str(dt_base_raw)
                        parsed = parse_exif_date_string(val)
                        if parsed:
                            return parsed

        finally:
            if should_close:
                stream.close()

    except (UnidentifiedImageError, OSError, Exception) as exc:
        logger.warning("Could not extract EXIF datetime from image: %s", exc)

    return default_timestamp
