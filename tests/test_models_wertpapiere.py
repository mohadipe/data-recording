import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base
from data_recorder.models.wertpapiere import (
    Etf,
    WknErtragDatum,
    WknInvestDatum,
    WknWertDatum,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {"verbrauch": None, "wertpapiere": None}
        },
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def test_etf_crud(db_session: Session):
    etf = Etf(
        wkn="A1T8FV",
        isin="IE00B4L5Y983",
        name="iShares Core MSCI World UCITS ETF",
        ticker_yahoo="EUNL.DE",
        typ="ETF",
        aktiv=True,
    )
    db_session.add(etf)
    db_session.commit()

    saved = db_session.execute(select(Etf).where(Etf.wkn == "A1T8FV")).scalar_one()
    assert saved.id is not None
    assert saved.isin == "IE00B4L5Y983"
    assert saved.name == "iShares Core MSCI World UCITS ETF"
    assert saved.ticker_yahoo == "EUNL.DE"
    assert saved.typ == "ETF"
    assert saved.aktiv is True

    assert repr(saved).startswith("<Etf")

    # Update
    saved.ticker_yahoo = "EUNL.TG"
    db_session.commit()
    assert db_session.get(Etf, saved.id).ticker_yahoo == "EUNL.TG"

    # Delete
    db_session.delete(saved)
    db_session.commit()
    assert db_session.get(Etf, saved.id) is None


def test_wkn_invest_datum_crud_and_relationship(db_session: Session):
    etf = Etf(wkn="A1XB5U", name="Xtrackers MSCI Emerging Markets")
    db_session.add(etf)
    db_session.commit()

    invest = WknInvestDatum(
        wkn_id=etf.id,
        datum=datetime.date(2025, 1, 2),
        invest=Decimal("150.00"),
    )
    db_session.add(invest)
    db_session.commit()

    saved = db_session.execute(
        select(WknInvestDatum).where(WknInvestDatum.wkn_id == etf.id)
    ).scalar_one()
    assert saved.id is not None
    assert saved.invest == Decimal("150.00")
    assert saved.etf.wkn == "A1XB5U"
    assert len(etf.invest_daten) == 1
    assert etf.invest_daten[0].id == saved.id
    assert repr(saved).startswith("<WknInvestDatum")

    # Update
    saved.invest = Decimal("200.00")
    db_session.commit()
    assert db_session.get(WknInvestDatum, saved.id).invest == Decimal("200.00")

    # Delete
    db_session.delete(saved)
    db_session.commit()
    assert db_session.get(WknInvestDatum, saved.id) is None


def test_wkn_wert_datum_crud_and_relationship(db_session: Session):
    etf = Etf(wkn="LYX0CA", name="Lyxor Core DAX")
    db_session.add(etf)
    db_session.commit()

    wert = WknWertDatum(
        wkn_id=etf.id,
        datum=datetime.date(2025, 1, 15),
        wert=Decimal("4520.80"),
    )
    db_session.add(wert)
    db_session.commit()

    saved = db_session.execute(
        select(WknWertDatum).where(WknWertDatum.wkn_id == etf.id)
    ).scalar_one()
    assert saved.id is not None
    assert saved.wert == Decimal("4520.80")
    assert saved.etf.wkn == "LYX0CA"
    assert len(etf.wert_daten) == 1
    assert etf.wert_daten[0].id == saved.id
    assert repr(saved).startswith("<WknWertDatum")

    # Update
    saved.wert = Decimal("4600.00")
    db_session.commit()
    assert db_session.get(WknWertDatum, saved.id).wert == Decimal("4600.00")

    # Delete
    db_session.delete(saved)
    db_session.commit()
    assert db_session.get(WknWertDatum, saved.id) is None


def test_wkn_ertrag_datum_crud_and_relationship(db_session: Session):
    etf = Etf(wkn="A1JT1B", name="Vanguard FTSE All-World High Dividend Yield")
    db_session.add(etf)
    db_session.commit()

    ertrag = WknErtragDatum(
        wkn_id=etf.id,
        datum=datetime.date(2025, 6, 20),
        betrag=Decimal("45.60"),
        typ="DIVIDENDE",
    )
    db_session.add(ertrag)
    db_session.commit()

    saved = db_session.execute(
        select(WknErtragDatum).where(WknErtragDatum.wkn_id == etf.id)
    ).scalar_one()
    assert saved.id is not None
    assert saved.betrag == Decimal("45.60")
    assert saved.typ == "DIVIDENDE"
    assert saved.etf.wkn == "A1JT1B"
    assert len(etf.ertrag_daten) == 1
    assert etf.ertrag_daten[0].id == saved.id
    assert repr(saved).startswith("<WknErtragDatum")

    # Update
    saved.betrag = Decimal("48.10")
    db_session.commit()
    assert db_session.get(WknErtragDatum, saved.id).betrag == Decimal("48.10")

    # Delete
    db_session.delete(saved)
    db_session.commit()
    assert db_session.get(WknErtragDatum, saved.id) is None
