-- Migration: 03_zaehler_and_messwerte_updates.sql
-- Ziel: Korrektur der Zaehler-Stammdaten (Stromzaehler 3 & 4 aktivieren, veralteten Zaehler 5 deaktivieren)
--       sowie Unique-Constraint fuer Messwerte mit Einheit (KWH und M3 bei Waermezaehlern am gleichen Datum).

USE verbrauch;

-- 1. Stromzaehler-Laufzeiten korrigieren
-- 1 EMH00 0988 6538 und 1 EMH00 0988 6539 sind die aktiven Zaehler (Ausbau in die Zukunft verlegen)
UPDATE zaehler SET ausbau_dt = '2036-06-25' WHERE id IN (3, 4);

-- Veralteten Zaehler 55215647 als ausgebaut markieren
UPDATE zaehler SET ausbau_dt = '2020-05-31' WHERE id = 5;

-- 2. Eindeutigen Index fuer zaehler_id, datum, einheit ergaenzen (falls noch nicht vorhanden)
SET @exist := (
    SELECT COUNT(*) 
    FROM information_schema.statistics 
    WHERE table_schema = 'verbrauch' 
      AND table_name = 'messwerte' 
      AND index_name = 'uq_zaehler_datum_einheit'
);
SET @sqlstmt := IF(@exist = 0, 'ALTER TABLE messwerte ADD UNIQUE KEY uq_zaehler_datum_einheit (zaehler_id, datum, einheit)', 'SELECT "Index already exists"');
PREPARE stmt FROM @sqlstmt;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
