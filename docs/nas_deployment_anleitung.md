# 🚀 Release- & Deployment-Anleitung: Data-Recording auf Synology NAS (`nas-infra`)

Dieses Dokument beschreibt Schritt für Schritt, wie die neue Python 3.12 Anwendung `data-recording` gebaut, als Docker-Image bereitgestellt und in das bestehende **`nas-infra` (Stack 03: Apps)** auf der Synology DiskStation DS218+ (`192.168.2.125`) deployed wird.

---

## 🏛️ 1. Architektur-Einordnung im `nas-infra` Stack

Das gestern aufgesetzte Repository [`nas-infra`](../../nas-infra/README.md) verwaltet alle Container der Synology in 5 modular getrennten Stacks, die über das gemeinsame Docker-Netzwerk **`nas_lan`** kommunizieren:

* **Stack 01 (`01_smarthome`):** `ebusd` läuft auf Port `58888` (intern: `http://ebusd:8888/data`)
* **Stack 02 (`02_database`):** `mysql_db` läuft auf Port `3306` (intern: `mysql_db:3306`), phpMyAdmin auf Port `48080`
* **Stack 03 (`03_apps`):** Paperless-ngx (`http://paperless-webserver-1:8000`) & **`Data-Recording`** (Port `9015`)
* **Stack 04 (`04_analytics`):** Apache Superset (Port `8088`)
* **Stack 05 (`05_monitoring`):** Grafana (Port `3001`) & Loki (Port `3100`)

Dadurch benötigt `Data-Recording` keine Host-IPs im Docker-Netzwerk, sondern spricht Datenbank, eBUS und Paperless direkt über deren Docker-DNS-Namen im `nas_lan` an.

---

## 📦 2. Zweistufiger Release- & Rollout-Prozess (Automatisiert)

Der Bereitstellungsprozess ist in zwei getrennte, sichere Stufen aufgeteilt:

```
┌─────────────────────────────────┐
│ Stufe 1: GitHub Actions CI/CD   │
│ - Tag Push (v*.*.*)             │ ──► ghcr.io/mohadipe/data-recorder:latest
│ - Multi-Stage Build & Args      │ ──► GitHub Release & Changelog
│ - Push zu GHCR                  │
└─────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Stufe 2: NAS Deployment-Skript  │
│ - ./scripts/deploy_nas.sh       │ ──► Pull & Up in 03_apps
│ - SSH-Verbindung zum NAS        │ ──► Healthcheck auf Port 9015
│ - 1-Befehl-Rollout von innen    │ ──► Status & Versions-Report
└─────────────────────────────────┘
```

---

### 2.1 Stufe 1: Release-Workflow auf GitHub Actions (`.github/workflows/release.yml`)

Der Workflow wird vollautomatisch getriggert, sobald ein Git-Tag gepusht wird, oder kann manuell via `workflow_dispatch` in GitHub ausgelöst werden:

```bash
# 1. Lokalen Stand taggen (SemVer)
git tag v0.2.0

# 2. Tag auf GitHub pushen
git push origin v0.2.0
```

**Was der GitHub Actions Workflow ausführt:**
1. **Multi-Stage Build (`linux/amd64`):**
   * Baut das produktionsreife `Dockerfile` für die Zielarchitektur der Synology DS218+ (x86_64 / amd64).
   * Injiziert Build-Args:
     * `APP_VERSION`: Bereinigte Versionsnummer (z. B. `0.2.0`).
     * `BUILD_COMMIT`: Git Commit SHA (`${{ github.sha }}`) für Traceability.
2. **Registry Push:**
   * Pusht das Image auf die **GitHub Container Registry (ghcr.io)**:
     * `ghcr.io/mohadipe/data-recorder:<version>` und `latest`
     * `ghcr.io/mohadipe/data-recording:<version>` und `latest`
   * *Optional:* Bei hinterlegten Secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`) wird zusätzlich zu Docker Hub (`mohadipe/data-recorder`) gepusht.
3. **Automatisches GitHub Release:**
   * Erstellt ein GitHub Release mit automatischer Changelog-/Release-Notes-Generierung.

---

### 2.2 Stufe 2: 1-Befehl NAS-Rollout (`./scripts/deploy_nas.sh`)

Da das NAS sicher im internen Heimnetzwerk steht, wird das neue Release über das Idempotente Deployment-Skript von deinem Rechner (oder dem Server Gibbs) angestoßen:

```bash
# Standard-Aufruf (nutzt Host 'nas' aus ~/.ssh/config)
./scripts/deploy_nas.sh

# Simulation / Trockenlauf ohne Änderungen auf dem NAS:
./scripts/deploy_nas.sh --dry-run

# Mit expliziter IP-Adresse oder alternativen Parametern:
NAS_HOST=192.168.2.125 ./scripts/deploy_nas.sh
```

**Was das Skript `deploy_nas.sh` automatisch durchführt:**
1. **SSH-Verbindung:** Verbindet sich per SSH auf das NAS (`ssh nas`).
2. **Image Pull:** Wechselt in `/volume1/docker/nas-infra/03_apps` und zieht das neueste Image via `docker compose pull data-recording`.
3. **Zero-Downtime Neustart:** Aktualisiert den Service ohne Neustart abhängiger Container via `docker compose up -d --no-deps data-recording`.
4. **Automatischer Healthcheck:** Führt eine Retry-Schleife gegen `http://localhost:9015/health` durch (bis zu 15 Versuche).
5. **Erfolgs-Report:** Gibt die verifizierte Anwendungsversion und den aktuellen Docker-Status im Terminal aus.

---

### 2.3 Manueller Fallback (Ad-hoc)

Falls das Skript nicht zur Hand ist, können die Schritte auch manuell via SSH ausgeführt werden:

```bash
ssh nas
cd /volume1/docker/nas-infra/03_apps
docker compose pull data-recording
docker compose up -d --no-deps data-recording
curl -fs http://localhost:9015/health
```

---

## 🗄️ 3. Einmalige Vorbereitung auf dem NAS

### 3.1 Verzeichnisse & Berechtigungen anlegen
Da der Container aus Sicherheitsgründen als Non-Root-User `appuser` (UID 1000) läuft, müssen die persistenten Verzeichnisse auf dem NAS existieren und für UID 1000 beschreibbar sein:

```bash
ssh nas
sudo mkdir -p /volume1/docker/data-recording/logs
sudo mkdir -p /volume1/docker/data-recording/uploads
sudo mkdir -p /volume1/docker/data-recording/failed_uploads

# Berechtigungen auf UID 1000 setzen
sudo chown -R 1000:1000 /volume1/docker/data-recording
```

### 3.2 DDL-Migrationen in MySQL ausführen
Öffne **phpMyAdmin** auf dem NAS ([http://192.168.2.125:48080](http://192.168.2.125:48080)) als `root` oder nutze die MySQL-CLI:

1. **Skript 1 ausführen:** [`database/migrations/01_init_new_tables.sql`](../database/migrations/01_init_new_tables.sql)  
   *(Erstellt `waermepumpe_stundenwert`, `heizoel_preis`, `wkn_ertrag_datum` und erweitert `etf`).*
2. **Skript 2 ausführen:** [`database/migrations/02_hibiscus_import_log.sql`](../database/migrations/02_hibiscus_import_log.sql)  
   *(Erstellt die Tracking-Tabelle für idempotente Hibiscus-Umsatzimporte).*

### 3.3 Wertpapier-Stammdaten initialisieren (XETRA-Ticker & ISINs)
Führe im Schema `wertpapiere` folgendes SQL-Update aus, damit die automatische Yahoo-Finance-Kursabfrage und das Hibiscus-Matching sofort greifen:

> ⚠️ **Wichtig:** Yahoo Finance unterstützt kein Börsenkürzel `.TG`. Es müssen die offiziellen XETRA-Kürzel mit **`.DE`** eingetragen werden!

```sql
USE wertpapiere;

-- Stammdaten mit offiziellen XETRA-Tickern (.DE) und ISINs befüllen
UPDATE etf SET isin = 'IE00B4L5Y983', ticker_yahoo = 'EUNL.DE', name = 'iShares Core MSCI World', aktiv = TRUE WHERE wkn = 'A1T8FV';
UPDATE etf SET isin = 'LU0274208692', ticker_yahoo = 'XMMA.DE', name = 'Xtrackers MSCI Emerging Markets', aktiv = TRUE WHERE wkn = 'A1XB5U';
UPDATE etf SET isin = 'LU0378438732', ticker_yahoo = 'DAX.DE', name = 'Amundi Core DAX', aktiv = TRUE WHERE wkn = 'LYX0CA';
UPDATE etf SET isin = 'IE00B3VVMM66', ticker_yahoo = 'VFEM.DE', name = 'Vanguard FTSE Emerging Markets', aktiv = TRUE WHERE wkn = 'A1XJ53';
UPDATE etf SET isin = 'IE00B8GKDB10', ticker_yahoo = 'VGWD.DE', name = 'Vanguard FTSE All-World High Div', aktiv = TRUE WHERE wkn = 'A1JT1B';

-- Reine Krypto-Positionen vom automatischen Börsenkurs-Polling ausschließen
UPDATE etf SET aktiv = FALSE WHERE wkn = 'Crypto Ether';
```

---

## 🚢 4. Deployment via `deploy_nas.sh` & `nas-infra`

### 4.1 Standard: 1-Befehl-Rollout (Empfohlen)

Führe einfach das Deployment-Skript im Repository-Root aus:

```bash
./scripts/deploy_nas.sh
```

Das Skript verbindet sich via SSH, aktualisiert das Image und den Container in `03_apps`, wartet auf den Healthcheck und gibt die Bestätigung aus.

### 4.2 Alternativ: Vollständiger Stack-Neustart via `nas.sh`

Falls Änderungen an der Stack-Konfiguration in `nas-infra` vorgenommen wurden:

```bash
# 1. Auf das NAS verbinden
ssh nas

# 2. In das nas-infra Verzeichnis wechseln & neuesten Stand ziehen
cd /volume1/docker/nas-infra
git pull

# 3. Stack 03 (Apps) aktualisieren und neu starten
./nas.sh up apps
```

Der Container `Data-Recording` wird automatisch gestartet, bindet sich an `nas_lan` und ist unter Port **`9015`** erreichbar.

---

## ✅ 5. End-to-End Verifikation & Smoke Tests

Nach dem Start auf dem NAS können alle Funktionen direkt per HTTP verifiziert werden:

### 1. Health-Check
```bash
curl -i http://192.168.2.125:9015/health
# Antwort: {"status":"ok","version":"0.1.0","environment":"production"}
```

### 2. Mobile Web-UI (Zählerablesung)
* Im Browser oder Smartphone aufrufen: **[http://192.168.2.125:9015/wizard](http://192.168.2.125:9015/wizard)**
* Prüfen:
  * Werden die aktiven Zähler (Strom, Wasser, Wärme) angezeigt?
  * Kann ein Foto hochgeladen werden?
  * Wird das EXIF-Datum automatisch eingetragen?

### 3. Manueller eBUS-Test (Wärmepumpe)
```bash
curl -X POST http://192.168.2.125:9015/api/ebus/poll-now
# Antwort: {"status":"ok","message":"eBUS-Daten erfolgreich abgefragt und gespeichert.","data":{...}}
```

### 4. Manueller Heizölpreis-Test (PLZ 90579)
```bash
curl -X POST http://192.168.2.125:9015/api/oil-price/poll-now
# Antwort: {"status":"ok","message":"Heizölpreis erfolgreich abgefragt und gespeichert.","data":{"plz":"90579","preis_pro_liter":...}}
```

### 5. Manueller Börsenkurs-Test (Yahoo Finance)
```bash
curl -X POST http://192.168.2.125:9015/api/finance/update-prices
# Antwort: {"status":"ok","message":"X Kurs(e) erfolgreich aktualisiert.","updated_count":X,...}
```

### 6. Manueller Hibiscus-Scan
```bash
curl -X POST http://192.168.2.125:9015/api/finance/scan-hibiscus
# Antwort: {"status":"ok","scanned_count":...,"imported_count":...}
```

---

## 📊 6. Logs & Monitoring

* **Live-Logs des Containers:**
  ```bash
  docker logs -f Data-Recording
  ```
* **Log-Dateien auf dem Host:**
  ```bash
  tail -f /volume1/docker/data-recording/logs/data-recorder.log
  ```
* **Monitoring & Dashboard:**
  * Durch Stack 05 (`05_monitoring`) sammelt Promtail die Docker-Logs automatisch ein.
  * In Grafana ([http://192.168.2.125:3001](http://192.168.2.125:3001)) unter *Explore* / Loki mit `{container_name="Data-Recording"}` einsehbar.

---

## 🤖 7. Optional: Vollautomatisches CD via Self-Hosted GitHub Actions Runner

Wer das Deployment nach einem Tag-Push vollautomatisch (Continuous Deployment) ohne manuelle Ausführung von `./scripts/deploy_nas.sh` durchführen möchte, kann einen **Self-Hosted Runner** im internen Heimnetzwerk anbinden (z. B. auf dem Server `gibbs`).

### Vorteile
* Das NAS muss **keine** öffentlichen Ports im Router öffnen.
* Der Runner verbindet sich outbound (HTTPS) zu GitHub, empfängt den Deployment-Trigger und führt das Rollout von innen heraus aus.

### Einrichtung auf dem Server (z. B. Gibbs)

1. **Runner in GitHub registrieren:**
   * Unter GitHub: Repository Settings ➔ Actions ➔ Runners ➔ *New self-hosted runner*.
   * Download & Installation des Runners auf dem internen Host.
   * Labels vergeben: z. B. `self-hosted`, `linux`, `heimnetz`.

2. **CD-Workflow ergänzen (`.github/workflows/deploy.yml`):**
   ```yaml
   name: Continuous Deployment (NAS)

   on:
     workflow_run:
       workflows: ["Release & Publish Container Image"]
       types: [completed]
       branches: [main]

   jobs:
     deploy:
       if: ${{ github.event.workflow_run.conclusion == 'success' }}
       runs-on: [self-hosted, heimnetz]
       steps:
         - name: Checkout Code
           uses: actions/checkout@v4

         - name: Rollout auf Synology NAS
           run: |
             chmod +x ./scripts/deploy_nas.sh
             ./scripts/deploy_nas.sh
   ```
