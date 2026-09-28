-- ==============================================================================
-- View 3: view_heizkosten_vergleich_oel_vs_wp
-- Schema: verbrauch
-- Zweck: Berechnet monatlich den wirtschaftlichen Vergleich zwischen Wärmepumpe und Öl:
--        • Tatsächliche Wärmepumpen-Stromkosten (Stromverbrauch * hinterlegter Stromtarif)
--        • Hypothetische Heizölkosten: (Erzeugte Wärme / (10 kWh/L * 0.88)) * regionaler Heizölpreis
--        • Netto-Ersparnis in Euro und Prozent
-- ==============================================================================

USE verbrauch;

CREATE OR REPLACE VIEW verbrauch.view_heizkosten_vergleich_oel_vs_wp AS
WITH wp_monat AS (
    SELECT 
        DATE(DATE_FORMAT(zeitstempel, '%Y-%m-01')) AS monat,
        YEAR(zeitstempel) AS jahr,
        MONTH(zeitstempel) AS monat_nr,
        DATE_FORMAT(zeitstempel, '%Y-%m') AS monat_name,
        ROUND(COALESCE(
            NULLIF(MAX(ertrag_gesamt_kwh) - MIN(ertrag_gesamt_kwh), 0),
            NULLIF(MAX(ertrag_heizen_kwh) - MIN(ertrag_heizen_kwh), 0) + NULLIF(MAX(ertrag_warmwasser_kwh) - MIN(ertrag_warmwasser_kwh), 0),
            SUM(ertrag_gesamt_kwh),
            0
        ), 2) AS erzeugte_waerme_kwh,
        ROUND(COALESCE(
            NULLIF(MAX(strom_gesamt_kwh) - MIN(strom_gesamt_kwh), 0),
            NULLIF(MAX(strom_heizen_kwh) - MIN(strom_heizen_kwh), 0) + NULLIF(MAX(strom_warmwasser_kwh) - MIN(strom_warmwasser_kwh), 0),
            SUM(strom_gesamt_kwh),
            0
        ), 2) AS strom_wp_kwh
    FROM verbrauch.waermepumpe_stundenwert
    GROUP BY 
        DATE(DATE_FORMAT(zeitstempel, '%Y-%m-01')),
        YEAR(zeitstempel),
        MONTH(zeitstempel),
        DATE_FORMAT(zeitstempel, '%Y-%m')
),
berechnung_preise AS (
    SELECT 
        w.monat,
        w.jahr,
        w.monat_nr,
        w.monat_name,
        w.erzeugte_waerme_kwh,
        w.strom_wp_kwh,
        -- Stromtarif in Euro/kWh (Fallback auf 0.30 €/kWh)
        COALESCE(
            (SELECT k.preis / 100.0 FROM verbrauch.kosten k 
             WHERE k.ressource = 'Strom' AND k.von <= w.monat AND k.bis >= w.monat 
             ORDER BY k.von DESC LIMIT 1),
            (SELECT k.preis / 100.0 FROM verbrauch.kosten k 
             WHERE k.ressource = 'Strom' 
             ORDER BY k.von DESC LIMIT 1),
            0.3000
        ) AS strompreis_pro_kwh,
        -- Regionaler Heizölpreis in Euro/Liter (Fallback auf 1.05 €/L)
        COALESCE(
            (SELECT AVG(h.preis_pro_liter) FROM verbrauch.heizoel_preis h 
             WHERE h.datum >= w.monat AND h.datum <= LAST_DAY(w.monat)),
            (SELECT h.preis_pro_liter FROM verbrauch.heizoel_preis h 
             ORDER BY h.datum DESC LIMIT 1),
            (SELECT (k.preis / 100.0) FROM verbrauch.kosten k 
             WHERE (k.ressource = 'Öl' OR k.ressource LIKE '%l%') 
             ORDER BY k.von DESC LIMIT 1),
            1.0500
        ) AS heizoelpreis_pro_liter,
        -- Benötigte Liter Heizöl: (Erzeugte Wärme / (10 kWh/L * 0.88))
        ROUND(w.erzeugte_waerme_kwh / 8.8, 2) AS heizoel_liter_aequivalent
    FROM wp_monat w
)
SELECT 
    monat,
    jahr,
    monat_nr,
    monat_name,
    erzeugte_waerme_kwh,
    strom_wp_kwh,
    strompreis_pro_kwh,
    heizoelpreis_pro_liter,
    heizoel_liter_aequivalent,
    ROUND(strom_wp_kwh * strompreis_pro_kwh, 2) AS stromkosten_wp_euro,
    ROUND(heizoel_liter_aequivalent * heizoelpreis_pro_liter, 2) AS heizoelkosten_hypothetisch_euro,
    ROUND((heizoel_liter_aequivalent * heizoelpreis_pro_liter) - (strom_wp_kwh * strompreis_pro_kwh), 2) AS netto_ersparnis_euro,
    ROUND(
        CASE 
            WHEN (heizoel_liter_aequivalent * heizoelpreis_pro_liter) > 0 
            THEN (((heizoel_liter_aequivalent * heizoelpreis_pro_liter) - (strom_wp_kwh * strompreis_pro_kwh)) / (heizoel_liter_aequivalent * heizoelpreis_pro_liter)) * 100
            ELSE 0 
        END, 1
    ) AS ersparnis_prozent
FROM berechnung_preise;
