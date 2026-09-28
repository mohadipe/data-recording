from pathlib import Path


def test_migration_file_exists_and_content():
    migration_file = (
        Path(__file__).parent.parent / "database" / "migrations" / "01_init_new_tables.sql"
    )
    assert migration_file.exists(), f"Migration file {migration_file} does not exist"

    content = migration_file.read_text(encoding="utf-8")
    assert len(content) > 0

    # Ensure CREATE TABLE statements are present
    assert "waermepumpe_stundenwert" in content.lower()
    assert "heizoel_preis" in content.lower()
    assert "wkn_ertrag_datum" in content.lower()
    assert "create table if not exists" in content.lower()

    # Ensure ALTER TABLE for etf column extensions are present
    assert "alter table" in content.lower()
    assert "etf" in content.lower()
    assert "isin varchar(12)" in content.lower()
    assert "name varchar(255)" in content.lower()
    assert "ticker_yahoo varchar(50)" in content.lower()
    assert "typ varchar(50)" in content.lower()
    assert "aktiv boolean" in content.lower()


def test_migration_02_hibiscus_import_log_exists_and_content():
    migration_file = (
        Path(__file__).parent.parent / "database" / "migrations" / "02_hibiscus_import_log.sql"
    )
    assert migration_file.exists(), f"Migration file {migration_file} does not exist"

    content = migration_file.read_text(encoding="utf-8")
    assert len(content) > 0
    assert "hibiscus_import_log" in content.lower()
    assert "hibiscus_umsatz_id" in content.lower()
    assert "create table if not exists" in content.lower()
    assert "uq_hibiscus_import_umsatz_id" in content.lower()


def test_migration_03_zaehler_and_messwerte_updates():
    migration_file = (
        Path(__file__).parent.parent / "database" / "migrations" / "03_zaehler_and_messwerte_updates.sql"
    )
    assert migration_file.exists(), f"Migration file {migration_file} does not exist"
    content = migration_file.read_text(encoding="utf-8").lower()
    assert "uq_zaehler_datum_einheit" in content
    assert "1 emh00 0988 6538" in content


def test_migration_04_superset_views_and_view_files():
    migration_file = (
        Path(__file__).parent.parent / "database" / "migrations" / "04_superset_views.sql"
    )
    assert migration_file.exists(), f"Migration file {migration_file} does not exist"
    content = migration_file.read_text(encoding="utf-8").lower()
    assert "view_waermepumpe_monats_cop" in content
    assert "view_waermepumpe_tages_cop" in content
    assert "view_heizkosten_vergleich_oel_vs_wp" in content
    assert "view_portfolio_performance" in content
    assert "view_portfolio_uebersicht_aktuell" in content

    # Check view files directory
    views_dir = Path(__file__).parent.parent / "database" / "views"
    assert views_dir.exists()
    assert (views_dir / "01_view_waermepumpe_monats_cop.sql").exists()
    assert (views_dir / "02_view_waermepumpe_tages_cop.sql").exists()
    assert (views_dir / "03_view_heizkosten_vergleich_oel_vs_wp.sql").exists()
    assert (views_dir / "04_view_portfolio_performance.sql").exists()
    assert (views_dir / "05_view_portfolio_uebersicht_aktuell.sql").exists()

