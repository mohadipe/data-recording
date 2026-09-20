# 🏗️ Architektur-, Entwicklungs- & Test-Richtlinien (Data-Recording)

Dieses Dokument ist das verbindliche technische Handbuch für die Entwicklung im Projekt `data-recording`. Es überträgt die bewährten Standards aus dem Quartett-Projekt auf den Python- und Daten-Erfassungs-Stack.

---

## 1. Schichtenarchitektur & Modul-Entkopplung

Die Anwendung folgt einer strikten Trennung zwischen Präsentation (API/Web), Geschäftslogik (Services), Persistenz (Datenbank) und Hintergrund-Automatisierung (Scheduler):

```text
src/data_recorder/
├── api/                   # Web & REST Schnittstelle (FastAPI Router)
│   ├── routes_zaehler.py  # Endpunkte für Zähler-Upload & Wizard
│   ├── routes_finance.py  # Endpunkte für Finanzen
│   └── routes_ebus.py     # Endpunkte für eBUS-Status & Trigger
├── core/                  # Fundament
│   ├── config.py          # Pydantic Settings (.env)
│   ├── database.py        # SQLAlchemy Engine & Session Generator
│   ├── logging.py         # Zentrales JSON-/Text-Logging
│   └── scheduler.py       # APScheduler Initialisierung & Jobs
├── models/                # SQLAlchemy 2.0 ORM Klassen
│   ├── verbrauch.py       # Zaehler, Messwerte, Waermepumpe, Heizoel
│   └── wertpapiere.py     # Etf, WknInvest, WknWert, WknErtrag
├── services/              # Reine Geschäftslogik (Reines Python, testbar ohne HTTP)
│   ├── ebus_service.py    # ebusd Client & Messwert-Extraktion
│   ├── exif_service.py    # Extraktion von Aufnahme-Zeitstempeln aus Fotos
│   ├── paperless_service.py # Upload & Tagging in Paperless-ngx
│   ├── stock_service.py   # Yahoo Finance / Tradegate Kurse
│   ├── hibiscus_service.py # WKN-Parsing & Sparplan-Zuordnung
│   └── oil_service.py     # Regionaler Tecson/Esyoil Scraper
├── templates/             # Jinja2 HTML Templates für Smartphone UI
└── main.py                # App-Einstiegspunkt & Lifecycle-Hooks
```

---

## 2. Die 5 Goldenen Architekturregeln

### Regel 1: Skinny Endpoints (Reine Controller)
* Router-Funktionen in `api/` enthalten **keine** Berechnungen, keine Business-Logik und keine direkten externen HTTP-Aufrufe.
* Router validieren ausschließlich den Request (via Pydantic-Schema oder Form-Upload), rufen den zuständigen Service auf und geben das Response-Model oder gerenderte Template zurück.

### Regel 2: Strikt idempotente Datenerfassung
* Ein Job oder API-Call, der mehrmals für denselben Tag oder Zeitpunkt aufgerufen wird, darf niemals zu Duplikaten führen.
* **Technisches Muster:**
  * In MySQL besitzen Tabellen eindeutige Schlüssel (z. B. `UNIQUE KEY uq_zaehler_datum (zaehler_id, datum)` oder `UNIQUE KEY uq_wkn_datum (wkn_id, datum)`).
  * Services nutzen entweder `INSERT ... ON DUPLICATE KEY UPDATE` oder prüfen die Existenz vor dem Schreiben.

### Regel 3: Zero-Crash Policy bei Netzwerk- & Service-Ausfällen
* Das NAS läuft 24/7. Externe Dienste (wie das Internet, der eBUS-Adapter oder Paperless-ngx) sind naturgemäß nicht 100% verfügbar.
* **Regel:** Jeder Netzwerkaufruf an Drittsysteme muss defensiv abgesichert sein:
  ```python
  try:
      response = await client.get(ebus_url, timeout=5.0)
      response.raise_for_status()
      data = response.json()
  except (httpx.RequestError, httpx.HTTPStatusError) as exc:
      logger.warning(f"eBUS nicht erreichbar: {exc}. Job wird beim nächsten Zyklus wiederholt.")
      return None
  ```
* Die FastAPI-App darf bei Scheduler-Fehlern unter keinen Umständen beendet werden.

### Regel 4: Entkopplung von Speichern und Archivieren
* Wenn ein Nutzer einen Zählerstand über das Handy eingibt und das Foto hochlädt:
  1. Der Zählerstand wird **sofort** in MySQL committet (Primärziel: Datenverlust vermeiden).
  2. Der Upload nach Paperless-ngx erfolgt asynchron im Hintergrund oder mit Fallback:
     Falls Paperless offline ist, wird das Bild im lokalen Verzeichnis `/data/failed_uploads/` zwischengespeichert und ein Warning geloggt. Der Nutzer erhält trotzdem eine Erfolgsmeldung für seinen Zählerstand.

### Regel 5: Umfassende Typisierung (Type Hints)
* Alle Service-Methoden und Models müssen explizite Type-Hints tragen.
* Optionale Rückgabewerte müssen mit `Optional[T]` versehen sein.
* Flake8/Ruff und Type-Checker müssen ohne Warnungen durchlaufen.

---

## 3. Test-Strategie & Mocking-Standards

Tests sind für Gibbs das Qualitätsnetzwerk. Es gelten folgende Vorgaben:

### 3.1 Unabhängigkeit von externer Infrastruktur
* Tests laufen im CI-Runner oder lokal auf Gibbs **ohne** Zugriff auf das NAS, ohne Internet und ohne echte MySQL-Datenbank.
* **Datenbank:** Tests verwenden SQLite In-Memory:
  ```python
  @pytest.fixture
  def db_session():
      engine = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(bind=engine)
      with Session(engine) as session:
          yield session
  ```
* **HTTP-Mocks:** Externe HTTP-Aufrufe (`ebusd`, Paperless, Yahoo Finance, Scraper) werden via `respx` oder `unittest.mock.AsyncMock` vollständig gemockt.

### 3.2 Pflicht-Testkategorien für jedes Issue
1. **Unit-Tests:**
   * Parser-Logik (EXIF-Extraktion aus synthetischen Testbildern).
   * Berechnungen (COP-Formel: `(YieldHeating + YieldHotWater) / (EnergyInputHeating + EnergyInputHotWater)`).
   * Regex-Matching von WKNs aus unterschiedlichen Hibiscus-Buchungstexten.
2. **Integration-Tests:**
   * FastAPI TestClient: Endpunkte mit validen und ungültigen Payloads testen.
   * SQLAlchemy CRUD-Zyklen (Create, Read, Update, Idempotenz).

---

## 4. Release- & Dokumentations-Standards

* **README.md** muss stets den aktuellen Installations- und Startbefehl für den Synology Container Manager widerspiegeln.
* **SQL-Dateien:** Jede Änderung am Datenbank-Schema muss in einem neuen Migrations-Skript unter `database/migrations/` mit aufsteigender Nummerierung abgelegt werden.
