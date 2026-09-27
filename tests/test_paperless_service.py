import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from data_recorder.services.paperless_service import (
    PaperlessService,
    PaperlessUploadResult,
)


@pytest.mark.asyncio
async def test_upload_document_success(tmp_path: Path):
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["headers"] = dict(request.headers)
        captured_request["content"] = request.read()
        return httpx.Response(200, text='"7f098583-059a-4122-bc56-f0fca5c52c6f"')

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    service = PaperlessService(
        api_url="http://paperless.nas:8000",
        api_token="my_test_token",
        failed_uploads_dir=tmp_path / "failed_uploads",
        http_client=client,
    )

    created_dt = datetime(2026, 9, 1, 10, 30, 0)
    result = await service.upload_document(
        file_content=b"JPEG_MOCK_DATA",
        filename="strom_zaehler.jpg",
        title="Zaehlerbeleg Strom 2026-09-01",
        created=created_dt,
        tag="Zaehlerbeleg",
        document_type="Zaehlerbeleg",
    )

    assert isinstance(result, PaperlessUploadResult)
    assert result.success is True
    assert result.task_uuid == "7f098583-059a-4122-bc56-f0fca5c52c6f"
    assert result.status_code == 200
    assert result.local_archive_path is None
    assert captured_request["method"] == "POST"
    assert captured_request["url"] == "http://paperless.nas:8000/api/documents/post_document/"
    assert captured_request["headers"]["authorization"] == "Token my_test_token"
    assert b"Zaehlerbeleg Strom 2026-09-01" in captured_request["content"]
    assert b"2026-09-01T10:30:00" in captured_request["content"]


@pytest.mark.asyncio
async def test_upload_document_http_500_fallback(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    service = PaperlessService(
        api_url="http://paperless.nas:8000",
        api_token="my_test_token",
        failed_uploads_dir=tmp_path / "failed_uploads",
        http_client=client,
    )

    result = await service.upload_document(
        file_content=b"SAMPLE_IMAGE_BYTES",
        filename="gas_zaehler.jpg",
        title="Zaehlerbeleg Gas 2026-09-01",
    )

    assert result.success is False
    assert result.status_code == 500
    assert "500" in (result.error or "")
    assert result.local_archive_path is not None
    assert result.local_archive_path.exists()
    assert result.local_archive_path.read_bytes() == b"SAMPLE_IMAGE_BYTES"

    # Meta file must also exist alongside
    meta_path = result.local_archive_path.with_suffix(".json")
    assert meta_path.exists()
    meta_data = json.loads(meta_path.read_text())
    assert meta_data["title"] == "Zaehlerbeleg Gas 2026-09-01"
    assert "500" in meta_data["error"]


@pytest.mark.asyncio
async def test_upload_document_connect_error_fallback(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to connect to host 192.168.2.125")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    service = PaperlessService(
        api_url="http://192.168.2.125:8000",
        api_token="my_token",
        failed_uploads_dir=tmp_path / "failed_uploads",
        http_client=client,
    )

    result = await service.upload_document(
        file_content=b"WATER_METER_PIC",
        filename="wasser.jpg",
        title="Zaehlerbeleg Wasser 2026-09-01",
    )

    assert result.success is False
    assert "Failed to connect" in (result.error or "")
    assert result.local_archive_path is not None
    assert result.local_archive_path.exists()
    assert result.local_archive_path.read_bytes() == b"WATER_METER_PIC"


@pytest.mark.asyncio
async def test_upload_document_timeout_fallback(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Server timed out")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    service = PaperlessService(
        api_url="http://192.168.2.125:8000",
        api_token="my_token",
        failed_uploads_dir=tmp_path / "failed_uploads",
        http_client=client,
    )

    result = await service.upload_document(
        file_content=b"TIMEOUT_IMAGE",
        filename="timeout.jpg",
        title="Zaehlerbeleg Timeout",
    )

    assert result.success is False
    assert "timed out" in (result.error or "").lower()
    assert result.local_archive_path is not None
    assert result.local_archive_path.exists()


@pytest.mark.asyncio
async def test_upload_document_unconfigured(tmp_path: Path):
    service = PaperlessService(
        api_url="",
        api_token="",
        failed_uploads_dir=tmp_path / "failed_uploads",
    )

    result = await service.upload_document(
        file_content=b"UNCONFIGURED_IMAGE",
        filename="unconfigured.jpg",
        title="Zaehlerbeleg Unconfigured",
    )

    assert result.success is False
    assert result.error == "Paperless API not configured"
    assert result.local_archive_path is not None
    assert result.local_archive_path.exists()
    assert result.local_archive_path.read_bytes() == b"UNCONFIGURED_IMAGE"


@pytest.mark.asyncio
async def test_archive_unique_filenames(tmp_path: Path):
    service = PaperlessService(
        api_url="",
        api_token="",
        failed_uploads_dir=tmp_path / "failed_uploads",
    )

    res1 = await service.upload_document(b"IMG_1", "duplicate.jpg", "Title 1")
    res2 = await service.upload_document(b"IMG_2", "duplicate.jpg", "Title 2")

    assert res1.local_archive_path is not None
    assert res2.local_archive_path is not None
    assert res1.local_archive_path != res2.local_archive_path
    assert res1.local_archive_path.exists()
    assert res2.local_archive_path.exists()
    assert res1.local_archive_path.read_bytes() == b"IMG_1"
    assert res2.local_archive_path.read_bytes() == b"IMG_2"
