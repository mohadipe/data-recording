# Phase 2.2: Mobile Web-UI – Foto-Wizard für monatliche Zählererfassung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a responsive, touch- and smartphone-optimized Web-UI wizard for monthly meter readings with photo upload, automatic EXIF date extraction, live plausibility calculation, DB persistence in `verbrauch.messwerte`, asynchronous Paperless-ngx upload, and PWA support.

**Architecture:**
- `api/routes_wizard.py`: FastAPI routes for:
  - `GET /` & `GET /wizard`: Serves the Jinja2 wizard page.
  - `GET /manifest.json`: PWA manifest.
  - `GET /api/zaehler`: List active meters.
  - `GET /api/zaehler/{zaehler_id}/latest`: Get latest reading, date, and unit for a meter.
  - `POST /api/wizard/extract-date`: Extracts EXIF capture date from uploaded receipt image.
  - `POST /wizard/submit` & `POST /api/wizard/submit`: Accepts multipart form (`zaehler_id`, `datum`, `wert`, `foto`), stores reading in `verbrauch.messwerte`, triggers asynchronous Paperless-ngx upload via `BackgroundTasks`, and returns confirmation.
- `templates/wizard.html`: Mobile-first Jinja2 template with Tailwind CSS, camera capture `<input type="file" accept="image/*" capture="environment">`, 3-step wizard flow, live difference calculation, and negative value warnings.
- `static/`: Static assets including `manifest.json`, high-resolution touch icons (`icon-192.png`, `icon-512.png`, `apple-touch-icon.png`), and custom styles.
- `main.py`: Mounts static directory, templates, and includes wizard routes.

**Tech Stack:** Python 3.12+, FastAPI, Jinja2, TailwindCSS, Pillow, pillow-heif, SQLAlchemy 2.0, httpx, pytest, pytest-asyncio.

---

### Task 1: PWA Manifest & App Icons Setup

**Files:**
- Create: `src/data_recorder/static/manifest.json`
- Create: `src/data_recorder/static/icons/` with generated icons
- Modify: `pyproject.toml` (package data inclusion)
- Create: `tests/test_pwa_assets.py`

- [ ] **Step 1: Write failing test for PWA manifest and icons**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Generate icons and write manifest.json**
- [ ] **Step 4: Update pyproject.toml to include static assets and templates**
- [ ] **Step 5: Run test to verify it passes**
- [ ] **Step 6: Commit changes**

---

### Task 2: API Endpoints for Active Meters, Latest Reading & EXIF Date Extraction

**Files:**
- Create: `src/data_recorder/api/routes_wizard.py`
- Modify: `src/data_recorder/main.py`
- Create: `tests/test_api_wizard.py`

- [ ] **Step 1: Write failing tests for `/api/zaehler`, `/api/zaehler/{id}/latest`, and `/api/wizard/extract-date`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement endpoints in `src/data_recorder/api/routes_wizard.py` and register in `main.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit changes**

---

### Task 3: Meter Reading Submission & Asynchronous Paperless Upload

**Files:**
- Modify: `src/data_recorder/api/routes_wizard.py`
- Modify: `tests/test_api_wizard.py`

- [ ] **Step 1: Write failing tests for `POST /wizard/submit` and `POST /api/wizard/submit` with multipart form data**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement database persistence and background Paperless upload**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit changes**

---

### Task 4: Mobile-First Jinja2 Template & Wizard Frontend

**Files:**
- Create: `src/data_recorder/templates/base.html`
- Create: `src/data_recorder/templates/wizard.html`
- Modify: `src/data_recorder/api/routes_wizard.py` (render HTML on GET)
- Create: `tests/test_wizard_ui.py`

- [ ] **Step 1: Write failing test verifying HTML template rendering, active meters list, and step elements**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `base.html` and `wizard.html` with responsive Tailwind UI, touch controls, camera input, and live plausibility logic**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit changes**

---

### Task 5: End-to-End Integration Tests & Verification

**Files:**
- Create/Extend: `tests/test_wizard_integration.py`

- [ ] **Step 1: Run comprehensive wizard integration test suite covering the full 3-step workflow**
- [ ] **Step 2: Verify all 40+ existing tests and new tests pass cleanly**
- [ ] **Step 3: Commit changes**

---

### Task 6: Push Branch, Inline Code Review & Pull Request

- [ ] **Step 1: Git push feature branch to origin**
- [ ] **Step 2: Conduct inline code review against acceptance criteria**
- [ ] **Step 3: Create Pull Request with evidence**
- [ ] **Step 4: Update Issue labels and add comment**
