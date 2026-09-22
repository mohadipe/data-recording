from pathlib import Path


def test_migration_file_exists_and_content():
    migration_file = (
        Path(__file__).parent.parent
        / "database"
        / "migrations"
        / "01_init_new_tables.sql"
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
    assert "add column if not exists isin" in content.lower()
    assert "add column if not exists name" in content.lower()
    assert "add column if not exists ticker_yahoo" in content.lower()
    assert "add column if not exists typ" in content.lower()
    assert "add column if not exists aktiv" in content.lower()
