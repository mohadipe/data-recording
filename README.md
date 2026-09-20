# 📊 Data-Recording (Python 3.12 FastAPI)

Zentraler, leichtgewichtiger Datenerfassungs- und Automatisierungs-Daemon für Haus-, Energie- und Finanzdaten auf der **Synology DiskStation**.

---

## 🚀 Schnellstart & Lokale Entwicklung

### 1. Virtuelle Umgebung erstellen und Abhängigkeiten installieren
```bash
# Mit uv (empfohlen):
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Oder mit pip:
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Konfiguration anlegen
Kopiere die Vorlage und passe die Werte bei Bedarf an:
```bash
cp .env.example .env
```

### 3. Anwendung starten
```bash
uvicorn data_recorder.main:app --host 0.0.0.0 --port 9015 --reload
```

Die interaktive API-Dokumentation (Swagger UI) ist erreichbar unter:
* [http://localhost:9015/docs](http://localhost:9015/docs)
* Health-Check: `GET http://localhost:9015/health`

---

## 🧪 Tests & Qualitätssicherung

```bash
# Tests ausführen
pytest tests/ -v

# Tests mit Coverage-Report ausführen
pytest tests/ --cov=data_recorder --cov-report=term-missing
```

---

## 📁 Projektstruktur

```text
data-recording/
├── .env.example                 # Vorlage für Umgebungsvariablen
├── database/                    # SQL-Dumps & Schemas (verbrauch, wertpapiere)
├── docs/                        # Richtlinien & Spezifikationen
├── pyproject.toml               # Projektkonfiguration & Dependencies (PEP 621)
├── src/
│   └── data_recorder/
│       ├── __init__.py
│       ├── main.py              # FastAPI Application & Lifespan Hooks
│       ├── api/                 # REST Router (Skinny Controllers)
│       │   ├── __init__.py
│       │   └── routes_health.py # Health-Check Endpoint
│       └── core/                # Fundament
│           ├── __init__.py
│           ├── config.py        # Pydantic Settings (.env)
│           ├── database.py      # SQLAlchemy 2.0 Engine & Sessions
│           └── logging.py       # Zentrales Logging
└── tests/                       # Pytest Testsuite (100% Offline)
```
