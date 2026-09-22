-- Migration: 01_init_new_tables.sql
-- Ziel: Neue Tabellen (waermepumpe_stundenwert, heizoel_preis, wkn_ertrag_datum) anlegen
--       sowie Spaltenerweiterungen fuer etf (isin, name, ticker_yahoo, typ, aktiv) nachruesten.

-- ========================================================
-- 1. Schema: verbrauch
-- ========================================================
CREATE DATABASE IF NOT EXISTS verbrauch;
USE verbrauch;

-- Neue Tabelle fuer stuendliche Waermepumpen-Messwerte & Arbeitszahlen (COP)
CREATE TABLE IF NOT EXISTS waermepumpe_stundenwert (
    id INT NOT NULL AUTO_INCREMENT,
    zeitstempel DATETIME NOT NULL,
    aussentemperatur DECIMAL(5, 2) NULL,
    vorlauf_temp DECIMAL(5, 2) NULL,
    ruecklauf_temp DECIMAL(5, 2) NULL,
    ertrag_gesamt_kwh DECIMAL(12, 3) NULL,
    strom_gesamt_kwh DECIMAL(12, 3) NULL,
    ertrag_heizen_kwh DECIMAL(12, 3) NULL,
    strom_heizen_kwh DECIMAL(12, 3) NULL,
    ertrag_warmwasser_kwh DECIMAL(12, 3) NULL,
    strom_warmwasser_kwh DECIMAL(12, 3) NULL,
    cop_aktuell DECIMAL(5, 2) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_wp_zeitstempel (zeitstempel)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Neue Tabelle fuer regionale Heizoelpreise (Vergleichskosten-Berechnung)
CREATE TABLE IF NOT EXISTS heizoel_preis (
    id INT NOT NULL AUTO_INCREMENT,
    datum DATE NOT NULL,
    plz VARCHAR(10) NOT NULL,
    menge_liter INT NOT NULL,
    preis_pro_liter DECIMAL(10, 4) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_heizoel_datum (datum),
    KEY idx_heizoel_plz (plz),
    UNIQUE KEY uq_heizoel_datum_plz_menge (datum, plz, menge_liter)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ========================================================
-- 2. Schema: wertpapiere
-- ========================================================
CREATE DATABASE IF NOT EXISTS wertpapiere;
USE wertpapiere;

-- Spaltenerweiterungen fuer bestehende Tabelle `etf`
ALTER TABLE etf ADD COLUMN IF NOT EXISTS isin VARCHAR(12) NULL;
ALTER TABLE etf ADD COLUMN IF NOT EXISTS name VARCHAR(255) NULL;
ALTER TABLE etf ADD COLUMN IF NOT EXISTS ticker_yahoo VARCHAR(50) NULL;
ALTER TABLE etf ADD COLUMN IF NOT EXISTS typ VARCHAR(50) NOT NULL DEFAULT 'ETF';
ALTER TABLE etf ADD COLUMN IF NOT EXISTS aktiv BOOLEAN NOT NULL DEFAULT TRUE;

-- Neue Tabelle fuer Dividenden, Ertraege und Ausschuettungen
CREATE TABLE IF NOT EXISTS wkn_ertrag_datum (
    id INT NOT NULL AUTO_INCREMENT,
    wkn_id INT NOT NULL,
    datum DATE NOT NULL,
    betrag DECIMAL(10, 2) NOT NULL,
    typ VARCHAR(50) NOT NULL DEFAULT 'DIVIDENDE',
    PRIMARY KEY (id),
    KEY idx_wkn_ertrag_wkn_id (wkn_id),
    KEY idx_wkn_ertrag_datum (datum),
    UNIQUE KEY uq_wkn_ertrag_wkn_datum_typ (wkn_id, datum, typ),
    CONSTRAINT fk_wkn_ertrag_etf FOREIGN KEY (wkn_id) REFERENCES etf (id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
