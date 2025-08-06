-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: mysql_db
-- Erstellungszeit: 06. Aug 2025 um 13:23
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
-- Datenbank: `wertpapiere`
--

-- --------------------------------------------------------

--
-- Tabellenstruktur für Tabelle `etf`
--

CREATE TABLE `etf` (
  `id` int NOT NULL,
  `wkn` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Daten für Tabelle `etf`
--

INSERT INTO `etf` (`id`, `wkn`) VALUES
(1, 'A1T8FV'),
(2, 'A1XB5U'),
(3, 'LYX0CA'),
(4, 'A1XJ53'),
(5, 'A113FF'),
(6, 'A113FD'),
(7, 'Crypto Ether'),
(9, 'A1JT1B');

--
-- Indizes der exportierten Tabellen
--

--
-- Indizes für die Tabelle `etf`
--
ALTER TABLE `etf`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT für exportierte Tabellen
--

--
-- AUTO_INCREMENT für Tabelle `etf`
--
ALTER TABLE `etf`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
