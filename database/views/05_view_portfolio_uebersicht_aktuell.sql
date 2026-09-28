-- ==============================================================================
-- View 5: view_portfolio_uebersicht_aktuell
-- Schema: wertpapiere
-- Zweck: Aktuelle Stichtagsübersicht über alle Wertpapiere für KPI-Cards und Tabellen.
--        Zeigt für jedes aktive Wertpapier den letzten Stand, Gesamt-Investitionen,
--        Gesamt-Erträge sowie absolute und prozentuale Gesamtrendite.
-- ==============================================================================

USE wertpapiere;

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
