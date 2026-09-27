"""Asynchronous Paperless-ngx REST client for meter reading receipt uploads.

Integrates with Paperless-ngx `POST /api/documents/post_document/` and implements
a resilient zero-crash fallback by storing receipts locally in `data/failed_uploads/`
when Paperless is offline or misconfigured.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from data_recorder.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PaperlessUploadResult:
    """Outcome of a document upload attempt to Paperless-ngx."""

    success: bool
    task_uuid: str | None = None
    document_id: int | None = None
    error: str | None = None
    local_archive_path: Path | None = None
    status_code: int | None = None


class PaperlessService:
    """Asynchronous client for uploading meter reading documents to Paperless-ngx."""

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
        failed_uploads_dir: str | Path | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        raw_url = api_url if api_url is not None else settings.PAPERLESS_API_URL
        self.api_url = raw_url.rstrip("/") if raw_url else ""
        self.api_token = api_token if api_token is not None else settings.PAPERLESS_API_TOKEN
        self.failed_uploads_dir = Path(
            failed_uploads_dir if failed_uploads_dir is not None else settings.FAILED_UPLOADS_DIR
        )
        self.default_tag = settings.PAPERLESS_TAG
        self.default_document_type = settings.PAPERLESS_DOCUMENT_TYPE
        self._client = http_client

    async def upload_document(
        self,
        file_content: bytes,
        filename: str,
        title: str,
        created: datetime | None = None,
        tag: str | None = None,
        document_type: str | None = None,
        mime_type: str = "image/jpeg",
    ) -> PaperlessUploadResult:
        """Uploads a receipt image to Paperless-ngx with metadata.

        If Paperless is unreachable, returns an error or is unconfigured, the file
        is safely preserved in the local failed_uploads archive so that no data is lost.
        """
        metadata: dict[str, Any] = {
            "title": title,
            "created": created.isoformat() if created else None,
            "tag": tag if tag is not None else self.default_tag,
            "document_type": document_type if document_type is not None else self.default_document_type,
        }

        if not self.api_url or not self.api_token:
            logger.warning("Paperless API URL or token not configured. Archiving receipt locally.")
            metadata["error"] = "Paperless API not configured"
            archive_path = await self._archive_locally(file_content, filename, metadata)
            return PaperlessUploadResult(
                success=False,
                error="Paperless API not configured",
                local_archive_path=archive_path,
            )

        url = f"{self.api_url}/api/documents/post_document/"
        headers = {
            "Authorization": f"Token {self.api_token}",
        }

        form_data: dict[str, Any] = {
            "title": title,
        }
        if created:
            form_data["created"] = created.isoformat()

        selected_tag = tag if tag is not None else self.default_tag
        if selected_tag:
            form_data["tags"] = selected_tag

        selected_doc_type = document_type if document_type is not None else self.default_document_type
        if selected_doc_type:
            form_data["document_type"] = selected_doc_type

        files = {
            "document": (filename, file_content, mime_type),
        }

        try:
            if self._client is not None:
                response = await self._client.post(url, data=form_data, files=files, headers=headers, timeout=10.0)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, data=form_data, files=files, headers=headers)

            if response.status_code in (200, 201, 202):
                try:
                    resp_json = response.json()
                    task_uuid = resp_json if isinstance(resp_json, str) else resp_json.get("task_id")
                except Exception:
                    task_uuid = response.text.strip().strip('"')

                logger.info(
                    "Successfully uploaded document '%s' to Paperless-ngx (Task UUID: %s)",
                    title,
                    task_uuid,
                )
                return PaperlessUploadResult(
                    success=True,
                    task_uuid=task_uuid,
                    status_code=response.status_code,
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.warning(
                    "Paperless upload failed for '%s' with %s. Archiving locally.",
                    title,
                    error_msg,
                )
                metadata["error"] = error_msg
                archive_path = await self._archive_locally(file_content, filename, metadata)
                return PaperlessUploadResult(
                    success=False,
                    status_code=response.status_code,
                    error=error_msg,
                    local_archive_path=archive_path,
                )

        except (httpx.RequestError, Exception) as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Paperless upload encountered connection/request error: %s. Archiving locally.",
                error_msg,
            )
            metadata["error"] = error_msg
            archive_path = await self._archive_locally(file_content, filename, metadata)
            return PaperlessUploadResult(
                success=False,
                error=error_msg,
                local_archive_path=archive_path,
            )

    async def _archive_locally(
        self,
        file_content: bytes,
        filename: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Saves un-uploaded receipt files locally to ensure zero data loss."""
        self.failed_uploads_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_filename = Path(filename).name
        target_filename = f"{timestamp}_{safe_filename}"
        target_path = self.failed_uploads_dir / target_filename

        target_path.write_bytes(file_content)

        if metadata:
            meta_path = target_path.with_suffix(".json")
            meta_payload = {
                "original_filename": filename,
                "archived_at": datetime.now().isoformat(),
                **metadata,
            }
            meta_path.write_text(json.dumps(meta_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("Meter reading receipt archived locally to %s", target_path)
        return target_path
