import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base
from data_recorder.models.verbrauch import (
    HeizoelPreis,
    Messwert,
    WaermepumpeStundenwert,
    Zaehler,
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


def test_zaehler_crud(db_session: Session):
    zaehler = Zaehler(
        geraete_nr="1 EMH00 0988 6538",
        einbau_dt=datetime.date(2020, 6, 25),
        ausbau_dt=datetime.date(2026, 6, 25),
        typ="STROM",
    )
    db_session.add(zaehler)
    db_session.commit()

    saved = db_session.execute(
        select(Zaehler).where(Zaehler.geraete_nr == "1 EMH00 0988 6538")
    ).scalar_one()
    assert saved.id is not None
    assert saved.typ == "STROM"
    assert repr(saved).startswith("<Zaehler")

    # Update
    saved.typ = "STROM_WP"
    db_session.commit()
    updated = db_session.get(Zaehler, saved.id)
    assert updated.typ == "STROM_WP"

    # Delete
    db_session.delete(updated)
    db_session.commit()
    assert db_session.get(Zaehler, saved.id) is None


def test_messwert_crud_and_relationship(db_session: Session):
    zaehler = Zaehler(
        geraete_nr="71792750",
        einbau_dt=datetime.date(2024, 12, 3),
        ausbau_dt=datetime.date(2030, 12, 3),
        typ="WASSER",
    )
    db_session.add(zaehler)
    db_session.commit()

    messwert = Messwert(
        zaehler_id=zaehler.id,
        datum=datetime.date(2025, 3, 1),
        wert=Decimal("32.50"),
        einheit="M3",
    )
    db_session.add(messwert)
    db_session.commit()

    saved = db_session.execute(
        select(Messwert).where(Messwert.zaehler_id == zaehler.id)
    ).scalar_one()
    assert saved.id is not None
    assert saved.wert == Decimal("32.50")
    assert saved.einheit == "M3"
    assert saved.zaehler.geraete_nr == "71792750"
    assert len(zaehler.messwerte) == 1
    assert zaehler.messwerte[0].id == saved.id
    assert repr(saved).startswith("<Messwert")

    # Update
    saved.wert = Decimal("33.00")
    db_session.commit()
    assert db_session.get(Messwert, saved.id).wert == Decimal("33.00")

    # Delete
    db_session.delete(saved)
    db_session.commit()
    assert db_session.get(Messwert, saved.id) is None


def test_waermepumpe_stundenwert_crud(db_session: Session):
    now = datetime.datetime(2026, 9, 20, 14, 0, 0, tzinfo=datetime.UTC)
    wp = WaermepumpeStundenwert(
        zeitstempel=now,
        aussentemperatur=Decimal("12.50"),
        vorlauf_temp=Decimal("35.20"),
        ruecklauf_temp=Decimal("30.10"),
        ertrag_gesamt_kwh=Decimal("15200.50"),
        strom_gesamt_kwh=Decimal("3800.25"),
        ertrag_heizen_kwh=Decimal("12000.00"),
        strom_heizen_kwh=Decimal("2900.00"),
        ertrag_warmwasser_kwh=Decimal("3200.50"),
        strom_warmwasser_kwh=Decimal("900.25"),
        cop_aktuell=Decimal("4.00"),
    )
    db_session.add(wp)
    db_session.commit()

    saved = db_session.execute(
        select(WaermepumpeStundenwert).where(WaermepumpeStundenwert.zeitstempel == now)
    ).scalar_one()
    assert saved.id is not None
    assert saved.cop_aktuell == Decimal("4.00")
    assert saved.aussentemperatur == Decimal("12.50")
    assert saved.ertrag_gesamt_kwh == Decimal("15200.50")
    assert repr(saved).startswith("<WaermepumpeStundenwert")

    # Update
    saved.cop_aktuell = Decimal("4.25")
    db_session.commit()
    assert db_session.get(WaermepumpeStundenwert, saved.id).cop_aktuell == Decimal(
        "4.25"
    )

    # Delete
    db_session.delete(saved)
    db_session.commit()
    assert db_session.get(WaermepumpeStundenwert, saved.id) is None


def test_heizoel_preis_crud(db_session: Session):
    preis = HeizoelPreis(
        datum=datetime.date(2026, 9, 20),
        plz="53881",
        menge_liter=3000,
        preis_pro_liter=Decimal("0.9850"),
    )
    db_session.add(preis)
    db_session.commit()

    saved = db_session.execute(
        select(HeizoelPreis).where(HeizoelPreis.plz == "53881")
    ).scalar_one()
    assert saved.id is not None
    assert saved.menge_liter == 3000
    assert saved.preis_pro_liter == Decimal("0.9850")
    assert repr(saved).startswith("<HeizoelPreis")

    # Update
    saved.preis_pro_liter = Decimal("0.9990")
    db_session.commit()
    assert db_session.get(HeizoelPreis, saved.id).preis_pro_liter == Decimal("0.9990")

    # Delete
    db_session.delete(saved)
    db_session.commit()
    assert db_session.get(HeizoelPreis, saved.id) is None
