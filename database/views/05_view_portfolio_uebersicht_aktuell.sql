-- ==============================================================================
-- View 5: view_portfolio_uebersicht_aktuell
-- Schema: wertpapiere
-- Zweck: Aktuelle Stichtagsübersicht über alle Wertpapiere für KPI-Cards und Tabellen.
--        Ermittelt für jedes Wertpapier:
--        - Letzten Schlusskurs aus wkn_kurs_datum (inkl. Notierungsdatum)
--        - Letzten Anteilsbestand aus wkn_bestand_datum
--        - Aktuellen Gesamtwert (Anteile * Kurs), mit Fallback auf historischen
--          Snapshot aus wkn_wert_datum falls Anteile oder Kurs fehlen
--        - Gesamt-Investitionen, Gesamt-Erträge sowie absolute und prozentuale Rendite.
-- ==============================================================================

USE wertpapiere;

CREATE OR REPLACE VIEW wertpapiere.view_portfolio_uebersicht_aktuell AS
WITH latest_kurs AS (
    SELECT 
        k.wkn_id,
        k.datum,
        k.kurs
    FROM wertpapiere.wkn_kurs_datum k
    INNER JOIN (
        SELECT wkn_id, MAX(datum) AS max_datum
        FROM wertpapiere.wkn_kurs_datum
        GROUP BY wkn_id
    ) mk ON k.wkn_id = mk.wkn_id AND k.datum = mk.max_datum
),
latest_bestand AS (
    SELECT 
        b.wkn_id,
        b.datum,
        b.anteile
    FROM wertpapiere.wkn_bestand_datum b
    INNER JOIN (
        SELECT wkn_id, MAX(datum) AS max_datum
        FROM wertpapiere.wkn_bestand_datum
        GROUP BY wkn_id
    ) mb ON b.wkn_id = mb.wkn_id AND b.datum = mb.max_datum
),
latest_wert AS (
    SELECT 
        w.wkn_id,
        w.datum AS letzter_stichtag,
        w.wert AS aktueller_wert
    FROM wertpapiere.wkn_wert_datum w
    INNER JOIN (
        SELECT wkn_id, MAX(datum) AS max_datum
        FROM wertpapiere.wkn_wert_datum
        WHERE datum <= '2026-07-16'
        GROUP BY wkn_id
    ) mw ON w.wkn_id = mw.wkn_id AND w.datum = mw.max_datum
),
portfolio_base AS (
    SELECT 
        e.id AS wkn_id,
        e.wkn,
        e.isin,
        e.name,
        e.ticker_yahoo,
        e.typ,
        e.aktiv,
        CASE 
            WHEN lb.anteile IS NOT NULL AND lk.kurs IS NOT NULL THEN lk.datum
            ELSE COALESCE(lw.letzter_stichtag, lk.datum, lb.datum)
        END AS letzter_stichtag,
        lk.kurs AS aktueller_kurs,
        lb.anteile AS aktueller_bestand,
        CASE 
            WHEN lb.anteile IS NOT NULL AND lk.kurs IS NOT NULL THEN ROUND(lb.anteile * lk.kurs, 2)
            ELSE COALESCE(lw.aktueller_wert, 0.00)
        END AS aktueller_wert,
        COALESCE((
            SELECT SUM(i.invest) 
            FROM wertpapiere.wkn_invest_datum i 
            WHERE i.wkn_id = e.id
        ), 0.00) AS invest_gesamt,
        COALESCE((
            SELECT SUM(er.betrag) 
            FROM wertpapiere.wkn_ertrag_datum er 
            WHERE er.wkn_id = e.id
        ), 0.00) AS ertrag_gesamt
    FROM wertpapiere.etf e
    LEFT JOIN latest_kurs lk ON lk.wkn_id = e.id
    LEFT JOIN latest_bestand lb ON lb.wkn_id = e.id
    LEFT JOIN latest_wert lw ON lw.wkn_id = e.id
)
SELECT 
    wkn_id,
    wkn,
    isin,
    name,
    ticker_yahoo,
    typ,
    aktiv,
    letzter_stichtag,
    aktueller_kurs,
    aktueller_bestand,
    aktueller_wert,
    invest_gesamt,
    ertrag_gesamt,
    ROUND(aktueller_wert + ertrag_gesamt, 2) AS gesamtwert_inkl_ertrag,
    ROUND((aktueller_wert + ertrag_gesamt) - invest_gesamt, 2) AS gewinn_verlust_euro,
    ROUND(
        CASE 
            WHEN invest_gesamt > 0 
            THEN (((aktueller_wert + ertrag_gesamt) - invest_gesamt) / invest_gesamt) * 100
            ELSE 0 
        END, 2
    ) AS rendite_gesamt_prozent
FROM portfolio_base;
