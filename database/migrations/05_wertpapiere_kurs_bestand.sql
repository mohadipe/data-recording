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
