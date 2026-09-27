import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base
from data_recorder.models.hibiscus import HibiscusKonto, HibiscusUmsatz
from data_recorder.models.wertpapiere import (
    Etf,
    HibiscusImportLog,
    WknErtragDatum,
    WknInvestDatum,
)
from data_recorder.services.hibiscus_service import (
    HibiscusService,
    categorize_transaction,
    extract_wkn_or_isin,
)


@pytest.fixture
def db_session():
    """Provides a clean in-memory SQLite database session with mapped schemas."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {
                "verbrauch": None,
                "wertpapiere": None,
                "hibiscus": None,
            }
        },
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_etfs(db_session: Session) -> list[Etf]:
    """Creates sample ETFs for matching in wertpapiere.etf."""
    etfs = [
        Etf(
            id=1,
            wkn="A1T8FV",
            isin="IE00B4L5Y983",
            name="iShares Core MSCI World UCITS ETF",
            ticker_yahoo="EUNL.TG",
            aktiv=True,
        ),
        Etf(
            id=2,
            wkn="A1XB5U",
            isin="LU0274208692",
            name="Xtrackers MSCI Emerging Markets UCITS ETF",
            ticker_yahoo="XMEA.TG",
            aktiv=True,
        ),
        Etf(
            id=3,
            wkn="LYX0CA",
            isin="LU0378438732",
            name="Amundi Core DAX UCITS ETF",
            ticker_yahoo="DAX.TG",
            aktiv=True,
        ),
        Etf(
            id=4,
            wkn="A1JT1B",
            isin="IE00B8GKDB10",
            name="Vanguard FTSE All-World High Dividend Yield UCITS ETF",
            ticker_yahoo="VGWL.TG",
            aktiv=True,
        ),
    ]
    db_session.add_all(etfs)
    db_session.commit()
    return etfs


class TestWknAndIsinExtraction:
    """Tests for regex parsing of WKNs and ISINs from booking texts."""

    def test_extract_wkn_explicit_colon(self):
        text = "Wertpapiere - Sparplan WKN: A1T8FV Ausfuehrung am 01.03.2024"
        identifier, is_isin = extract_wkn_or_isin(text)
        assert identifier == "A1T8FV"
        assert is_isin is False

    def test_extract_wkn_explicit_space(self):
        text = "WERT-PAPIER-KAUF SPARPLAN WKN A1XB5U STK 1,2345"
        identifier, is_isin = extract_wkn_or_isin(text)
        assert identifier == "A1XB5U"
        assert is_isin is False

    def test_extract_wkn_with_dots(self):
        text = "Kauf W.K.N. LYX0CA Ausfuehrung Sparplan"
        identifier, is_isin = extract_wkn_or_isin(text)
        assert identifier == "LYX0CA"
        assert is_isin is False

    def test_extract_isin_explicit(self):
        text = "Wertpapier Ertrag ISIN IE00B8GKDB10 WKN A1JT1B"
        identifier, is_isin = extract_wkn_or_isin(text)
        # Should detect ISIN or WKN
        assert identifier in ("IE00B8GKDB10", "A1JT1B")

    def test_extract_isin_only(self):
        text = "Ausschuettung Dividende ISIN LU0274208692 Betrag 50 EUR"
        identifier, is_isin = extract_wkn_or_isin(text)
        assert identifier == "LU0274208692"
        assert is_isin is True

    def test_extract_wkn_from_known_etfs_fallback(self):
        text = "Ausfuehrung Sparplan A1XB5U 01.04.2024"
        known_wkns = {"A1XB5U": 2, "A1T8FV": 1}
        identifier, is_isin = extract_wkn_or_isin(text, known_wkns=known_wkns)
        assert identifier == "A1XB5U"
        assert is_isin is False

    def test_no_wkn_in_regular_bookings(self):
        negative_texts = [
            "Miete fuer Wohnung Hauptstr. 12, 90579 Langenzenn",
            "REWE Filiale 4312 Muenchen Kartenzahlung 12.05.2024",
            "ALDI SUED sagt danke 05.04.2024 Kartenzahlung",
            "Gehalt / Bezuege Mai 2024 Firma GmbH",
            "Dauerauftrag Taschengeld",
            "Kauf im Supermarkt EDEKA Kartenzahlung 543210",
            "Autokauf Anzahlung VW Golf",
        ]
        known_wkns = {"A1XB5U": 2, "A1T8FV": 1, "LYX0CA": 3, "A1JT1B": 4}
        for text in negative_texts:
            identifier, _ = extract_wkn_or_isin(text, known_wkns=known_wkns)
            assert identifier is None, f"Expected no WKN in: '{text}', but got: '{identifier}'"


class TestTransactionCategorization:
    """Tests for categorizing transactions into Sparplan/Kauf or Dividende/Ausschüttung."""

    def test_categorize_sparplan_negative_amount(self):
        category, typ = categorize_transaction(
            "Wertpapierkauf Sparplan WKN: A1T8FV",
            Decimal("-100.00"),
        )
        assert category == "SPARPLAN"
        assert typ == "SPARPLAN"

    def test_categorize_kauf_negative_amount(self):
        category, typ = categorize_transaction(
            "Kauf WKN: LYX0CA Ausfuehrung",
            Decimal("-250.50"),
        )
        assert category == "SPARPLAN"
        assert typ == "KAUF"

    def test_categorize_dividende_positive_amount(self):
        category, typ = categorize_transaction(
            "DIVIDENDE / GUTSCHRIFT WKN: A1JT1B",
            Decimal("45.60"),
        )
        assert category == "DIVIDENDE"
        assert typ == "DIVIDENDE"

    def test_categorize_ausschuettung_positive_amount(self):
        category, typ = categorize_transaction(
            "Ausschuettung ETF WKN: A1T8FV",
            Decimal("18.75"),
        )
        assert category == "DIVIDENDE"
        assert typ == "AUSSCHUETTUNG"

    def test_categorize_ertrag_positive_amount(self):
        category, typ = categorize_transaction(
            "Ertrag Wertpapier WKN: A1XB5U",
            Decimal("32.10"),
        )
        assert category == "DIVIDENDE"
        assert typ == "ERTRAG"

    def test_negative_sparplan_with_positive_amount_ignored(self):
        category, _ = categorize_transaction(
            "Rueckbuchung Sparplan Kauf",
            Decimal("100.00"),
        )
        assert category is None

    def test_negative_dividende_with_negative_amount_ignored(self):
        category, _ = categorize_transaction(
            "Korrektur Dividende Storno",
            Decimal("-45.60"),
        )
        assert category is None

    def test_negative_regular_booking_ignored(self):
        category, _ = categorize_transaction(
            "Miete Langenzenn",
            Decimal("-850.00"),
        )
        assert category is None


class TestHibiscusScannerService:
    """Integration tests for HibiscusService scanning, matching, and persisting."""

    def test_scan_and_import_sparplan_and_dividende(
        self, db_session: Session, sample_etfs: list[Etf]
    ):
        service = HibiscusService()

        # Create Konto
        konto = HibiscusKonto(
            id=1,
            kontonummer="1234567890",
            blz="76030080",
            iban="DE12760300801234567890",
            bezeichnung="Cortal Consors Giro/Depot",
        )
        db_session.add(konto)

        # Create 3 transactions: 1 Sparplan, 1 Dividende, 1 Supermarkt
        u1 = HibiscusUmsatz(
            id=101,
            konto_id=1,
            datum=datetime.date(2024, 3, 1),
            valuta=datetime.date(2024, 3, 1),
            betrag=Decimal("-150.00"),
            zweck="Wertpapierkauf Sparplan WKN: A1T8FV",
            empfaenger_name="Cortal Consors",
        )
        u2 = HibiscusUmsatz(
            id=102,
            konto_id=1,
            datum=datetime.date(2024, 3, 15),
            valuta=datetime.date(2024, 3, 15),
            betrag=Decimal("42.50"),
            zweck="Dividende / Ertrag WKN A1JT1B",
            empfaenger_name="Vanguard Funds",
        )
        u3 = HibiscusUmsatz(
            id=103,
            konto_id=1,
            datum=datetime.date(2024, 3, 16),
            valuta=datetime.date(2024, 3, 16),
            betrag=Decimal("-35.80"),
            zweck="REWE Filiale 4312 Muenchen Kartenzahlung",
            empfaenger_name="REWE Markt",
        )
        db_session.add_all([u1, u2, u3])
        db_session.commit()

        # Run scanner
        result = service.scan_and_import(
            session_wertpapiere=db_session,
            session_hibiscus=db_session,
        )

        assert result.scanned_count == 3
        assert result.imported_count == 2
        assert result.sparplaene_count == 1
        assert result.dividenden_count == 1
        assert result.skipped_count == 0

        # Verify Sparplan saved in wertpapiere.wkn_invest_datum
        invest_entries = db_session.execute(select(WknInvestDatum)).scalars().all()
        assert len(invest_entries) == 1
        assert invest_entries[0].wkn_id == 1  # A1T8FV
        assert invest_entries[0].datum == datetime.date(2024, 3, 1)
        assert invest_entries[0].invest == Decimal("150.00")  # Positive!

        # Verify Dividende saved in wertpapiere.wkn_ertrag_datum
        ertrag_entries = db_session.execute(select(WknErtragDatum)).scalars().all()
        assert len(ertrag_entries) == 1
        assert ertrag_entries[0].wkn_id == 4  # A1JT1B
        assert ertrag_entries[0].datum == datetime.date(2024, 3, 15)
        assert ertrag_entries[0].betrag == Decimal("42.50")

        # Verify HibiscusImportLog has both transactions
        logs = db_session.execute(select(HibiscusImportLog)).scalars().all()
        assert len(logs) == 2
        log_ids = [log_entry.hibiscus_umsatz_id for log_entry in logs]
        assert 101 in log_ids
        assert 102 in log_ids
        assert 103 not in log_ids

    def test_idempotency_second_run_does_not_duplicate(
        self, db_session: Session, sample_etfs: list[Etf]
    ):
        service = HibiscusService()

        konto = HibiscusKonto(
            id=1,
            kontonummer="1234567890",
            iban="DE12760300801234567890",
            bezeichnung="Cortal Consors",
        )
        u1 = HibiscusUmsatz(
            id=201,
            konto_id=1,
            datum=datetime.date(2024, 4, 2),
            betrag=Decimal("-100.00"),
            zweck="Wertpapier-Sparplan WKN: A1XB5U",
        )
        db_session.add_all([konto, u1])
        db_session.commit()

        # Run 1
        res1 = service.scan_and_import(
            session_wertpapiere=db_session,
            session_hibiscus=db_session,
        )
        assert res1.imported_count == 1

        # Run 2 with same data
        res2 = service.scan_and_import(
            session_wertpapiere=db_session,
            session_hibiscus=db_session,
        )
        assert res2.imported_count == 0
        assert res2.skipped_count == 1

        # Check total rows in wkn_invest_datum
        invest_entries = db_session.execute(select(WknInvestDatum)).scalars().all()
        assert len(invest_entries) == 1
        assert invest_entries[0].invest == Decimal("100.00")

    def test_account_filtering(self, db_session: Session, sample_etfs: list[Etf]):
        service = HibiscusService()

        konto1 = HibiscusKonto(
            id=1,
            kontonummer="DEPOT123",
            iban="DE1111111111",
            bezeichnung="Depot Consors",
        )
        konto2 = HibiscusKonto(
            id=2,
            kontonummer="GIRO456",
            iban="DE2222222222",
            bezeichnung="Anderes Girokonto",
        )
        db_session.add_all([konto1, konto2])

        u1 = HibiscusUmsatz(
            id=301,
            konto_id=1,
            datum=datetime.date(2024, 5, 2),
            betrag=Decimal("-200.00"),
            zweck="Kauf Sparplan WKN: A1T8FV",
        )
        u2 = HibiscusUmsatz(
            id=302,
            konto_id=2,
            datum=datetime.date(2024, 5, 2),
            betrag=Decimal("-200.00"),
            zweck="Kauf Sparplan WKN: A1XB5U",
        )
        db_session.add_all([u1, u2])
        db_session.commit()

        # Filter only DEPOT123
        res = service.scan_and_import(
            session_wertpapiere=db_session,
            session_hibiscus=db_session,
            account_filters=["DEPOT123"],
        )
        assert res.scanned_count == 1
        assert res.imported_count == 1

        invest_entries = db_session.execute(select(WknInvestDatum)).scalars().all()
        assert len(invest_entries) == 1
        assert invest_entries[0].wkn_id == 1  # Only A1T8FV from DEPOT123
