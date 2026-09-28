-- ==============================================================================
-- View 4: view_portfolio_performance
-- Schema: wertpapiere
-- Zweck: Zeitreihen-Performance-Analyse je Wertpapier und Stichtag.
--        Hybrides Modell:
--        1. Historische Snapshots aus wkn_wert_datum (datum <= '2026-07-16')
--        2. Tägliche Schlusskurse aus wkn_kurs_datum kombiniert mit den
--           jeweils gültigen Anteilsbeständen aus wkn_bestand_datum.
--        Berechnet kumulierte Einzahlungen, aktuellen Depotwert, Erträge (Dividenden)
--        sowie Gesamtrendite in Euro und Prozent.
-- ==============================================================================

USE wertpapiere;

CREATE OR REPLACE VIEW wertpapiere.view_portfolio_performance AS
WITH raw_kurs AS (
    SELECT 
        k.id AS source_id,
        k.datum,
        k.wkn_id,
        k.kurs,
        (
            SELECT b.anteile 
            FROM wertpapiere.wkn_bestand_datum b 
            WHERE b.wkn_id = k.wkn_id AND b.datum <= k.datum 
            ORDER BY b.datum DESC, b.id DESC 
            LIMIT 1
        ) AS anteile
    FROM wertpapiere.wkn_kurs_datum k
),
combined_data AS (
    SELECT 
        w.id AS source_id,
        w.datum,
        w.wkn_id,
        CAST(NULL AS DECIMAL(10, 4)) AS kurs,
        CAST(NULL AS DECIMAL(12, 4)) AS anteile,
        w.wert AS depotwert
    FROM wertpapiere.wkn_wert_datum w
    WHERE w.datum <= '2026-07-16'
    UNION ALL
    SELECT 
        rk.source_id,
        rk.datum,
        rk.wkn_id,
        rk.kurs,
        rk.anteile,
        ROUND(COALESCE(rk.anteile, 0.0000) * rk.kurs, 2) AS depotwert
    FROM raw_kurs rk
),
perf_base AS (
    SELECT 
        cd.source_id,
        cd.datum,
        cd.wkn_id,
        e.wkn,
        e.isin,
        e.name,
        e.ticker_yahoo,
        e.typ,
        e.aktiv,
        cd.kurs,
        cd.anteile,
        cd.depotwert,
        COALESCE((
            SELECT SUM(i.invest) 
            FROM wertpapiere.wkn_invest_datum i 
            WHERE i.wkn_id = cd.wkn_id AND i.datum <= cd.datum
        ), 0.00) AS kumuliertes_invest,
        COALESCE((
            SELECT SUM(er.betrag) 
            FROM wertpapiere.wkn_ertrag_datum er 
            WHERE er.wkn_id = cd.wkn_id AND er.datum <= cd.datum
        ), 0.00) AS kumulierter_ertrag
    FROM combined_data cd
    JOIN wertpapiere.etf e ON e.id = cd.wkn_id
)
SELECT 
    source_id,
    datum,
    wkn_id,
    wkn,
    isin,
    name,
    ticker_yahoo,
    typ,
    aktiv,
    kurs,
    anteile,
    depotwert,
    kumuliertes_invest,
    kumulierter_ertrag,
    ROUND(depotwert + kumulierter_ertrag, 2) AS gesamtwert_inkl_ertrag,
    ROUND((depotwert + kumulierter_ertrag) - kumuliertes_invest, 2) AS gewinn_verlust_euro,
    ROUND(
        CASE 
            WHEN kumuliertes_invest > 0 
            THEN (((depotwert + kumulierter_ertrag) - kumuliertes_invest) / kumuliertes_invest) * 100
            ELSE 0 
        END, 2
    ) AS rendite_prozent
FROM perf_base;
