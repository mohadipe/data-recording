-- Migration: 02_hibiscus_import_log.sql
-- Ziel: Tracking-Tabelle fuer idempotente Hibiscus-Umsatz-Erkennung anlegen.

USE wertpapiere;

CREATE TABLE IF NOT EXISTS hibiscus_import_log (
    id INT NOT NULL AUTO_INCREMENT,
    hibiscus_umsatz_id INT NOT NULL,
    wkn_id INT NULL,
    typ VARCHAR(50) NOT NULL,
    datum DATE NOT NULL,
    betrag DECIMAL(10, 2) NOT NULL,
    verwendungszweck VARCHAR(1000) NULL,
    imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_hibiscus_import_umsatz_id (hibiscus_umsatz_id),
    KEY idx_hibiscus_import_wkn_id (wkn_id),
    KEY idx_hibiscus_import_datum (datum),
    CONSTRAINT fk_hibiscus_import_etf FOREIGN KEY (wkn_id) REFERENCES etf (id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
