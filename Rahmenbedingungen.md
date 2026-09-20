# 🏛️ Rahmenbedingungen & Architektur-Entscheidungen (Data-Recording 2.0)

Dieses Dokument hält die fundamentalen organisatorischen und technischen Rahmenbedingungen für das Repository `data-recording` fest.

---

## 1. Hosting- & Infrastruktur-Umgebung

* **Host-System:** **Synology DiskStation NAS (`192.168.2.125`)**.
* **Betriebsmodus:** 24/7 containerisierter Betrieb via **Synology Container Manager (Docker Compose)**.
* **Ressourcenvorgaben:**
  * Das System muss extrem schlank sein (Ziel: **< 150 MB RAM** im Normalbetrieb).
  * Kein schwerer Java/JVM-Stack mehr – Umstieg auf Python 3.12 (FastAPI).
  * Geringe CPU-Last, asynchrone I/O-Verarbeitung.

---

## 2. Datenbank & Vorhandene Systeme (Single Source of Truth)

* **MySQL auf der Synology:**
  * Alle erfassten Daten werden in der bereits laufenden MySQL-Instanz auf dem NAS gespeichert.
  * Bestehende Schemas werden weitergeführt:
    * `verbrauch`: Hauszähler (Strom, Wasser, Wärme), neue Tabelle für Wärmepumpen-Stundenwerte, Tabelle für regionale Heizölpreise.
    * `wertpapiere`: ETF-/Aktien-Stammdaten, historische Kurse (`wkn_wert_datum`), Sparplan-Investitionen (`wkn_invest_datum`), Erträge/Dividenden.
    * `hibiscus`: Wird ausschließlich lesend abgefragt, um Sparpläne und Dividenden automatisch aus Kontoumsätzen zu parsen.
* **Keine parallele Datenbank:**
  * Es wird keine zusätzliche PostgreSQL- oder SQLite-Instanz im Produktivbetrieb hochgezogen, um die Systemkomplexität auf dem NAS minimal zu halten.

---

## 3. Schnittstellen & Ökosystem-Integration

1. **Wärmepumpe (Vaillant aroTHERM plus):**
   * Kein direkter Hardware-Zugriff aus diesem Container.
   * Kommunikation erfolgt über den bereits laufenden `ebusd`-Daemon auf dem NAS (`http://192.168.2.125:58888/data`).
   * Stündliches Polling und Speicherung zur COP-Berechnung.
2. **Dokumenten- und Belegarchivierung (Paperless-ngx):**
   * Zählerstandsfotos werden nicht im Dateisystem fragmentiert, sondern per REST-API direkt in das auf dem NAS laufende **Paperless-ngx** archiviert.
   * Metadaten: Tag `Zaehlerbeleg`, Typ `Zaehlerbeleg`, Erstellungsdatum = EXIF-Aufnahmedatum des Fotos.
3. **Visualisierung (Apache Superset):**
   * Superset läuft bereits auf dem NAS und greift direkt auf die MySQL-Tabellen/Views zu.
   * `data-recording` stellt optimierte SQL-Views bereit, um komplexe Berechnungen (z. B. monatlicher COP, Heizkosten-Ersparnis gegenüber Öl) direkt in der Datenbank vorzubereiten.
4. **Börsenkurse (Tradegate / Yahoo Finance):**
   * Tägliche Abfrage um 22:30 Uhr via Yahoo Finance (`.TG`-Suffix) für alle aktiven Wertpapiere.
   * Keine kostenpflichtigen oder limitierten API-Keys nötig.

---

## 4. Datenschutz & Resilienz

* **Datensouveränität:** Alle privaten Zählerstände, Verbrauchsdaten und Bankumsätze verbleiben zu 100 % im lokalen Heimnetzwerk.
* **Offline-Resilienz:** Fällt das Internet aus, läuft die Zählererfassung und eBUS-Wärmepumpenaufzeichnung lokal ungestört weiter; externe Kurse und Ölpreise werden beim nächsten Wiederverbinden nachgeholt.
