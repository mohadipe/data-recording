-- ==============================================================================
-- View 4: view_portfolio_performance
-- Schema: wertpapiere
-- Zweck: Zeitreihen-Performance-Analyse je Wertpapier und Stichtag.
--        Verknüpft etf, wkn_invest_datum, wkn_wert_datum und wkn_ertrag_datum.
--        Berechnet kumulierte Einzahlungen, aktuellen Depotwert, Erträge (Dividenden)
--        sowie Gesamtrendite in Euro und Prozent.
-- ==============================================================================

USE wertpapiere;

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
    -- Kumuliertes Invest bis zu diesem Stichtag
    COALESCE((
        SELECT SUM(i.invest) 
        FROM wertpapiere.wkn_invest_datum i 
        WHERE i.wkn_id = w.wkn_id AND i.datum <= w.datum
    ), 0.00) AS kumuliertes_invest,
    -- Kumulierte Erträge / Dividenden bis zu diesem Stichtag
    COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = w.wkn_id AND er.datum <= w.datum
    ), 0.00) AS kumulierter_ertrag,
    -- Gesamtwert inklusive Erträge
    ROUND(w.wert + COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = w.wkn_id AND er.datum <= w.datum
    ), 0.00), 2) AS gesamtwert_inkl_ertrag,
    -- Netto-Gewinn/Verlust in Euro
    ROUND((w.wert + COALESCE((
        SELECT SUM(er.betrag) 
        FROM wertpapiere.wkn_ertrag_datum er 
        WHERE er.wkn_id = w.wkn_id AND er.datum <= w.datum
    ), 0.00)) - COALESCE((
        SELECT SUM(i.invest) 
        FROM wertpapiere.wkn_invest_datum i 
        WHERE i.wkn_id = w.wkn_id AND i.datum <= w.datum
    ), 0.00), 2) AS gewinn_verlust_euro,
    -- Gesamtrendite in Prozent
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
