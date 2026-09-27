import asyncio
import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_recorder.core.config import Settings, get_settings
from data_recorder.core.database import get_db_session
from data_recorder.models.wertpapiere import Etf, WknWertDatum

logger = logging.getLogger(__name__)


@dataclass
class StockPriceResult:
    """Extracted stock price result for a security and date."""

    wkn_id: int
    wkn: str
    ticker: str
    datum: datetime.date
    wert: Decimal


class StockPriceService:
    """Service to fetch Tradegate closing prices from Yahoo Finance and persist them into MySQL."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_active_securities(self, session: Session) -> list[Etf]:
        """Returns all securities from wertpapiere.etf where aktiv is TRUE and ticker_yahoo is set."""
        stmt = (
            select(Etf)
            .where(Etf.aktiv.is_(True))
            .where(Etf.ticker_yahoo.is_not(None))
            .order_by(Etf.id)
        )
        candidates = session.execute(stmt).scalars().all()
        return [sec for sec in candidates if sec.ticker_yahoo and sec.ticker_yahoo.strip()]

    def fetch_closing_price_sync(
        self, ticker_symbol: str, target_date: datetime.date | None = None
    ) -> tuple[Decimal, datetime.date] | None:
        """Synchronously queries Yahoo Finance API for the closing price of the given ticker.

        Returns (price, quote_date) or None on error/missing data.
        """
        clean_ticker = ticker_symbol.strip()
        if not clean_ticker:
            return None

        try:
            ticker = yf.Ticker(clean_ticker)
            # Retrieve 5 trading days to account for weekends/bank holidays
            hist = ticker.history(period="5d")

            if hist is None or hist.empty:
                logger.warning(
                    "Yahoo Finance lieferte keine Kursdaten für Ticker '%s'.",
                    clean_ticker,
                )
                return None

            close_col = next((c for c in hist.columns if str(c).lower() == "close"), None)
            if close_col is None:
                logger.warning(
                    "Spalte 'Close' nicht in Yahoo-Finance-Historie für '%s' gefunden.",
                    clean_ticker,
                )
                return None

            if target_date is not None:
                matching = hist[hist.index.date == target_date]
                if matching.empty:
                    logger.warning(
                        "Kein Kurs für das Zieldatum %s bei Ticker '%s' in den letzten 5 Handelstagen gefunden.",
                        target_date,
                        clean_ticker,
                    )
                    return None
                row = matching.iloc[-1]
                quote_date = target_date
            else:
                row = hist.iloc[-1]
                quote_date = hist.index[-1].date()

            raw_price = row[close_col]
            if raw_price is None or pd_is_na(raw_price):
                logger.warning(
                    "Schlusskurs für Ticker '%s' am %s ist ungültig (NA/None).",
                    clean_ticker,
                    quote_date,
                )
                return None

            price = Decimal(str(round(float(raw_price), 2)))
            if price <= Decimal("0"):
                logger.warning(
                    "Unplausibler Schlusskurs <= 0 (%s) für Ticker '%s' am %s.",
                    price,
                    clean_ticker,
                    quote_date,
                )
                return None

            return price, quote_date

        except Exception as exc:
            logger.warning(
                "Fehler bei Yahoo-Finance-Kursabfrage für Ticker '%s': %s",
                clean_ticker,
                exc,
            )
            return None

    async def fetch_closing_price(
        self, ticker_symbol: str, target_date: datetime.date | None = None
    ) -> tuple[Decimal, datetime.date] | None:
        """Asynchronous non-blocking wrapper around fetch_closing_price_sync."""
        return await asyncio.to_thread(self.fetch_closing_price_sync, ticker_symbol, target_date)

    def save_stock_price(
        self,
        wkn_id: int,
        datum: datetime.date,
        wert: Decimal,
        session: Session,
    ) -> WknWertDatum:
        """Idempotently saves or updates the stock price in wertpapiere.wkn_wert_datum."""
        stmt = select(WknWertDatum).where(
            WknWertDatum.wkn_id == wkn_id,
            WknWertDatum.datum == datum,
        )
        record = session.execute(stmt).scalar_one_or_none()

        if record is None:
            record = WknWertDatum(
                wkn_id=wkn_id,
                datum=datum,
                wert=wert,
            )
            session.add(record)
        else:
            record.wert = wert

        session.commit()
        session.refresh(record)
        return record

    async def _process_securities(
        self, session: Session, target_date: datetime.date | None = None
    ) -> list[WknWertDatum]:
        """Iterates over active securities, fetches latest quotes, and saves them idempotently."""
        securities = self.get_active_securities(session)
        if not securities:
            logger.info("Keine aktiven Wertpapiere mit hinterlegtem Yahoo-Ticker vorhanden.")
            return []

        saved_records: list[WknWertDatum] = []
        for sec in securities:
            ticker = sec.ticker_yahoo
            if not ticker:
                continue

            try:
                fetch_result = await self.fetch_closing_price(ticker, target_date=target_date)
                if fetch_result is None:
                    logger.warning(
                        "Konnte keinen Kurs für WKN %s (Ticker: %s) ermitteln.",
                        sec.wkn,
                        ticker,
                    )
                    continue

                price, quote_date = fetch_result
                record = self.save_stock_price(
                    wkn_id=sec.id,
                    datum=quote_date,
                    wert=price,
                    session=session,
                )
                record.etf = sec
                saved_records.append(record)
                logger.info(
                    "Kurs für WKN %s (%s) am %s erfolgreich gespeichert: %s €",
                    sec.wkn,
                    ticker,
                    quote_date,
                    price,
                )
            except Exception as exc:
                logger.error(
                    "Fehler beim Verarbeiten von WKN %s (%s): %s",
                    sec.wkn,
                    ticker,
                    exc,
                    exc_info=True,
                )
                session.rollback()

        return saved_records

    async def poll_and_save(
        self,
        session: Session | None = None,
        target_date: datetime.date | None = None,
    ) -> list[WknWertDatum]:
        """Main entry point to fetch and persist quotes for all active securities."""
        if session is not None:
            return await self._process_securities(session, target_date=target_date)

        for db in get_db_session("wertpapiere"):
            return await self._process_securities(db, target_date=target_date)

        return []


def pd_is_na(val: Any) -> bool:
    """Helper to detect pandas/numpy NaN or None values."""
    if val is None:
        return True
    try:
        import math

        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False
