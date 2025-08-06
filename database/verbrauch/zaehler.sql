-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: mysql_db
-- Erstellungszeit: 06. Aug 2025 um 13:18
-- Server-Version: 8.0.32
-- PHP-Version: 8.1.16

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Datenbank: `verbrauch`
--

-- --------------------------------------------------------

--
-- Tabellenstruktur für Tabelle `zaehler`
--

CREATE TABLE `zaehler` (
  `id` int NOT NULL,
  `geraete_nr` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `einbau_dt` date NOT NULL,
  `ausbau_dt` date NOT NULL,
  `typ` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Daten für Tabelle `zaehler`
--

INSERT INTO `zaehler` (`id`, `geraete_nr`, `einbau_dt`, `ausbau_dt`, `typ`) VALUES
(1, '71792750', '2024-12-03', '2030-12-03', 'WASSER'),
(2, '200042394A', '2020-11-30', '2026-11-30', 'WASSER'),
(3, '1 EMH00 0988 6538', '2020-06-25', '2026-06-25', 'STROM'),
(4, '1 EMH00 0988 6539', '2020-06-25', '2026-06-25', 'STROM'),
(5, '55215647', '2017-02-28', '2036-02-28', 'STROM'),
(6, '24389158', '2025-03-01', '2031-03-01', 'WAERME'),
(7, '24389048', '2025-03-01', '2031-03-01', 'WAERME'),
(8, '57603401', '2019-12-03', '2024-12-03', 'WASSER'),
(9, '45021701', '2013-12-03', '2019-12-03', 'WASSER'),
(10, '53390595', '2014-06-24', '2020-06-24', 'STROM'),
(11, '39964317', '2014-06-24', '2020-06-24', 'STROM'),
(12, '3075602', '2018-03-01', '2025-03-01', 'WAERME'),
(13, '3075516', '2018-03-01', '2025-03-01', 'WAERME'),
(14, '3075600', '2018-03-01', '2025-03-01', 'WAERME'),
(15, 'Ölmenge', '2017-02-28', '2024-12-23', 'VOLUMEN');

--
-- Indizes der exportierten Tabellen
--

--
-- Indizes für die Tabelle `zaehler`
--
ALTER TABLE `zaehler`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT für exportierte Tabellen
--

--
-- AUTO_INCREMENT für Tabelle `zaehler`
--
ALTER TABLE `zaehler`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=16;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
