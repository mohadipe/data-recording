-- ==============================================================================
-- View 2 (Bonus Tagesaggregation): view_waermepumpe_tages_cop
-- Schema: verbrauch
-- Zweck: Aggregiert die stündlichen eBUS-Messwerte der Wärmepumpe auf Tagesbasis.
--        Ermöglicht detaillierte Zeitreihen in Superset für COP und Außentemperatur.
-- ==============================================================================

USE verbrauch;

CREATE OR REPLACE VIEW verbrauch.view_waermepumpe_tages_cop AS
WITH tag_base AS (
    SELECT 
        DATE(zeitstempel) AS datum,
        YEAR(zeitstempel) AS jahr,
        MONTH(zeitstempel) AS monat_nr,
        DAY(zeitstempel) AS tag_nr,
        COUNT(*) AS anzahl_messungen,
        ROUND(AVG(aussentemperatur), 2) AS aussentemperatur_avg,
        ROUND(MIN(aussentemperatur), 2) AS aussentemperatur_min,
        ROUND(MAX(aussentemperatur), 2) AS aussentemperatur_max,
        ROUND(AVG(vorlauf_temp), 2) AS vorlauf_temp_avg,
        ROUND(AVG(ruecklauf_temp), 2) AS ruecklauf_temp_avg,
        ROUND(COALESCE(
            NULLIF(MAX(ertrag_heizen_kwh) - MIN(ertrag_heizen_kwh), 0),
            SUM(ertrag_heizen_kwh),
            0
        ), 2) AS waerme_heizen_kwh,
        ROUND(COALESCE(
            NULLIF(MAX(strom_heizen_kwh) - MIN(strom_heizen_kwh), 0),
            SUM(strom_heizen_kwh),
            0
        ), 2) AS strom_heizen_kwh,
        ROUND(COALESCE(
            NULLIF(MAX(ertrag_warmwasser_kwh) - MIN(ertrag_warmwasser_kwh), 0),
            SUM(ertrag_warmwasser_kwh),
            0
        ), 2) AS waerme_warmwasser_kwh,
        ROUND(COALESCE(
            NULLIF(MAX(strom_warmwasser_kwh) - MIN(strom_warmwasser_kwh), 0),
            SUM(strom_warmwasser_kwh),
            0
        ), 2) AS strom_warmwasser_kwh,
        ROUND(COALESCE(
            NULLIF(MAX(ertrag_gesamt_kwh) - MIN(ertrag_gesamt_kwh), 0),
            NULLIF(MAX(ertrag_heizen_kwh) - MIN(ertrag_heizen_kwh), 0) + NULLIF(MAX(ertrag_warmwasser_kwh) - MIN(ertrag_warmwasser_kwh), 0),
            SUM(ertrag_gesamt_kwh),
            0
        ), 2) AS waerme_gesamt_kwh,
        ROUND(COALESCE(
            NULLIF(MAX(strom_gesamt_kwh) - MIN(strom_gesamt_kwh), 0),
            NULLIF(MAX(strom_heizen_kwh) - MIN(strom_heizen_kwh), 0) + NULLIF(MAX(strom_warmwasser_kwh) - MIN(strom_warmwasser_kwh), 0),
            SUM(strom_gesamt_kwh),
            0
        ), 2) AS strom_gesamt_kwh,
        ROUND(AVG(cop_aktuell), 2) AS cop_aktuell_avg
    FROM verbrauch.waermepumpe_stundenwert
    GROUP BY 
        DATE(zeitstempel),
        YEAR(zeitstempel),
        MONTH(zeitstempel),
        DAY(zeitstempel)
)
SELECT 
    datum,
    jahr,
    monat_nr,
    tag_nr,
    anzahl_messungen,
    aussentemperatur_avg,
    aussentemperatur_min,
    aussentemperatur_max,
    vorlauf_temp_avg,
    ruecklauf_temp_avg,
    waerme_heizen_kwh,
    strom_heizen_kwh,
    waerme_warmwasser_kwh,
    strom_warmwasser_kwh,
    waerme_gesamt_kwh,
    strom_gesamt_kwh,
    ROUND(waerme_heizen_kwh / NULLIF(strom_heizen_kwh, 0), 2) AS cop_heizen,
    ROUND(waerme_warmwasser_kwh / NULLIF(strom_warmwasser_kwh, 0), 2) AS cop_warmwasser,
    COALESCE(ROUND(waerme_gesamt_kwh / NULLIF(strom_gesamt_kwh, 0), 2), cop_aktuell_avg) AS cop_gesamt,
    cop_aktuell_avg
FROM tag_base;
