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
