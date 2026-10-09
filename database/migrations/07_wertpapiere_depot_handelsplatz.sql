-- ==============================================================================
-- Migration 07: Depot- und Handelsplatz-Unterstützung für Wertpapiere
-- Schema: wertpapiere
-- Zweck: Ergänzt die Tabelle 'etf' um die Spalten 'depot' und 'handelsplatz',
--        um Mehrfachdepots (Cortal Consors / Consorsbank vs. Scalable Capital)
--        und spezifische Handelsplätze (Tradegate, gettex, Xetra, Stuttgart)
--        zu verwalten und das Kursabfrage-Routing gezielt zu steuern.
-- ==============================================================================

USE wertpapiere;

-- 1. Spalten 'depot' und 'handelsplatz' zur Tabelle 'etf' hinzufügen
ALTER TABLE wertpapiere.etf
    ADD COLUMN depot VARCHAR(50) NOT NULL DEFAULT 'cortal_consors' AFTER typ,
    ADD COLUMN handelsplatz VARCHAR(50) NOT NULL DEFAULT 'tradegate' AFTER depot,
    ADD INDEX idx_etf_depot (depot);

-- 2. Bestehende Datensätze initialisieren (idempotent)
UPDATE wertpapiere.etf
SET depot = 'cortal_consors'
WHERE depot IS NULL OR depot = '';

UPDATE wertpapiere.etf
SET handelsplatz = 'tradegate'
WHERE handelsplatz IS NULL OR handelsplatz = '';
