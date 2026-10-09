-- Migration 06: Stammdatenpflege für wertpapiere.etf (ISINs & Namen für Tradegate-Integration)
-- Stellt sicher, dass alle aktiven Wertpapiere eine gültige ISIN und Bezeichnung für Tradegate besitzen.

UPDATE wertpapiere.etf 
SET isin = 'IE00B8GKDB10', name = 'Vanguard FTSE All-World High Dividend Yield UCITS ETF USD Distributing', ticker_yahoo = 'VGWD.DE' 
WHERE wkn = 'A1T8FV';

UPDATE wertpapiere.etf 
SET isin = 'IE00BJ0KDQ92', name = 'Xtrackers MSCI World UCITS ETF 1C', ticker_yahoo = 'XMMA.DE' 
WHERE wkn = 'A1XB5U';

UPDATE wertpapiere.etf 
SET isin = 'FR0010527275', name = 'Amundi MSCI Water UCITS ETF Dist', ticker_yahoo = 'LYX0CA.DE' 
WHERE wkn = 'LYX0CA';

UPDATE wertpapiere.etf 
SET isin = 'IE00B3XXRP09', name = 'Vanguard S&P 500 UCITS ETF', ticker_yahoo = 'VUSA.DE' 
WHERE wkn = 'A1XJ53';

UPDATE wertpapiere.etf 
SET isin = 'IE00BKM4GZ66', name = 'iShares Core MSCI Emerging Markets IMI UCITS ETF (Acc)', ticker_yahoo = 'EMIM.DE' 
WHERE wkn = 'A113FF';

UPDATE wertpapiere.etf 
SET isin = 'IE00BKM4H312', name = 'iShares Core MSCI World UCITS ETF EUR Hedged (Acc)', ticker_yahoo = 'IWDE.DE' 
WHERE wkn = 'A113FD';

UPDATE wertpapiere.etf 
SET isin = 'IE00B5M1WJ87', name = 'State Street SPDR S&P Euro Dividend Aristocrats UCITS ETF', ticker_yahoo = 'SPYW.DE' 
WHERE wkn = 'A1JT1B';

UPDATE wertpapiere.etf 
SET isin = 'IE00B4L5Y983', name = 'iShares Core MSCI World UCITS ETF USD (Acc)', ticker_yahoo = 'EUNL.DE' 
WHERE wkn = 'A0RPWH';

UPDATE wertpapiere.etf 
SET isin = 'IE00BK5BQX27', name = 'Vanguard FTSE Developed Europe UCITS ETF EUR Accumulation', ticker_yahoo = 'VWCG.DE' 
WHERE wkn = 'A2PLBK';

UPDATE wertpapiere.etf 
SET isin = 'IE00BJ5JNY98', name = 'iShares MSCI World Information Technology Sector Advanced UCITS ETF', ticker_yahoo = 'AYEW.DE' 
WHERE wkn = 'A2PHCC';

UPDATE wertpapiere.etf 
SET isin = 'IE00BK5BCH80', name = 'L&G Clean Energy UCITS ETF USD Acc', ticker_yahoo = 'RENW.DE' 
WHERE wkn = 'A2QFEN';
