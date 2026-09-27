import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base
from data_recorder.models.hibiscus import HibiscusKonto, HibiscusUmsatz


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"hibiscus": None}},
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def test_hibiscus_konto_and_umsatz_crud(db_session: Session):
    konto = HibiscusKonto(
        kontonummer="123456789",
        blz="76030080",
        iban="DE12760300801234567890",
        bic="GENODEF1M01",
        bezeichnung="Girokonto Hauptkonto",
        name="Sven",
    )
    db_session.add(konto)
    db_session.commit()

    saved_konto = db_session.execute(
        select(HibiscusKonto).where(HibiscusKonto.kontonummer == "123456789")
    ).scalar_one()
    assert saved_konto.id is not None
    assert saved_konto.iban == "DE12760300801234567890"
    assert repr(saved_konto).startswith("<HibiscusKonto")

    umsatz = HibiscusUmsatz(
        konto_id=saved_konto.id,
        datum=datetime.date(2025, 4, 1),
        valuta=datetime.date(2025, 4, 1),
        betrag=Decimal("-150.00"),
        empfaenger_name="Cortal Consors",
        empfaenger_konto="987654321",
        empfaenger_blz="76030080",
        zweck="Sparplan WKN: A1T8FV",
        zweck2="Ausfuehrung 01.04.2025",
        art="Dauerauftrag",
    )
    db_session.add(umsatz)
    db_session.commit()

    saved_umsatz = db_session.execute(
        select(HibiscusUmsatz).where(HibiscusUmsatz.id == umsatz.id)
    ).scalar_one()
    assert saved_umsatz.id is not None
    assert saved_umsatz.betrag == Decimal("-150.00")
    assert saved_umsatz.konto.kontonummer == "123456789"
    assert len(saved_konto.umsatz_daten) == 1
    assert repr(saved_umsatz).startswith("<HibiscusUmsatz")

    # Delete
    db_session.delete(saved_konto)
    db_session.commit()
    assert db_session.get(HibiscusKonto, saved_konto.id) is None
    assert db_session.get(HibiscusUmsatz, saved_umsatz.id) is None
