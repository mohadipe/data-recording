import datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_recorder.core.database import Base


class Zaehler(Base):
    """Zähler-Stammdaten im Schema verbrauch."""

    __tablename__ = "zaehler"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "verbrauch"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geraete_nr: Mapped[str] = mapped_column(String(255), nullable=False)
    einbau_dt: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ausbau_dt: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    typ: Mapped[str] = mapped_column(String(255), nullable=False)

    messwerte: Mapped[list["Messwert"]] = relationship(
        "Messwert",
        back_populates="zaehler",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Zaehler(id={self.id}, geraete_nr='{self.geraete_nr}', typ='{self.typ}')>"
        )


class Messwert(Base):
    """Messwerte für Zählerstände im Schema verbrauch."""

    __tablename__ = "messwerte"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("zaehler_id", "datum", name="uq_zaehler_datum"),
        {"schema": "verbrauch"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zaehler_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("verbrauch.zaehler.id"),
        nullable=False,
        index=True,
    )
    datum: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    wert: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    einheit: Mapped[str] = mapped_column(String(255), nullable=False)

    zaehler: Mapped[Zaehler] = relationship("Zaehler", back_populates="messwerte")

    def __repr__(self) -> str:
        return f"<Messwert(id={self.id}, zaehler_id={self.zaehler_id}, datum={self.datum}, wert={self.wert} {self.einheit})>"


# Alias for backwards compatibility with plural table naming
Messwerte = Messwert


class WaermepumpeStundenwert(Base):
    """Stündliche Messwerte und Arbeitszahlen der Wärmepumpe im Schema verbrauch."""

    __tablename__ = "waermepumpe_stundenwert"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("zeitstempel", name="uq_wp_zeitstempel"),
        {"schema": "verbrauch"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zeitstempel: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )
    aussentemperatur: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    vorlauf_temp: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    ruecklauf_temp: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    ertrag_gesamt_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    strom_gesamt_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    ertrag_heizen_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    strom_heizen_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    ertrag_warmwasser_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    strom_warmwasser_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    cop_aktuell: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<WaermepumpeStundenwert(id={self.id}, zeitstempel={self.zeitstempel}, cop={self.cop_aktuell})>"


class HeizoelPreis(Base):
    """Regionale Heizölpreis-Historie zur Kosten-Vergleichsberechnung im Schema verbrauch."""

    __tablename__ = "heizoel_preis"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint(
            "datum", "plz", "menge_liter", name="uq_heizoel_datum_plz_menge"
        ),
        {"schema": "verbrauch"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    datum: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    plz: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    menge_liter: Mapped[int] = mapped_column(Integer, nullable=False)
    preis_pro_liter: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    def __repr__(self) -> str:
        return f"<HeizoelPreis(id={self.id}, datum={self.datum}, plz='{self.plz}', preis={self.preis_pro_liter})>"
