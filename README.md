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

### 3. Anwendung lokal starten
```bash
uvicorn data_recorder.main:app --host 0.0.0.0 --port 9015 --reload
```

Die interaktive API-Dokumentation (Swagger UI) ist erreichbar unter:
* [http://localhost:9015/docs](http://localhost:9015/docs)
* Health-Check: `GET http://localhost:9015/health`

---

## 🐳 Docker & Container Deployment

Das Projekt stellt ein schlankes, sicheres Multi-Stage Docker-Image bereit:
* **Basis:** `python:3.12-slim` (Multi-Stage Build)
* **Sicherheit:** Kein Root-User im Container (`USER appuser`, UID 1000)
* **Imagegröße:** Strikt minimiert (~100 MB komprimiert / schlanke Runtime ohne Build-Tools)
* **Health-Check:** Integrierter Docker-Healthcheck für den Endpoint `/health`

### 1. Docker Image manuell bauen & starten

```bash
# 1. Image bauen
docker build -t data-recorder .

# 2. Container starten (mit .env und Port-Freigabe 9015)
docker run -d \
  --name data-recorder \
  -p 9015:9015 \
  --env-file .env \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/data/uploads:/app/data/uploads" \
  data-recorder:latest

# 3. Healthcheck testen
curl http://localhost:9015/health
```

### 2. Lokaler Start via Docker Compose

```bash
# 1. Konfiguration sicherstellen
cp -n .env.example .env

# 2. Container im Hintergrund starten
docker compose up -d

# 3. Logs ansehen
docker compose logs -f data-recorder

# 4. Container stoppen
docker compose down
```

---

## 🖥️ Bereitstellung auf der Synology DiskStation (Container Manager)

Der Dienst ist für den dauerhaften Betrieb auf der **Synology DiskStation (DSM 7.2+)** via **Container Manager** optimiert.

### Voraussetzungen auf der Synology
* **Container Manager** Paket über das DSM Paketzentrum installiert.
* **MariaDB 10 / MySQL** auf dem NAS aktiv (z. B. auf Port `3306`).
* Berechtigter Datenbank-Benutzer (`recorder`) mit Zugriff auf `verbrauch` und `wertpapiere`.

---

### Schritt-für-Schritt-Anleitung für Synology Container Manager

#### Schritt 1: Projektverzeichnis auf dem NAS anlegen
Erstelle auf dem gemeinsamen Ordner `docker` (z. B. via File Station oder SSH) folgendes Verzeichnis:
```text
/volume1/docker/data-recording/
├── docker-compose.yml
├── .env
├── logs/
└── data/
    └── uploads/
```

#### Schritt 2: Dateien bereitstellen
1. Kopiere `docker-compose.yml` aus diesem Repository nach `/volume1/docker/data-recording/docker-compose.yml`.
2. Kopiere `.env.example` nach `/volume1/docker/data-recording/.env` und passe die Zugangsdaten an:
   ```env
   ENVIRONMENT=production
   DB_HOST=192.168.2.125
   DB_PORT=3306
   DB_USER=recorder
   DB_PASSWORD=<dein_sicheres_passwort>
   DB_NAME_VERBRAUCH=verbrauch
   DB_NAME_WERTPAPIERE=wertpapiere
   EBUSD_URL=http://192.168.2.125:58888/data
   PAPERLESS_API_URL=http://192.168.2.125:8000/api
   PAPERLESS_API_TOKEN=<dein_paperless_token>
   ```

#### Schritt 3: Dateiberechtigungen für Non-Root-User (UID 1000)
Da der Container aus Sicherheitsgründen als `appuser` (**UID 1000**) läuft, müssen die Mount-Ordner für diese UID beschreibbar sein:
```bash
# Auf der Synology via SSH:
cd /volume1/docker/data-recording
mkdir -p logs data/uploads
sudo chown -R 1000:1000 logs data/uploads
chmod -R 775 logs data/uploads
```

#### Schritt 4: Projekt im Container Manager erstellen
1. Öffne den **Container Manager** im DSM.
2. Navigiere im linken Menü auf **Projekt** und klicke auf **Erstellen**.
3. **Projektname:** `data-recording`
4. **Pfad:** `/docker/data-recording` auswählen.
5. **Quelle:** *Bestehende docker-compose.yml verwenden* wählen. Der Container Manager erkennt automatisch die abgelegte `docker-compose.yml` und die `.env`-Datei.
6. Klicke auf **Weiter** und anschließend auf **Fertigstellen** (Projekt nach Erstellung starten).

#### Schritt 5: Netzwerk & Erreichbarkeit von MySQL auf dem NAS
* Standardmäßig bindet sich das Projekt an das Bridge-Netzwerk `synology_default` ein.
* Um die native MySQL/MariaDB auf dem NAS zu erreichen, verwende in der `.env` die LAN-IP der DiskStation (`192.168.2.125`).
* **Alternative (Host-Netzwerk):** Falls kein Port-Forwarding gewünscht ist und MySQL direkt über `127.0.0.1` angesprochen werden soll, kann in `docker-compose.yml` beim Service `network_mode: host` gesetzt werden (in diesem Fall die Zeilen `ports:` und `networks:` auskommentieren).

#### Schritt 6: Status & Health-Check verifizieren
* Im Container Manager wird der Status des Containers mit grünem Herzsymbol (**healthy**) angezeigt.
* Im Browser oder Terminal prüfen:
  ```bash
  curl http://192.168.2.125:9015/health
  ```
  Erwartete Antwort:
  ```json
  {"status":"ok","version":"0.1.0","app_name":"data-recorder"}
  ```

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
├── .dockerignore                 # Build-Context Ausschlussliste für schlankes Docker-Image
├── .env.example                 # Vorlage für Umgebungsvariablen
├── database/                    # SQL-Dumps & Schemas (verbrauch, wertpapiere)
├── docker-compose.yml           # Docker Compose Spezifikation (Synology & Lokal)
├── Dockerfile                   # Multi-Stage Dockerfile (python:3.12-slim, Non-Root)
├── docs/                        # Richtlinien & Spezifikationen
├── logs/                        # Lokaler Log-Mount (.gitkeep)
├── data/
│   └── uploads/                 # Upload-Puffer für Zählerstand-Fotos (.gitkeep)
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
