-- ==============================================================================
-- Migration: 04_superset_views.sql
-- Ziel: Erstellung aller optimierten SQL-Views für Apache Superset in MySQL 8
--       (Wärmepumpen-COP, Heizkostenvergleich Öl vs. WP, Portfolio Performance)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Schema: verbrauch
-- ------------------------------------------------------------------------------
USE verbrauch;

-- 1.1 Monats-COP & Temperatur Wärmepumpe
CREATE OR REPLACE VIEW verbrauch.view_waermepumpe_monats_cop AS
WITH monat_base AS (
    SELECT 
        DATE(DATE_FORMAT(zeitstempel, '%Y-%m-01')) AS monat,
        YEAR(zeitstempel) AS jahr,
        MONTH(zeitstempel) AS monat_nr,
        DATE_FORMAT(zeitstempel, '%Y-%m') AS monat_name,
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
        DATE(DATE_FORMAT(zeitstempel, '%Y-%m-01')),
        YEAR(zeitstempel),
        MONTH(zeitstempel),
        DATE_FORMAT(zeitstempel, '%Y-%m')
)
SELECT 
    monat,
    jahr,
    monat_nr,
    monat_name,
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
FROM monat_base;

-- 1.2 Tages-COP & Temperatur Wärmepumpe (Feinere Zeitreihen)
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

-- 1.3 Heizkostenvergleich Öl vs. Wärmepumpe
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

-- ------------------------------------------------------------------------------
-- 2. Schema: wertpapiere
-- ------------------------------------------------------------------------------
USE wertpapiere;

-- 2.1 Zeitreihen Performance je Wertpapier
CREATE OR REPLACE VIEW wertpapiere.view_portfolio_performance AS
SELECT 
    w.id AS wert_id,
    w.datum,
    e.id AS wkn_id,
    e.wkn,
    e.isin,
    e.name,
    e.ticker_yahoo,
    e.typ,
    e.aktiv,
    w.wert AS depotwert,
    COALESCE((
        SELECT SUM(i.invest) 
        FROM wertpapiere.wkn_invest_datum i 
        WHERE i.wkn_id = w.wkn_id AND i.datum <= w.datum
    ), 0.00) AS kumuliertes_invest,
    COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = w.wkn_id AND er.datum <= w.datum
    ), 0.00) AS kumulierter_ertrag,
    ROUND(w.wert + COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = w.wkn_id AND er.datum <= w.datum
    ), 0.00), 2) AS gesamtwert_inkl_ertrag,
    ROUND((w.wert + COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = w.wkn_id AND er.datum <= w.datum
    ), 0.00)) - COALESCE((
        SELECT SUM(i.invest) 
        FROM wertpapiere.wkn_invest_datum i 
        WHERE i.wkn_id = w.wkn_id AND i.datum <= w.datum
    ), 0.00), 2) AS gewinn_verlust_euro,
    ROUND(
        CASE 
            WHEN COALESCE((SELECT SUM(i.invest) FROM wertpapiere.wkn_invest_datum i WHERE i.wkn_id = w.wkn_id AND i.datum <= w.datum), 0.00) > 0 
            THEN (((w.wert + COALESCE((SELECT SUM(er.betrag) FROM wertpapiere.wkn_ertrag_datum er WHERE er.wkn_id = w.wkn_id AND er.datum <= w.datum), 0.00)) - 
                  (SELECT SUM(i.invest) FROM wertpapiere.wkn_invest_datum i WHERE i.wkn_id = w.wkn_id AND i.datum <= w.datum)) / 
                  (SELECT SUM(i.invest) FROM wertpapiere.wkn_invest_datum i WHERE i.wkn_id = w.wkn_id AND i.datum <= w.datum)) * 100
            ELSE 0 
        END, 2
    ) AS rendite_prozent
FROM wertpapiere.wkn_wert_datum w
JOIN wertpapiere.etf e ON e.id = w.wkn_id;

-- 2.2 Aktuelle Gesamtübersicht je Wertpapier
CREATE OR REPLACE VIEW wertpapiere.view_portfolio_uebersicht_aktuell AS
WITH latest_wert AS (
    SELECT 
        w.wkn_id,
        w.datum AS letzter_stichtag,
        w.wert AS aktueller_wert
    FROM wertpapiere.wkn_wert_datum w
    INNER JOIN (
        SELECT wkn_id, MAX(datum) AS max_datum 
        FROM wertpapiere.wkn_wert_datum 
        GROUP BY wkn_id
    ) mw ON w.wkn_id = mw.wkn_id AND w.datum = mw.max_datum
)
SELECT 
    e.id AS wkn_id,
    e.wkn,
    e.isin,
    e.name,
    e.ticker_yahoo,
    e.typ,
    e.aktiv,
    lw.letzter_stichtag,
    COALESCE(lw.aktueller_wert, 0.00) AS aktueller_wert,
    COALESCE((
        SELECT SUM(i.invest) 
        FROM wertpapiere.wkn_invest_datum i 
        WHERE i.wkn_id = e.id
    ), 0.00) AS invest_gesamt,
    COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = e.id
    ), 0.00) AS ertrag_gesamt,
    ROUND(COALESCE(lw.aktueller_wert, 0.00) + COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = e.id
    ), 0.00), 2) AS gesamtwert_inkl_ertrag,
    ROUND((COALESCE(lw.aktueller_wert, 0.00) + COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = e.id
    ), 0.00)) - COALESCE((
        SELECT SUM(i.invest) 
        FROM wertpapiere.wkn_invest_datum i 
        WHERE i.wkn_id = e.id
    ), 0.00), 2) AS gewinn_verlust_euro,
    ROUND(
        CASE 
            WHEN COALESCE((SELECT SUM(i.invest) FROM wertpapiere.wkn_invest_datum i WHERE i.wkn_id = e.id), 0.00) > 0 
            THEN (((COALESCE(lw.aktueller_wert, 0.00) + COALESCE((SELECT SUM(er.betrag) FROM wertpapiere.wkn_ertrag_datum er WHERE er.wkn_id = e.id), 0.00)) - 
                  (SELECT SUM(i.invest) FROM wertpapiere.wkn_invest_datum i WHERE i.wkn_id = e.id)) / 
                  (SELECT SUM(i.invest) FROM wertpapiere.wkn_invest_datum i WHERE i.wkn_id = e.id)) * 100
            ELSE 0 
        END, 2
    ) AS rendite_gesamt_prozent
FROM wertpapiere.etf e
LEFT JOIN latest_wert lw ON lw.wkn_id = e.id;
