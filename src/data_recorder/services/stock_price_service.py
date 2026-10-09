import asyncio
import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from data_recorder.core.config import Settings, get_settings
from data_recorder.core.database import get_db_session
from data_recorder.models.wertpapiere import Etf, WknKursDatum
from data_recorder.services.stock_price_providers import (
    StockPriceProvider,
    TradegateProvider,
    YahooFinanceProvider,
)

logger = logging.getLogger(__name__)


@dataclass
class StockPriceResult:
    """Extracted stock price result for a security and date."""

    wkn_id: int
    wkn: str
    ticker: str
    datum: datetime.date
    kurs: Decimal
    source: str = "tradegate"

    def __init__(
        self,
        wkn_id: int,
        wkn: str,
        ticker: str,
        datum: datetime.date,
        kurs: Decimal | None = None,
        wert: Decimal | None = None,
        source: str = "tradegate",
    ) -> None:
        self.wkn_id = wkn_id
        self.wkn = wkn
        self.ticker = ticker
        self.datum = datum
        self.source = source
        if kurs is not None:
            self.kurs = kurs
        elif wert is not None:
            self.kurs = wert
        else:
            raise ValueError("Either 'kurs' or 'wert' must be provided.")

    @property
    def wert(self) -> Decimal:
        """Backward-compatibility alias for kurs."""
        return self.kurs

    @wert.setter
    def wert(self, value: Decimal) -> None:
        self.kurs = value


class StockPriceService:
    """Service to fetch stock and ETF closing prices via Tradegate (Primary) and Yahoo Finance (Fallback) and persist them into MySQL."""

    def __init__(
        self,
        settings: Settings | None = None,
        providers: list[StockPriceProvider] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.providers: list[StockPriceProvider] = (
            providers
            if providers is not None
            else [TradegateProvider(), YahooFinanceProvider()]
        )

    def get_active_securities(self, session: Session) -> list[Etf]:
        """Returns all active securities from wertpapiere.etf that have at least ISIN, WKN or Ticker set."""
        stmt = (
            select(Etf)
            .where(Etf.aktiv.is_(True))
            .where(
                or_(
                    Etf.isin.is_not(None),
                    Etf.wkn.is_not(None),
                    Etf.ticker_yahoo.is_not(None),
                )
            )
            .order_by(Etf.id)
        )
        candidates = session.execute(stmt).scalars().all()
        return [
            sec
            for sec in candidates
            if (sec.isin and sec.isin.strip())
            or (sec.wkn and sec.wkn.strip())
            or (sec.ticker_yahoo and sec.ticker_yahoo.strip())
        ]

    def fetch_closing_price_sync(
        self,
        ticker_symbol: str,
        target_date: datetime.date | None = None,
        *,
        wkn: str = "",
        isin: str | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        """Synchronously queries the provider chain for price data.

        Returns (price, quote_date, source_provider_name) or None.
        """
        for provider in self.providers:
            try:
                if hasattr(provider, "fetch_price_sync"):
                    result = provider.fetch_price_sync(  # type: ignore[attr-defined]
                        wkn=wkn,
                        isin=isin,
                        ticker=ticker_symbol,
                        target_date=target_date,
                    )
                else:
                    # Async fallback
                    result = asyncio.run(
                        provider.fetch_price(
                            wkn=wkn,
                            isin=isin,
                            ticker=ticker_symbol,
                            target_date=target_date,
                        )
                    )

                if result is not None:
                    price, quote_date, source = result
                    return price, quote_date, source
            except Exception as exc:
                logger.warning(
                    "Provider '%s' fehlgeschlagen für WKN=%s, ISIN=%s, Ticker=%s: %s",
                    getattr(provider, "name", str(provider)),
                    wkn,
                    isin,
                    ticker_symbol,
                    exc,
                )

        return None

    async def fetch_closing_price(
        self,
        ticker_symbol: str,
        target_date: datetime.date | None = None,
        *,
        wkn: str = "",
        isin: str | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        """Asynchronously queries the provider chain for price data."""
        for provider in self.providers:
            try:
                result = await provider.fetch_price(
                    wkn=wkn,
                    isin=isin,
                    ticker=ticker_symbol,
                    target_date=target_date,
                )
                if result is not None:
                    price, quote_date, source = result
                    return price, quote_date, source
            except Exception as exc:
                logger.warning(
                    "Provider '%s' fehlgeschlagen für WKN=%s, ISIN=%s, Ticker=%s: %s",
                    getattr(provider, "name", str(provider)),
                    wkn,
                    isin,
                    ticker_symbol,
                    exc,
                )

        return None

    def save_stock_price(
        self,
        wkn_id: int,
        datum: datetime.date,
        kurs: Decimal | None = None,
        session: Session | None = None,
        *,
        wert: Decimal | None = None,
    ) -> WknKursDatum:
        """Idempotently saves or updates the stock price in wertpapiere.wkn_kurs_datum."""
        actual_kurs = kurs if kurs is not None else wert
        if actual_kurs is None:
            raise ValueError("Either 'kurs' or 'wert' must be provided.")
        if session is None:
            raise ValueError("Database session must be provided.")

        stmt = select(WknKursDatum).where(
            WknKursDatum.wkn_id == wkn_id,
            WknKursDatum.datum == datum,
        )
        record = session.execute(stmt).scalar_one_or_none()

        if record is None:
            record = WknKursDatum(
                wkn_id=wkn_id,
                datum=datum,
                kurs=actual_kurs,
            )
            session.add(record)
        else:
            record.kurs = actual_kurs

        session.commit()
        session.refresh(record)
        return record

    async def _process_securities(
        self, session: Session, target_date: datetime.date | None = None
    ) -> list[WknKursDatum]:
        """Iterates over active securities, fetches quotes via Tradegate/Yahoo providers, and persists them."""
        securities = self.get_active_securities(session)
        if not securities:
            logger.info("Keine aktiven Wertpapiere zur Kursabfrage vorhanden.")
            return []

        saved_records: list[WknKursDatum] = []
        for sec in securities:
            try:
                fetch_result = await self.fetch_closing_price(
                    ticker_symbol=sec.ticker_yahoo or "",
                    target_date=target_date,
                    wkn=sec.wkn,
                    isin=sec.isin,
                )
                if fetch_result is None:
                    logger.warning(
                        "Konnte für WKN %s (%s, ISIN: %s, Ticker: %s) über keinen Provider einen Kurs ermitteln.",
                        sec.wkn,
                        sec.name,
                        sec.isin,
                        sec.ticker_yahoo,
                    )
                    continue

                price, quote_date, source_name = fetch_result
                record = self.save_stock_price(
                    wkn_id=sec.id,
                    datum=quote_date,
                    kurs=price,
                    session=session,
                )
                record.etf = sec
                saved_records.append(record)
                logger.info(
                    "Kurs für WKN %s (%s, ISIN: %s) via %s am %s erfolgreich gespeichert: %s €",
                    sec.wkn,
                    sec.name or sec.wkn,
                    sec.isin or "-",
                    source_name,
                    quote_date,
                    price,
                )
            except Exception as exc:
                logger.error(
                    "Fehler beim Verarbeiten von WKN %s (ISIN: %s): %s",
                    sec.wkn,
                    sec.isin,
                    exc,
                    exc_info=True,
                )
                session.rollback()

        return saved_records

    async def poll_and_save(
        self,
        session: Session | None = None,
        target_date: datetime.date | None = None,
    ) -> list[WknKursDatum]:
        """Main entry point to fetch and persist quotes for all active securities."""
        if session is not None:
            return await self._process_securities(session, target_date=target_date)

        for db in get_db_session("wertpapiere"):
            return await self._process_securities(db, target_date=target_date)

        return []
