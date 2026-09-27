import datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import (
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_recorder.core.database import Base


class HibiscusKonto(Base):
    """Hibiscus Konto-Stammdaten im Schema hibiscus (lesender Zugriff)."""

    __tablename__ = "konto"
    __table_args__: ClassVar[tuple[Any, ...]] = ({"schema": "hibiscus"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kontonummer: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    blz: Mapped[str | None] = mapped_column(String(50), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    bic: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bezeichnung: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    umsatz_daten: Mapped[list["HibiscusUmsatz"]] = relationship(
        "HibiscusUmsatz",
        back_populates="konto",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<HibiscusKonto(id={self.id}, kontonummer='{self.kontonummer}', iban='{self.iban}', bezeichnung='{self.bezeichnung}')>"


class HibiscusUmsatz(Base):
    """Hibiscus Buchungen/Umsatztabelle im Schema hibiscus (lesender Zugriff)."""

    __tablename__ = "umsatz"
    __table_args__: ClassVar[tuple[Any, ...]] = ({"schema": "hibiscus"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    konto_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hibiscus.konto.id"),
        nullable=False,
        index=True,
    )
    valuta: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    datum: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    betrag: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    empfaenger_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    empfaenger_konto: Mapped[str | None] = mapped_column(String(50), nullable=True)
    empfaenger_blz: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zweck: Mapped[str | None] = mapped_column(Text, nullable=True)
    zweck2: Mapped[str | None] = mapped_column(Text, nullable=True)
    zweck3: Mapped[str | None] = mapped_column(Text, nullable=True)
    kommentar: Mapped[str | None] = mapped_column(Text, nullable=True)
    art: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customerref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primanota: Mapped[str | None] = mapped_column(String(100), nullable=True)

    konto: Mapped[HibiscusKonto | None] = relationship(
        "HibiscusKonto",
        back_populates="umsatz_daten",
    )

    def __repr__(self) -> str:
        return f"<HibiscusUmsatz(id={self.id}, konto_id={self.konto_id}, datum={self.datum}, betrag={self.betrag})>"
