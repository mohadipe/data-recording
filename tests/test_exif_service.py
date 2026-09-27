import io
from datetime import datetime, timedelta
from pathlib import Path

import piexif
import pillow_heif
import pytest
from PIL import Image

from data_recorder.services.exif_service import (
    extract_capture_datetime,
    parse_exif_date_string,
)


def create_test_jpeg(exif_dict: dict | None = None) -> bytes:
    img = Image.new("RGB", (20, 20), color="blue")
    buf = io.BytesIO()
    if exif_dict:
        exif_bytes = piexif.dump(exif_dict)
        img.save(buf, format="JPEG", exif=exif_bytes)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


def create_test_png(exif_dict: dict | None = None) -> bytes:
    img = Image.new("RGB", (20, 20), color="green")
    buf = io.BytesIO()
    if exif_dict:
        exif_bytes = piexif.dump(exif_dict)
        img.save(buf, format="PNG", exif=exif_bytes)
    else:
        img.save(buf, format="PNG")
    return buf.getvalue()


def create_test_heic(exif_dict: dict | None = None) -> bytes:
    pillow_heif.register_heif_opener()
    img = Image.new("RGB", (20, 20), color="red")
    buf = io.BytesIO()
    heif_file = pillow_heif.from_pillow(img)
    if exif_dict:
        exif_bytes = piexif.dump(exif_dict)
        heif_file.info["exif"] = exif_bytes
    heif_file.save(buf)
    return buf.getvalue()


class TestParseExifDateString:
    def test_parse_standard_exif_format(self):
        result = parse_exif_date_string("2026:05:15 14:30:00")
        assert result == datetime(2026, 5, 15, 14, 30, 0)

    def test_parse_iso_format(self):
        result_space = parse_exif_date_string("2026-05-15 14:30:00")
        result_t = parse_exif_date_string("2026-05-15T14:30:00")
        assert result_space == datetime(2026, 5, 15, 14, 30, 0)
        assert result_t == datetime(2026, 5, 15, 14, 30, 0)

    def test_parse_with_subseconds(self):
        result = parse_exif_date_string("2026:05:15 14:30:00.500")
        assert result == datetime(2026, 5, 15, 14, 30, 0, 500000)

    def test_parse_invalid_strings(self):
        assert parse_exif_date_string("") is None
        assert parse_exif_date_string("invalid-date") is None
        assert parse_exif_date_string("0000:00:00 00:00:00") is None
        assert parse_exif_date_string(None) is None  # type: ignore


class TestExtractCaptureDatetime:
    def test_jpeg_datetime_original(self):
        exif = {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2026:03:10 09:15:30"}}
        data = create_test_jpeg(exif)
        dt = extract_capture_datetime(data)
        assert dt == datetime(2026, 3, 10, 9, 15, 30)

    def test_jpeg_datetime_digitized(self):
        exif = {"Exif": {piexif.ExifIFD.DateTimeDigitized: b"2026:04:12 11:20:00"}}
        data = create_test_jpeg(exif)
        dt = extract_capture_datetime(data)
        assert dt == datetime(2026, 4, 12, 11, 20, 0)

    def test_jpeg_datetime_base_ifd(self):
        exif = {"0th": {piexif.ImageIFD.DateTime: b"2026:01:01 00:00:00"}}
        data = create_test_jpeg(exif)
        dt = extract_capture_datetime(data)
        assert dt == datetime(2026, 1, 1, 0, 0, 0)

    def test_png_datetime_original(self):
        exif = {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2026:08:14 10:00:00"}}
        data = create_test_png(exif)
        dt = extract_capture_datetime(data)
        assert dt == datetime(2026, 8, 14, 10, 0, 0)

    def test_heic_datetime_original(self):
        exif = {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2026:07:20 18:45:12"}}
        data = create_test_heic(exif)
        dt = extract_capture_datetime(data)
        assert dt == datetime(2026, 7, 20, 18, 45, 12)

    def test_filepath_input(self, tmp_path: Path):
        exif = {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2026:09:01 08:00:00"}}
        data = create_test_jpeg(exif)
        file_path = tmp_path / "zaehler.jpg"
        file_path.write_bytes(data)

        dt = extract_capture_datetime(file_path)
        assert dt == datetime(2026, 9, 1, 8, 0, 0)

        dt_str = extract_capture_datetime(str(file_path))
        assert dt_str == datetime(2026, 9, 1, 8, 0, 0)

    def test_image_without_exif_fallback_now(self):
        data = create_test_jpeg(exif_dict=None)
        before = datetime.now()
        dt = extract_capture_datetime(data)
        after = datetime.now()
        assert before - timedelta(seconds=1) <= dt <= after + timedelta(seconds=1)

    def test_image_without_exif_custom_fallback(self):
        data = create_test_jpeg(exif_dict=None)
        custom_fb = datetime(2025, 12, 31, 23, 59, 59)
        dt = extract_capture_datetime(data, fallback=custom_fb)
        assert dt == custom_fb

    def test_corrupt_data_fallback(self):
        corrupt_bytes = b"NOT_AN_IMAGE_CONTENT_AT_ALL"
        custom_fb = datetime(2025, 1, 1, 12, 0, 0)
        dt = extract_capture_datetime(corrupt_bytes, fallback=custom_fb)
        assert dt == custom_fb
