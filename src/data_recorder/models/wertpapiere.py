import datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_recorder.core.database import Base


class Etf(Base):
    """ETF- und Wertpapier-Stammdaten im Schema wertpapiere."""

    __tablename__ = "etf"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("wkn", name="uq_etf_wkn"),
        {"schema": "wertpapiere"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wkn: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, unique=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ticker_yahoo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    typ: Mapped[str] = mapped_column(String(50), nullable=False, default="ETF")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    invest_daten: Mapped[list["WknInvestDatum"]] = relationship(
        "WknInvestDatum",
        back_populates="etf",
        cascade="all, delete-orphan",
    )
    wert_daten: Mapped[list["WknWertDatum"]] = relationship(
        "WknWertDatum",
        back_populates="etf",
        cascade="all, delete-orphan",
    )
    ertrag_daten: Mapped[list["WknErtragDatum"]] = relationship(
        "WknErtragDatum",
        back_populates="etf",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Etf(id={self.id}, wkn='{self.wkn}', name='{self.name}', ticker='{self.ticker_yahoo}', aktiv={self.aktiv})>"


class WknInvestDatum(Base):
    """Monatliche Sparplan-Investitionsbeträge im Schema wertpapiere."""

    __tablename__ = "wkn_invest_datum"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("wkn_id", "datum", name="uq_wkn_invest_wkn_datum"),
        {"schema": "wertpapiere"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wkn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wertpapiere.etf.id"),
        nullable=False,
        index=True,
    )
    datum: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    invest: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    etf: Mapped[Etf] = relationship("Etf", back_populates="invest_daten")

    def __repr__(self) -> str:
        return f"<WknInvestDatum(id={self.id}, wkn_id={self.wkn_id}, datum={self.datum}, invest={self.invest})>"


class WknWertDatum(Base):
    """Historische Depotwerte / Kurswerte im Schema wertpapiere."""

    __tablename__ = "wkn_wert_datum"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("wkn_id", "datum", name="uq_wkn_wert_wkn_datum"),
        {"schema": "wertpapiere"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wkn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wertpapiere.etf.id"),
        nullable=False,
        index=True,
    )
    datum: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    wert: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    etf: Mapped[Etf] = relationship("Etf", back_populates="wert_daten")

    def __repr__(self) -> str:
        return f"<WknWertDatum(id={self.id}, wkn_id={self.wkn_id}, datum={self.datum}, wert={self.wert})>"


class WknErtragDatum(Base):
    """Erträge, Dividenden und Ausschüttungen im Schema wertpapiere."""

    __tablename__ = "wkn_ertrag_datum"
    __table_args__: ClassVar[tuple[Any, ...]] = (
        UniqueConstraint("wkn_id", "datum", "typ", name="uq_wkn_ertrag_wkn_datum_typ"),
        {"schema": "wertpapiere"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wkn_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wertpapiere.etf.id"),
        nullable=False,
        index=True,
    )
    datum: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    betrag: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    typ: Mapped[str] = mapped_column(String(50), nullable=False, default="DIVIDENDE")

    etf: Mapped[Etf] = relationship("Etf", back_populates="ertrag_daten")

    def __repr__(self) -> str:
        return f"<WknErtragDatum(id={self.id}, wkn_id={self.wkn_id}, datum={self.datum}, betrag={self.betrag}, typ='{self.typ}')>"
