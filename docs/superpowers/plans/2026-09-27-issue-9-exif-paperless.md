# Phase 2.1: EXIF-Parser & Paperless-ngx REST-Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement resilient EXIF metadata extraction (JPEG, PNG, HEIC) and an asynchronous, fault-tolerant Paperless-ngx client with local storage fallback for meter reading receipts.

**Architecture:** 
- `services/exif_service.py`: Uses Pillow and `pillow-heif` to extract `DateTimeOriginal` or `DateTimeDigitized` from images with robust date string parsing and a reliable fallback to current datetime.
- `services/paperless_service.py`: Asynchronous HTTP client using `httpx.AsyncClient` targeting Paperless-ngx `POST /api/documents/post_document/`. Captures network errors and non-2xx status codes, logging warnings and persisting the receipt to a local fallback archive (`data/failed_uploads/`) to guarantee the Zero-Crash Policy.
- `core/config.py`: Expanded with settings for Paperless tags, document types, and fallback directory.

**Tech Stack:** Python 3.12+, FastAPI, Pillow 12+, pillow-heif, httpx 0.28+, pytest, pytest-asyncio.

**Spec:** GitHub Issue #9 (`mohadipe/data-recording`), `Rahmenbedingungen.md`, `docs/guidelines/architecture_and_development_guidelines.md`.

## Global Constraints

- Python 3.12+ type hints on all functions and methods.
- Zero external live network calls in tests; use `httpx.MockTransport` or mocks for 100% offline testing.
- Zero-crash policy: Paperless unavailability must never abort or fail the calling flow.
- Follow Conventional Commits referencing `fixes #9`.

---

### Task 1: Configuration & Dependencies Setup

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/data_recorder/core/config.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.FAILED_UPLOADS_DIR: str`, `Settings.PAPERLESS_TAG: str`, `Settings.PAPERLESS_DOCUMENT_TYPE: str`

- [ ] **Step 1: Write the failing test for new settings**

Add test cases to `tests/test_config.py` asserting `FAILED_UPLOADS_DIR`, `PAPERLESS_TAG`, and `PAPERLESS_DOCUMENT_TYPE` have sensible defaults and can be configured via environment variables.

- [ ] **Step 2: Run test to verify it fails**

Run: `../data-recording/.venv/bin/pytest ../data-recording/tests/test_config.py -v`
Expected: FAIL with AttributeError for missing attributes.

- [ ] **Step 3: Update `pyproject.toml` and `src/data_recorder/core/config.py`**

Add `pillow-heif>=0.18.0` to `dependencies` in `pyproject.toml`.
Add settings in `src/data_recorder/core/config.py`:
```python
FAILED_UPLOADS_DIR: str = "data/failed_uploads"
PAPERLESS_TAG: str = "Zaehlerbeleg"
PAPERLESS_DOCUMENT_TYPE: str = "Zaehlerbeleg"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../data-recording/.venv/bin/pytest ../data-recording/tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git -C ../data-recording add pyproject.toml src/data_recorder/core/config.py tests/test_config.py
git -C ../data-recording commit -m "chore(config): add pillow-heif dependency and paperless configuration settings (fixes #9)"
```

---

### Task 2: EXIF-Parser Service (`services/exif_service.py`)

**Files:**
- Create: `src/data_recorder/services/__init__.py`
- Create: `src/data_recorder/services/exif_service.py`
- Create: `tests/test_exif_service.py`

**Interfaces:**
- Produces:
  `extract_capture_datetime(image_source: str | Path | bytes | BinaryIO, fallback: datetime | None = None) -> datetime`
  `parse_exif_date_string(date_str: str) -> datetime | None`

- [ ] **Step 1: Write the failing tests for EXIF parsing**

In `tests/test_exif_service.py`:
- Test extracting datetime from a synthetic JPEG with `DateTimeOriginal`.
- Test extracting datetime from a synthetic JPEG with `DateTimeDigitized`.
- Test extracting datetime from a synthetic PNG with EXIF chunk.
- Test extracting datetime from a synthetic HEIC (or mock HEIC container with EXIF).
- Test fallback to current datetime when no EXIF tags exist.
- Test fallback when image file is invalid/corrupt.
- Test passing explicit custom fallback datetime.
- Test supporting both `bytes` input and file path input.

- [ ] **Step 2: Run test to verify it fails**

Run: `../data-recording/.venv/bin/pytest ../data-recording/tests/test_exif_service.py -v`
Expected: FAIL (ModuleNotFoundError / ImportError).

- [ ] **Step 3: Write minimal implementation in `services/exif_service.py`**

Implement `extract_capture_datetime` using `PIL.Image` with `pillow_heif.register_heif_opener()`, extracting IFD tags 36867 (`DateTimeOriginal`), 36868 (`DateTimeDigitized`), and 306 (`DateTime`), parsing `"YYYY:MM:DD HH:MM:SS"` or ISO variants, falling back cleanly to `datetime.now()` or provided `fallback`.

- [ ] **Step 4: Run test to verify it passes**

Run: `../data-recording/.venv/bin/pytest ../data-recording/tests/test_exif_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git -C ../data-recording add src/data_recorder/services/__init__.py src/data_recorder/services/exif_service.py tests/test_exif_service.py
git -C ../data-recording commit -m "feat(services): implement resilient EXIF parser service for JPEG, PNG and HEIC (fixes #9)"
```

---

### Task 3: Paperless-ngx REST-Client (`services/paperless_service.py`)

**Files:**
- Create: `src/data_recorder/services/paperless_service.py`
- Create: `tests/test_paperless_service.py`

**Interfaces:**
- Produces:
  `class PaperlessUploadResult(BaseModel or dataclass): success: bool, document_id: int | None, task_uuid: str | None, error: str | None, local_archive_path: Path | None`
  `class PaperlessService: async def upload_receipt(file_content: bytes, filename: str, title: str, created: datetime | None = None, tag: str | None = None, document_type: str | None = None) -> PaperlessUploadResult`
  `async def save_to_local_archive(file_content: bytes, filename: str, metadata: dict[str, Any] | None = None) -> Path`

- [ ] **Step 1: Write the failing tests for Paperless client**

In `tests/test_paperless_service.py`:
- Test successful upload: returns `PaperlessUploadResult(success=True, task_uuid=...)`.
- Test custom metadata passed in multipart/form-data: `title`, `created`, `tags`, `document_type`.
- Test handling when Paperless API URL or token is not configured: logs warning, archives to local fallback, returns `PaperlessUploadResult(success=False, local_archive_path=...)`.
- Test connection failure / timeout: MockTransport raises `httpx.ConnectError` -> logs warning, archives locally, returns `PaperlessUploadResult(success=False, local_archive_path=...)`, no exception raised.
- Test HTTP 500 server error: MockTransport returns status 500 -> logs warning, archives locally, returns `PaperlessUploadResult(success=False, local_archive_path=...)`, no exception raised.
- Test local archive directory auto-creation and unique file naming.

- [ ] **Step 2: Run test to verify it fails**

Run: `../data-recording/.venv/bin/pytest ../data-recording/tests/test_paperless_service.py -v`
Expected: FAIL (ModuleNotFoundError / ImportError).

- [ ] **Step 3: Write minimal implementation in `services/paperless_service.py`**

Implement `PaperlessService` with async `httpx.AsyncClient`, multipart upload to `{PAPERLESS_API_URL}/api/documents/post_document/`, authentication header `Authorization: Token {PAPERLESS_API_TOKEN}`, and resilient fallback archiving to `data/failed_uploads/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `../data-recording/.venv/bin/pytest ../data-recording/tests/test_paperless_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git -C ../data-recording add src/data_recorder/services/paperless_service.py tests/test_paperless_service.py
git -C ../data-recording commit -m "feat(services): implement resilient Paperless-ngx client with local archive fallback (fixes #9)"
```

---

### Task 4: Full Suite Verification & PR Preparation

**Files:**
- Modify: `data-recording/Dockerfile` (ensure failed_uploads dir is initialized)
- All test files

- [ ] **Step 1: Run complete test suite with coverage**

Run: `../data-recording/.venv/bin/pytest ../data-recording/tests -v --cov=data_recorder`
Expected: 100% passing tests, high coverage.

- [ ] **Step 2: Dockerfile verification**

Ensure `Dockerfile` creates `/app/data/failed_uploads` alongside `/app/data/uploads`.
Run Docker setup tests: `../data-recording/.venv/bin/pytest ../data-recording/tests/test_docker_setup.py -v`.

- [ ] **Step 3: Push feature branch and create Pull Request**

Push `feature/issue-9-exif-parser-paperless-client` to GitHub and create PR referencing `fixes #9`.
Update issue #9 labels: remove `in-progress`, add `needs-review`.
