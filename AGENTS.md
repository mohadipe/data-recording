# 🤖 Data-Recording – Agent Rules & Development Guidelines

Dieses Dokument definiert die verbindlichen Standards und Arbeitsregeln für KI-Coding-Assistenten (**Gibbs 2.0**, **Antigravity** und autonome Subagenten), die in diesem Repository arbeiten.

---

## 🎯 1. Projekt-Kontext & Rolle des Agenten

* **Zweck:** `data-recording` ist der zentrale, leichtgewichtige Datenerfassungs- und Automatisierungs-Daemon für Haus-, Energie- und Finanzdaten auf der **Synology DiskStation (`192.168.2.125`)**.
* **Auswertung:** Alle Daten fließen in bestehende MySQL-Datenbanken (`verbrauch`, `wertpapiere`, lesend `hibiscus`) und werden über **Apache Superset** visualisiert.
* **Arbeitsweise von Gibbs:**
  * Gibbs arbeitet autonom GitHub-Issues mit dem Label **`agent:gibbs`** ab.
  * Jedes Issue wird in sich geschlossen implementiert, mit Tests abgesichert und per Git committet.
  * Manuelle Schritte des Nutzers (Backups, API-Tokens, physische Zähler) sind mit **`user:manual`** markiert und werden vom Agenten **nicht** angerührt, sondern als Voraussetzung dokumentiert.

---

## 📐 2. Architektur- & Technologie-Standards

1. **Sprache & Laufzeitumgebung:**
   * **Python 3.12+** ist verbindlich.
   * **Strikte Typisierung:** Alle Funktionen, Klassen und Methoden müssen Type-Hints (`typing`) besitzen.
   * Keine undokumentierten `Any`-Typen in Schnittstellen.
2. **Framework & Schichten-Architektur:**
   * **FastAPI** als REST- und Web-Framework.
   * **Service- & Repository-Pattern:**
     * `api/`: Reine Routen-Handler (Skinny Controller), keine Geschäfts- oder DB-Logik.
     * `services/`: Fachlogik (eBUS-Parser, EXIF-Extraktion, Paperless-Client, Yahoo-Finance-Client, Hibiscus-Scanner).
     * `models/` & `db/`: SQLAlchemy 2.0 ORM-Klassen und Session-Handling.
     * `core/`: Konfiguration (`pydantic-settings`), Logging und APScheduler.
3. **Datenbank & ORM:**
   * **SQLAlchemy 2.0** mit `pymysql` Driver.
   * Keine harten Raw-SQL-Statements für Inserts/Updates – alles über ORM oder typisierte Core-Statements.
   * Unterstützung für Multi-Schema (`verbrauch.*`, `wertpapiere.*`).
4. **Idempotenz (Höchste Priorität):**
   * Alle Hintergrund-Jobs (stündliches eBUS-Polling, tägliche Tradegate-Kurse, Hibiscus-Transaktions-Sync) müssen **strikt idempotent** sein.
   * Ein doppelter Lauf am selben Tag darf niemals doppelte Datensätze erzeugen (Verwendung von Unique Constraints auf `datum + entity_id` bzw. `ON DUPLICATE KEY UPDATE`).
5. **Resilienz & Defensive Programmierung (Zero Crash Policy):**
   * Externe Schnittstellen (`ebusd`, Yahoo Finance, Paperless-ngx, Tecson/Ölpreis-Scraper) können temporär offline sein oder Timeouts werfen.
   * **Regel:** Der Container darf **niemals** wegen eines externen Netzwerkfehlers abstürzen!
   * Alle externen Aufrufe müssen in Try-Except-Blöcken gekapselt werden, Fehler sauber mit `logger.warning` protokollieren und beim nächsten Intervall wiederholen.
   * Bei Paperless-Ausfall: Zählerstand in MySQL speichern, Bild lokal puffern und Warnung loggen.

---

## 🧪 3. Test-Strategie (TDD & 100% Offline)

* **Framework:** `pytest`, `pytest-asyncio`, `pytest-cov`.
* **Keine externen Live-Aufrufe im Test:**
  * Tests dürfen **niemals** echte Netzwerkverbindungen zu `192.168.2.125`, Yahoo Finance oder Tradegate aufbauen.
  * Alle externen APIs (`httpx`, Web-Scraping, Paperless) werden mit Mocks / Fixtures (`respx` oder `unittest.mock`) getestet.
* **Test-Datenbank:**
  * Datenbank-Tests laufen standardmäßig gegen SQLite In-Memory (`sqlite:///:memory:`).
* **Test-Pflicht vor jedem Commit:**
  * Ein Issue gilt erst als gelöst, wenn alle Tests fehlerfrei durchlaufen:
    ```bash
    pytest tests/ -v
    ```

---

## 🔒 4. Sicherheit & Secrets

* **Niemals Passwörter, API-Tokens oder Credentials committen!**
* Alle Zugangsdaten (MySQL-Passwörter, Paperless-Tokens) werden ausschließlich über Umgebungsvariablen via `pydantic-settings` und `.env` geladen.
* Eine bereinigte `.env.example` mit Dummy-Werten muss immer synchron mit dem Code gepflegt werden.

---

## 📦 5. Git- & Commit-Konventionen

* **Conventional Commits:**
  * `feat(scope): kurze Beschreibung (fixes #X)`
  * `fix(scope): kurze Beschreibung (fixes #X)`
  * `test(scope): tests hinzugefügt`
  * `refactor(scope): code bereinigt`
  * `docs(scope): dokumentation aktualisiert`
  * `chore(scope): build oder dependencies angepasst`
* **Issue-Verlinkung:** Jeder Commit zur Umsetzung eines Issues muss die GitHub-Issue-Nummer referenzieren (z. B. `fixes #6`).
