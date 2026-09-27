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

## 📦 2. Release: Docker-Image bauen & bereitstellen

Es gibt zwei Wege, das Release-Image auf das NAS zu bringen:

### Option A: Lokal bauen und auf Docker Hub pushen (Empfohlen)

Auf deinem Entwicklungsrechner im Verzeichnis `data-recording`:

```bash
cd /home/mohadipe/IdeaProjects/data-recording

# 1. Multi-Stage Docker-Image bauen
docker build -t mohadipe/data-recorder:latest -t mohadipe/data-recorder:2.0.0 .

# 2. Image auf Docker Hub pushen
docker push mohadipe/data-recorder:latest
docker push mohadipe/data-recorder:2.0.0
```

### Option B: Direkt auf dem NAS bauen (falls kein Docker Hub Push gewünscht)

```bash
# Auf das NAS verbinden
ssh nas

# In das App-Verzeichnis wechseln oder Repo klonen
cd /volume1/docker
git clone https://github.com/mohadipe/data-recording.git data-recording-src
cd data-recording-src

# Image direkt auf der Synology bauen
docker build -t mohadipe/data-recorder:latest .
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

## 🚢 4. Deployment via `nas-infra`

In `nas-infra` ist Stack 03 (`03_apps/docker-compose.yaml`) bereits für `Data-Recording 2.0` konfiguriert:

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
