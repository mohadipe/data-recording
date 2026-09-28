# Wertpapiere Kurs- und Bestandstrennung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trennung von reinem Tageskurs (`wkn_kurs_datum`), Stichtags-Anteilen (`wkn_bestand_datum`) und berechnetem Gesamtwert im Wertpapiere-Modul inklusive neuer Web-UI (`/depot`) zur Anteilsverwaltung und korrigierter Superset-Views.

**Architecture:** Duale Tabellenstruktur für Marktdaten (`wkn_kurs_datum`) und persönliche Bestände (`wkn_bestand_datum`). Der Hintergrund-Dienst `StockPriceService` speichert Yahoo-Finance-Schlusskurse in der Kurstabelle. Der Nutzer pflegt Anteile über eine neue Web-UI (`/depot`). Eine hybride SQL-View vereint alte Gesamtwert-Snapshots bis 07/2026 mit den neuen täglichen dynamischen Berechnungen ($\text{Anteile} \times \text{Tageskurs}$).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, APScheduler, Jinja2, Tailwind CSS, MySQL 8 (NAS), Apache Superset & PostgreSQL (Metadata), Docker.

**Spec:** [`docs/superpowers/specs/2026-09-28-wertpapiere-kurs-bestand-trennung-design.md`](file:///home/mohadipe/IdeaProjects/data-recording/docs/superpowers/specs/2026-09-28-wertpapiere-kurs-bestand-trennung-design.md)

## Global Constraints

- Keine Zerstörung historischer Gesamtwert-Snapshots in `wertpapiere.wkn_wert_datum` vor dem 2026-07-16.
- Bereinigung der 4 fehlerhaften Kurswert-Zeilen vom 2026-09-25 in `wkn_wert_datum` und Übertrag nach `wkn_kurs_datum`.
- Striktes TDD: Für jeden Code-Schritt zuerst fehlschlagenden Test schreiben, dann Implementierung, Test grün, committen.
- Alle 200+ bestehenden Pytest-Tests müssen weiterhin durchlaufen (`.venv/bin/pytest`).
- Deployment auf Synology NAS (`ssh nas`) via Docker ohne Downtime.

---

### Task 1: MySQL Migration & Datenbereinigung

**Files:**
- Create: `database/migrations/05_wertpapiere_kurs_bestand.sql`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Produces: Tabellen `wertpapiere.wkn_kurs_datum` und `wertpapiere.wkn_bestand_datum`, bereinigte `wkn_wert_datum`.

- [ ] **Step 1: Write migration SQL file**
Write `database/migrations/05_wertpapiere_kurs_bestand.sql`:
```sql
-- Migration 05: Trennung von Kursdaten und Anteilsbeständen
USE wertpapiere;

-- 1. Tabelle für tägliche Schlusskurse
CREATE TABLE IF NOT EXISTS wertpapiere.wkn_kurs_datum (
    id INT AUTO_INCREMENT PRIMARY KEY,
    wkn_id INT NOT NULL,
    datum DATE NOT NULL,
    kurs DECIMAL(10, 4) NOT NULL,
    erfasst_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wkn_kurs_etf FOREIGN KEY (wkn_id) REFERENCES wertpapiere.etf(id) ON DELETE CASCADE,
    UNIQUE KEY uq_wkn_kurs_wkn_datum (wkn_id, datum),
    INDEX idx_wkn_kurs_datum (datum)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Tabelle für Stichtags-Anteilsbestände
CREATE TABLE IF NOT EXISTS wertpapiere.wkn_bestand_datum (
    id INT AUTO_INCREMENT PRIMARY KEY,
    wkn_id INT NOT NULL,
    datum DATE NOT NULL,
    anteile DECIMAL(12, 4) NOT NULL,
    erfasst_am DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wkn_bestand_etf FOREIGN KEY (wkn_id) REFERENCES wertpapiere.etf(id) ON DELETE CASCADE,
    UNIQUE KEY uq_wkn_bestand_wkn_datum (wkn_id, datum),
    INDEX idx_wkn_bestand_datum (datum)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Datenmigration: Übertrage die 4 versehentlich als Kurswert eingetragenen Zeilen vom 2026-09-25
INSERT IGNORE INTO wertpapiere.wkn_kurs_datum (wkn_id, datum, kurs)
SELECT wkn_id, datum, wert
FROM wertpapiere.wkn_wert_datum
WHERE datum = '2026-09-25' AND wkn_id IN (1, 3, 4, 9);

-- 4. Bereinigung: Lösche die 4 Zeilen aus wkn_wert_datum
DELETE FROM wertpapiere.wkn_wert_datum
WHERE datum = '2026-09-25' AND wkn_id IN (1, 3, 4, 9);
```

- [ ] **Step 2: Update migrations test in `tests/test_migrations.py`**
Test verify migration file syntax and contents.

- [ ] **Step 3: Run pytest on migrations test**
Run: `.venv/bin/pytest tests/test_migrations.py -v`
Expected: PASS

- [ ] **Step 4: Execute migration on live NAS MySQL**
Run command:
`ssh nas "/usr/local/bin/docker exec -i mysql_db mysql -uroot -pS6YytgeKHJklKoshOuxz wertpapiere" < database/migrations/05_wertpapiere_kurs_bestand.sql`
Verify that `wkn_kurs_datum` has 4 rows and `wkn_wert_datum` no longer has rows from 2026-09-25.

- [ ] **Step 5: Commit**
```bash
git add database/migrations/05_wertpapiere_kurs_bestand.sql tests/test_migrations.py
git commit -m "feat(db): Migration 05 für wkn_kurs_datum und wkn_bestand_datum mit Datenbereinigung"
```

---

### Task 2: SQLAlchemy Models für Kurse und Bestände

**Files:**
- Modify: `src/data_recorder/models/wertpapiere.py`
- Modify: `tests/test_models_wertpapiere.py`

**Interfaces:**
- Produces:
  - `WknKursDatum(id, wkn_id, datum, kurs, erfasst_am, etf)`
  - `WknBestandDatum(id, wkn_id, datum, anteile, erfasst_am, etf)`
  - `Etf.kurs_daten: list[WknKursDatum]`
  - `Etf.bestand_daten: list[WknBestandDatum]`

- [ ] **Step 1: Write failing tests in `tests/test_models_wertpapiere.py`**
Add `test_wkn_kurs_datum_crud_and_relationship` and `test_wkn_bestand_datum_crud_and_relationship`.
Verify relationships from `Etf` to `WknKursDatum` and `WknBestandDatum`.

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_models_wertpapiere.py -v`
Expected: FAIL (ImportError or AttributeError for WknKursDatum / WknBestandDatum)

- [ ] **Step 3: Implement models in `src/data_recorder/models/wertpapiere.py`**
Implement `WknKursDatum`, `WknBestandDatum` and update `Etf` with relationships.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_models_wertpapiere.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/data_recorder/models/wertpapiere.py tests/test_models_wertpapiere.py
git commit -m "feat(models): WknKursDatum und WknBestandDatum SQLAlchemy-Models implementiert"
```

---

### Task 3: Backend Service Update (`StockPriceService`)

**Files:**
- Modify: `src/data_recorder/services/stock_price_service.py`
- Modify: `tests/test_stock_price_service.py`

**Interfaces:**
- Consumes: `WknKursDatum` from Task 2
- Produces: `StockPriceService.save_stock_price(wkn_id, datum, kurs, session) -> WknKursDatum`

- [ ] **Step 1: Write failing tests in `tests/test_stock_price_service.py`**
Update existing tests so `save_stock_price` and `poll_and_save` expect `WknKursDatum` instances with `kurs` attribute instead of `WknWertDatum`.

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_stock_price_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement changes in `src/data_recorder/services/stock_price_service.py`**
- Import `WknKursDatum` instead of `WknWertDatum`.
- Change `save_stock_price` to query and save to `WknKursDatum` with column `kurs`.
- Return `WknKursDatum` in `_process_securities` and `poll_and_save`.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_stock_price_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/data_recorder/services/stock_price_service.py tests/test_stock_price_service.py
git commit -m "feat(service): StockPriceService speichert Schlusskurse in wkn_kurs_datum"
```

---

### Task 4: REST-API Holdings CRUD & Kursabfrage Endpunkte

**Files:**
- Modify: `src/data_recorder/api/routes_finance.py`
- Modify: `tests/test_api_finance.py`

**Interfaces:**
- Consumes: `WknKursDatum`, `WknBestandDatum`, `StockPriceService`
- Produces:
  - `POST /api/finance/update-prices` (uses `WknKursDatum`)
  - `GET /api/finance/latest-prices` (returns latest quotes from `WknKursDatum`)
  - `GET /api/finance/holdings` (returns active securities + current shares + current price + total value)
  - `GET /api/finance/holdings/history` (list of share entries)
  - `POST /api/finance/holdings` (create/update shares entry)
  - `DELETE /api/finance/holdings/{id}` (delete shares entry)

- [ ] **Step 1: Write failing tests in `tests/test_api_finance.py`**
Add tests for:
- `test_holdings_crud_endpoints` (GET, POST, DELETE)
- `test_holdings_history_endpoint`
- Update `test_update_prices_endpoint_success` and `test_get_latest_prices_endpoint` to verify `WknKursDatum`.

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_api_finance.py -v`
Expected: FAIL (404 on /holdings or schema mismatch)

- [ ] **Step 3: Implement endpoints and schemas in `src/data_recorder/api/routes_finance.py`**
Implement Pydantic models:
- `HoldingItemResponse`: `wkn_id`, `wkn`, `isin`, `name`, `ticker`, `anteile`, `bestand_datum`, `kurs`, `kurs_datum`, `gesamtwert`
- `HoldingHistoryItemResponse`: `id`, `wkn_id`, `wkn`, `name`, `datum`, `anteile`, `erfasst_am`
- `CreateHoldingRequest`: `wkn_id`, `datum`, `anteile`
Implement the endpoints with proper database session management, validation, and error responses.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_api_finance.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/data_recorder/api/routes_finance.py tests/test_api_finance.py
git commit -m "feat(api): Holdings CRUD und aktualisierte Kurs-Endpunkte implementiert"
```

---

### Task 5: Web-UI Template & Navigation (`/depot`)

**Files:**
- Create: `src/data_recorder/templates/depot.html`
- Modify: `src/data_recorder/templates/base.html`
- Modify: `src/data_recorder/api/routes_finance.py` (Add HTML template route `GET /depot`)
- Create: `tests/test_depot_ui.py`

**Interfaces:**
- Consumes: `/api/finance/holdings`, `/api/finance/update-prices`
- Produces: HTML page `GET /depot` for desktop & mobile.

- [ ] **Step 1: Write failing UI tests in `tests/test_depot_ui.py`**
Verify `client.get("/depot")` returns 200 with HTML, contains title "Depot", link to navigation, and table elements.

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_depot_ui.py -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Implement `depot.html` template and route**
- In `src/data_recorder/templates/base.html`: Add nav link `<a href="/depot">Depot</a>`.
- In `src/data_recorder/templates/depot.html`: Dark-mode Tailwind page with:
  - Header: KPI card for Gesamt-Depotwert, letzte Kursaktualisierung, Button "Kurse jetzt abrufen".
  - Table / Card list of active securities with button "Bestand erfassen".
  - Modal / Form for entering `datum` and `anteile`.
  - History list of past holdings entries with delete button.
- In `src/data_recorder/api/routes_finance.py`: Add route `GET /depot` rendering `depot.html` via Jinja2Templates.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_depot_ui.py -v`
Expected: PASS

- [ ] **Step 5: Run full pytest suite**
Run: `.venv/bin/pytest -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**
```bash
git add src/data_recorder/templates/depot.html src/data_recorder/templates/base.html src/data_recorder/api/routes_finance.py tests/test_depot_ui.py
git commit -m "feat(ui): Web-UI Seite /depot für Anteilsverwaltung und Kursaktualisierung"
```

---

### Task 6: SQL Views für Superset (`04_view_portfolio_performance.sql` & `05_view_portfolio_uebersicht_aktuell.sql`)

**Files:**
- Modify: `database/views/04_view_portfolio_performance.sql`
- Modify: `database/views/05_view_portfolio_uebersicht_aktuell.sql`
- Modify: `database/migrations/04_superset_views.sql`

**Interfaces:**
- Produces: Updated SQL views in `wertpapiere` on NAS MySQL.

- [ ] **Step 1: Update `database/views/04_view_portfolio_performance.sql`**
Implement the hybrid query:
- CTE uniting `wkn_wert_datum` (`datum <= '2026-07-16'`) and `wkn_kurs_datum` (with latest `anteile * kurs`).
- Columns: `source_id`, `datum`, `wkn_id`, `wkn`, `isin`, `name`, `ticker_yahoo`, `typ`, `aktiv`, `kurs`, `anteile`, `depotwert`, `kumuliertes_invest`, `kumulierter_ertrag`, `gesamtwert_inkl_ertrag`, `gewinn_verlust_euro`, `rendite_prozent`.

- [ ] **Step 2: Update `database/views/05_view_portfolio_uebersicht_aktuell.sql`**
Implement query using:
- Latest `kurs` from `wkn_kurs_datum`
- Latest `anteile` from `wkn_bestand_datum`
- `aktueller_wert = COALESCE(anteile * kurs, fallback_wkn_wert_datum)`
- `invest_gesamt`, `ertrag_gesamt`, `gesamtwert_inkl_ertrag`, `gewinn_verlust_euro`, `rendite_gesamt_prozent`.

- [ ] **Step 3: Update `database/migrations/04_superset_views.sql` to stay in sync**

- [ ] **Step 4: Deploy views to NAS MySQL**
Run command:
`ssh nas "/usr/local/bin/docker exec -i mysql_db mysql -uroot -pS6YytgeKHJklKoshOuxz wertpapiere" < database/views/04_view_portfolio_performance.sql`
`ssh nas "/usr/local/bin/docker exec -i mysql_db mysql -uroot -pS6YytgeKHJklKoshOuxz wertpapiere" < database/views/05_view_portfolio_uebersicht_aktuell.sql`
Verify views execute without error on NAS.

- [ ] **Step 5: Commit**
```bash
git add database/views/04_view_portfolio_performance.sql database/views/05_view_portfolio_uebersicht_aktuell.sql database/migrations/04_superset_views.sql
git commit -m "feat(views): Hybride Portfolio-Views mit dynamischer Kurs- und Bestandsberechnung"
```

---

### Task 7: Superset Metadata & Dashboard Synchronisation

**Files:**
- Superset PostgreSQL metadata on NAS: `superset_postgres`

**Interfaces:**
- Produces: Synchronized columns and metrics for datasets 63 & 64, verified dashboard 2.

- [ ] **Step 1: Check and update columns in `superset_postgres`**
Query `table_columns` for table_id 63 and 64 in `superset_postgres`. Add new column records (`kurs`, `anteile`) if not present.
Flush Redis cache (`docker exec -i superset redis-cli flushall`).

- [ ] **Step 2: Verify queries from Superset container**
Execute a test query in Superset against `wertpapiere.view_portfolio_performance` and `wertpapiere.view_portfolio_uebersicht_aktuell`.

- [ ] **Step 3: Commit any metadata sync scripts**
```bash
git add .
git commit -m "chore(superset): Datasets 63 und 64 mit neuen Kurs- und Bestands-Spalten synchronisiert"
```

---

### Task 8: Docker Rebuild, Push & Deployment auf Synology NAS

**Files:**
- Docker image `mohadipe/data-recording:latest`

- [ ] **Step 1: Run full test suite locally**
Run: `.venv/bin/pytest -v`
Expected: ALL PASS (100% clean)

- [ ] **Step 2: Build and push Docker image**
Run:
`docker build --platform linux/amd64 -t mohadipe/data-recording:latest .`
`docker push mohadipe/data-recording:latest`

- [ ] **Step 3: Update container on Synology NAS**
Run via `ssh nas`:
`/usr/local/bin/docker pull mohadipe/data-recording:latest`
`cd /volume1/docker/data-recording && /usr/local/bin/docker-compose up -d --force-recreate`

- [ ] **Step 4: Verify live health and test Web-UI `/depot`**
Run:
`curl -s http://192.168.2.125:8000/api/health`
`curl -s http://192.168.2.125:8000/depot | head -n 30`

- [ ] **Step 5: Final review and report to user**
