-- ==============================================================================
-- View 6: view_portfolio_dividenden
-- Schema: wertpapiere
-- Zweck: Einzelaufstellung aller Dividenden- und Ertragszahlungen pro Wertpapier
--        für Superset-Charts mit Zeit- und WKN-Filterung.
-- ==============================================================================

USE wertpapiere;

CREATE OR REPLACE VIEW wertpapiere.view_portfolio_dividenden AS
SELECT 
    er.id AS id,
    er.datum AS datum,
    e.id AS wkn_id,
    e.wkn AS wkn,
    e.name AS name,
    e.depot AS depot,
    er.typ AS typ,
    er.betrag AS betrag
FROM wertpapiere.wkn_ertrag_datum er
JOIN wertpapiere.etf e ON er.wkn_id = e.id;
