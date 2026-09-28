# 📊 Apache Superset: SQL-Views & Dashboard-Anleitung (`data-recording`)

Dieses Dokument beschreibt die für **Apache Superset** bereitgestellten SQL-Views in MySQL 8 sowie die Schritt-für-Schritt-Anleitung zur Erstellung aussagekräftiger Dashboards für Wärmepumpe, Heizkostenvergleich und Portfolio-Performance.

---

## 🏛️ 1. Bereitgestellte SQL-Views

Alle Views sind für **MySQL 8** optimiert, unterstützen `ONLY_FULL_GROUP_BY` und liegen im Verzeichnis [`database/views/`](../database/views/) sowie gebündelt in der Migration [`database/migrations/04_superset_views.sql`](../database/migrations/04_superset_views.sql).

| View-Name | Schema | Zweck | Zeitbezug |
| :--- | :--- | :--- | :--- |
| **`view_waermepumpe_monats_cop`** | `verbrauch` | Monatliche COP-Werte (Heizen, Warmwasser, Gesamt) & Außentemperaturen | `monat` (Monatserster) |
| **`view_waermepumpe_tages_cop`** | `verbrauch` | Tägliche COP-Werte & Temperaturverläufe für feingranulare Charts | `datum` (Tag) |
| **`view_heizkosten_vergleich_oel_vs_wp`** | `verbrauch` | Monetärer Vergleich: WP-Stromkosten vs. hypothetische Öl-Kosten & Netto-Ersparnis | `monat` (Monatserster) |
| **`view_portfolio_performance`** | `wertpapiere` | Historische Performance je Wertpapier (Invest, Depotwert, Dividenden, Rendite) | `datum` (Stichtag) |
| **`view_portfolio_uebersicht_aktuell`** | `wertpapiere` | Aktuelle Stichtagsübersicht aller Wertpapiere für KPI-Cards und Tabellen | `letzter_stichtag` |

---

## 🔍 2. Detaillierte View-Beschreibungen & Berechnungslogik

### 2.1 `view_waermepumpe_monats_cop` (Schema: `verbrauch`)
Aggregiert die stündlichen eBUS-Messwerte der Vaillant aroTHERM auf Monatsbasis:
* **Wärmemengen & Strom:** Berechnet die monatlichen Zählerdifferenzen (`MAX - MIN`) für Heizung (`waerme_heizen_kwh`, `strom_heizen_kwh`), Warmwasser (`waerme_warmwasser_kwh`, `strom_warmwasser_kwh`) und Gesamt (`waerme_gesamt_kwh`, `strom_gesamt_kwh`).
* **Arbeitszahlen (COP):**
  $$\text{COP}_{\text{Heizen}} = \frac{\text{Wärme}_{\text{Heizen}}}{\text{Strom}_{\text{Heizen}}}$$
  $$\text{COP}_{\text{Warmwasser}} = \frac{\text{Wärme}_{\text{Warmwasser}}}{\text{Strom}_{\text{Warmwasser}}}$$
  $$\text{COP}_{\text{Gesamt}} = \frac{\text{Wärme}_{\text{Gesamt}}}{\text{Strom}_{\text{Gesamt}}}$$
* **Temperaturvergleich:** `aussentemperatur_avg`, `aussentemperatur_min`, `aussentemperatur_max` sowie Vor- und Rücklauftemperaturen.

### 2.2 `view_heizkosten_vergleich_oel_vs_wp` (Schema: `verbrauch`)
Berechnet die monatliche finanzielle Ersparnis der Wärmepumpe gegenüber einer alten Ölheizung:
1. **WP-Stromkosten:**
   $$\text{Stromkosten}_{\text{WP}} = \text{Stromverbrauch (kWh)} \times \text{hinterlegter Stromtarif (€/kWh)}$$
   *(Tarif dynamisch aus Tabelle `verbrauch.kosten`, Fallback: 0,30 €/kWh)*
2. **Hypothetische Heizölkosten:**
   $$\text{Öläquivalent (Liter)} = \frac{\text{Erzeugte Wärme (kWh)}}{10\text{ kWh/L} \times 0{,}88\text{ (Kesselwirkungsgrad)}} = \frac{\text{Erzeugte Wärme}}{8{,}8}$$
   $$\text{Heizölkosten} = \text{Öläquivalent (Liter)} \times \text{regionaler Heizölpreis (€/L)}$$
   *(Heizölpreis dynamisch aus Tabelle `verbrauch.heizoel_preis`, Fallback: 1,05 €/L)*
3. **Netto-Ersparnis:**
   $$\text{Netto-Ersparnis (€)} = \text{Heizölkosten} - \text{Stromkosten}_{\text{WP}}$$
   $$\text{Ersparnis (\%)} = \frac{\text{Netto-Ersparnis}}{\text{Heizölkosten}} \times 100$$

### 2.3 `view_portfolio_performance` (Schema: `wertpapiere`)
Verknüpft Wertpapier-Stammdaten (`etf`), Einzahlungen (`wkn_invest_datum`), Depotbewertungen (`wkn_wert_datum`) und Erträge (`wkn_ertrag_datum`):
* **Kumuliertes Invest:** Summe aller Sparplan- und Sonderzahlungen bis zum jeweiligen Stichtag.
* **Kumulierter Ertrag:** Summe aller erhaltenen Dividenden und Ausschüttungen bis zum Stichtag.
* **Gesamtwert:** $\text{Depotwert} + \text{Kumulierte Erträge}$.
* **Gesamtrendite (€ & %):**
  $$\text{Gewinn/Verlust (€)} = (\text{Depotwert} + \text{Erträge}) - \text{Kumuliertes Invest}$$
  $$\text{Rendite (\%)} = \frac{\text{Gewinn/Verlust}}{\text{Kumuliertes Invest}} \times 100$$

### 2.4 `view_portfolio_uebersicht_aktuell` (Schema: `wertpapiere`)
Liefert für jedes Wertpapier genau eine Zeile mit dem aktuellsten Bewertungsstand, den Gesamteinzahlungen und der Gesamtperformance.

---

## 🚀 3. Registrierung der Datasets in Apache Superset

> ℹ️ **Hinweis:** Auf der Synology DS218+ sind alle 5 Datasets bereits in Superset unter der Datenbankverbindung **`Wertpapiere`** (IDs 60 bis 64) vorkonfiguriert!

Falls ein Dataset manuell neu registriert oder synchronisiert werden soll:

1. Öffne Apache Superset im Browser: **[http://192.168.2.125:8088](http://192.168.2.125:8088)**
2. Navigiere zu **Data ➔ Datasets** und klicke oben rechts auf **`+ DATASET`**.
3. Wähle die Einstellungen:
   * **Database:** `Wertpapiere`
   * **Schema:** `verbrauch` (für WP/Heizung) bzw. `wertpapiere` (für Portfolio)
   * **Table Name:** Wähle die gewünschte View (z. B. `view_waermepumpe_monats_cop`).
4. Klicke auf **ADD**.
5. Klicke beim neu erstellten Dataset auf das Stift-Symbol (**Edit Dataset**):
   * Im Reiter **Columns** prüfen, ob die Datumsspalte (`monat`, `datum` bzw. `letzter_stichtag`) als **Is temporal** markiert ist.
   * Auf **Save** klicken.

---

## 📈 4. Empfohlene Chart-Konfigurationen für Dashboards

### Dashboard 1: Wärmepumpen-Effizienz & Heizkosten (`Schäfers-Verbrauch`)

#### Chart 1.1: Arbeitszahl (COP) vs. Außentemperatur (Dual-Axis Line Chart)
* **Dataset:** `view_waermepumpe_monats_cop` (oder `view_waermepumpe_tages_cop`)
* **Chart-Typ:** `Mixed Timeseries` oder `ECharts Timeseries Line`
* **Time Column:** `monat` (Time Grain: `Month`)
* **Y-Achse 1 (Links):**
  * Metriken: `AVG(cop_gesamt)` (Bezeichnung: Gesamtarbeitszahl), `AVG(cop_heizen)`, `AVG(cop_warmwasser)`
  * Y-Achsen-Format: `0.00` (z. B. 3.80)
* **Y-Achse 2 (Rechts):**
  * Metrik: `AVG(aussentemperatur_avg)` (Bezeichnung: Mittlere Außentemperatur)
  * Y-Achsen-Format: `0.0 °C`
* **Aussage:** Visualisiert den thermodynamischen Zusammenhang zwischen kälteren Wintermonaten und der Wärmepumpeneffizienz.

#### Chart 1.2: Energiebilanz (Stacked Bar Chart)
* **Dataset:** `view_waermepumpe_monats_cop`
* **Chart-Typ:** `ECharts Timeseries Bar`
* **Time Column:** `monat`
* **Metriken:** `SUM(waerme_heizen_kwh)`, `SUM(waerme_warmwasser_kwh)`, `SUM(strom_gesamt_kwh)`
* **Stack:** Enabled

#### Chart 1.3: Heizkosten-Vergleich: Öl vs. Wärmepumpe (Grouped Bar Chart)
* **Dataset:** `view_heizkosten_vergleich_oel_vs_wp`
* **Chart-Typ:** `ECharts Timeseries Bar`
* **Time Column:** `monat`
* **Metriken:**
  * `SUM(stromkosten_wp_euro)` (Farbe: Grün / Blau)
  * `SUM(heizoelkosten_hypothetisch_euro)` (Farbe: Rot / Orange)
* **Aussage:** Direkter Monatsvergleich der reinen Betriebskosten beider Heizsysteme.

#### Chart 1.4: Netto-Ersparnis & Einsparungsquote (Big Number with Trendline)
* **Dataset:** `view_heizkosten_vergleich_oel_vs_wp`
* **Chart-Typ:** `Big Number with Trendline`
* **Metrik:** `SUM(netto_ersparnis_euro)`
* **Untertitel:** Kumulierte Kostenersparnis gegenüber Ölheizung in Euro.

---

### Dashboard 2: Portfolio-Performance & Finanzen (`Schäfers-Finanzen`)

#### Chart 2.1: Depotwert vs. Einzahlungen über die Zeit (Area / Line Chart)
* **Dataset:** `view_portfolio_performance`
* **Chart-Typ:** `ECharts Timeseries Line` (mit Area-Füllung)
* **Time Column:** `datum`
* **Metriken:**
  * `SUM(depotwert)` (Aktueller Kurswert)
  * `SUM(kumuliertes_invest)` (Eingezahltes Eigenkapital)
  * `SUM(gesamtwert_inkl_ertrag)` (Gesamtwert inkl. Dividenden)
* **Aussage:** Zeigt den Zinseszinseffekt und die Gesamtwertentwicklung über alle Investitionen hinweg.

#### Chart 2.2: Depot-Allokation nach Wertpapieren (Donut / Pie Chart)
* **Dataset:** `view_portfolio_uebersicht_aktuell`
* **Chart-Typ:** `Pie Chart`
* **Dimension:** `name` (oder `wkn`)
* **Metrik:** `SUM(aktueller_wert)`
* **Filter:** `aktiv = TRUE`
* **Aussage:** Zeigt die prozentuale Vermögensverteilung über die gehaltenen ETFs/Aktien.

#### Chart 2.3: Aktuelle Depot-Performance (Tabelle mit Ampel-Farben)
* **Dataset:** `view_portfolio_uebersicht_aktuell`
* **Chart-Typ:** `Table`
* **Dimensionen:** `wkn`, `name`, `typ`, `letzter_stichtag`
* **Metriken:** `aktueller_wert`, `invest_gesamt`, `ertrag_gesamt`, `gewinn_verlust_euro`, `rendite_gesamt_prozent`
* **Conditional Formatting:**
  * `rendite_gesamt_prozent > 0`: Grün
  * `rendite_gesamt_prozent < 0`: Rot

#### Chart 2.4: Gesamtertrag / Dividenden (Big Number Total)
* **Dataset:** `view_portfolio_uebersicht_aktuell`
* **Chart-Typ:** `Big Number Total`
* **Metrik:** `SUM(ertrag_gesamt)`
* **Header Format:** `#,###.00 €`
