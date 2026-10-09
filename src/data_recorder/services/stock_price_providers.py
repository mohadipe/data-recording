import asyncio
import datetime
import logging
import re
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any, Protocol

import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


class StockPriceProvider(Protocol):
    """Protocol for financial quote data providers."""

    name: str

    async def fetch_price(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        """Fetches current or closing price for a given security.

        Returns (price, quote_date, provider_name) or None.
        """
        ...


class TradegateProvider:
    """Primary provider: Queries real-time / closing quotes directly from Tradegate Exchange."""

    name: str = "tradegate"
    base_url: str = "https://www.tradegate.de/orderbuch.php"

    def __init__(
        self,
        timeout: float = 10.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch_price_sync(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        """Synchronously scrapes Tradegate orderbook page for the latest price."""
        query_identifier = (isin.strip() if isin and isin.strip() else wkn.strip()) if (isin or wkn) else None
        if not query_identifier:
            logger.debug("TradegateProvider: Weder ISIN noch WKN übergeben.")
            return None

        url = f"{self.base_url}?{urllib.parse.urlencode({'isin': query_identifier})}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                html = response.read().decode("utf-8", errors="ignore")

            price = self._parse_html_price(html)
            if price is None:
                logger.warning(
                    "Tradegate: Kein gültiger Kurs für '%s' im HTML gefunden.",
                    query_identifier,
                )
                return None

            quote_date = target_date or datetime.date.today()
            return price, quote_date, self.name

        except Exception as exc:
            logger.warning(
                "Tradegate: Verbindungs- oder Abfragefehler für '%s': %s",
                query_identifier,
                exc,
            )
            return None

    def _parse_html_price(self, html: str) -> Decimal | None:
        """Extracts the 'Last' price from Tradegate orderbook HTML.

        Format on Tradegate: <strong id="last">131,725</strong> or <td id="last" ...>131,725</td>
        """
        match = re.search(r'id=["\']last["\'][^>]*>([^<]+)<', html, re.IGNORECASE)
        if not match:
            # Fallback regex for class="longprice" containing strong
            match = re.search(r'<td\s+class=["\']longprice["\']>\s*<strong[^>]*>([^<]+)</strong>', html, re.IGNORECASE)

        if not match:
            return None

        raw_val = match.group(1).strip()
        # Clean German number formatting: remove thousand separators '.', replace decimal comma with '.'
        clean_val = raw_val.replace(".", "").replace(",", ".").replace(" ", "").replace("€", "")

        try:
            price = Decimal(clean_val)
            if price <= Decimal("0"):
                return None
            return price
        except Exception:
            return None

    async def fetch_price(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        return await asyncio.to_thread(
            self.fetch_price_sync, wkn, isin, ticker, target_date
        )


class GettexProvider:
    """Provider for gettex / Börse München quotes (Scalable Capital standard exchange)."""

    name: str = "gettex"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def fetch_price_sync(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        """Fetches closing price for gettex / Börse München."""
        candidates = []
        if ticker:
            clean_ticker = ticker.strip()
            # If ticker has another exchange suffix like .TG or .DE, generate .MU candidate
            if "." in clean_ticker:
                base = clean_ticker.split(".")[0]
                candidates.append(f"{base}.MU")
                candidates.append(f"{base}.HM")
                candidates.append(clean_ticker)
            else:
                candidates.append(f"{clean_ticker}.MU")
                candidates.append(clean_ticker)
        
        if isin:
            candidates.append(isin.strip())

        for cand in candidates:
            try:
                yf_ticker = yf.Ticker(cand)
                hist = yf_ticker.history(period="5d")
                if hist is None or hist.empty:
                    continue

                close_col = next(
                    (c for c in hist.columns if str(c).lower() == "close"), None
                )
                if close_col is None:
                    continue

                if target_date is not None:
                    matching = hist[hist.index.date == target_date]
                    if matching.empty:
                        continue
                    row = matching.iloc[-1]
                    quote_date = target_date
                else:
                    row = hist.iloc[-1]
                    quote_date = hist.index[-1].date()

                raw_price = row[close_col]
                if raw_price is None or pd_is_na(raw_price):
                    continue

                price = Decimal(str(round(float(raw_price), 4)))
                if price <= Decimal("0"):
                    continue

                return price, quote_date, self.name
            except Exception as exc:
                logger.debug("GettexProvider candidate '%s' failed: %s", cand, exc)

        logger.warning(
            "GettexProvider: Kein Kurs für WKN=%s, ISIN=%s, Ticker=%s ermittelt.",
            wkn,
            isin,
            ticker,
        )
        return None

    async def fetch_price(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        return await asyncio.to_thread(
            self.fetch_price_sync, wkn, isin, ticker, target_date
        )


class EixProvider:
    """Provider for European Investor Exchange (EIX) / Börse Hannover / Scalable Capital."""

    name: str = "eix"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def fetch_price_sync(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        """Fetches closing price for EIX (Börse Hannover / gettex / regional exchanges)."""
        candidates = []
        if ticker:
            clean = ticker.strip()
            if "." in clean:
                base = clean.split(".")[0]
                candidates.extend([f"{base}.HA", f"{base}.HM", f"{base}.MU", f"{base}.DE", clean])
            else:
                candidates.extend([f"{clean}.HA", f"{clean}.HM", f"{clean}.MU", f"{clean}.DE", clean])

        if isin:
            candidates.append(isin.strip())

        for cand in candidates:
            try:
                yf_ticker = yf.Ticker(cand)
                hist = yf_ticker.history(period="5d")
                if hist is None or hist.empty:
                    continue

                close_col = next(
                    (c for c in hist.columns if str(c).lower() == "close"), None
                )
                if close_col is None:
                    continue

                if target_date is not None:
                    matching = hist[hist.index.date == target_date]
                    if matching.empty:
                        continue
                    row = matching.iloc[-1]
                    quote_date = target_date
                else:
                    row = hist.iloc[-1]
                    quote_date = hist.index[-1].date()

                raw_price = row[close_col]
                if raw_price is None or pd_is_na(raw_price):
                    continue

                price = Decimal(str(round(float(raw_price), 4)))
                if price <= Decimal("0"):
                    continue

                return price, quote_date, self.name
            except Exception as exc:
                logger.debug("EixProvider candidate '%s' failed: %s", cand, exc)

        logger.warning(
            "EixProvider: Kein Kurs für WKN=%s, ISIN=%s, Ticker=%s ermittelt.",
            wkn,
            isin,
            ticker,
        )
        return None

    async def fetch_price(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        return await asyncio.to_thread(
            self.fetch_price_sync, wkn, isin, ticker, target_date
        )


class XetraProvider:
    """Provider for Deutsche Börse Xetra quotes (.DE)."""

    name: str = "xetra"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def fetch_price_sync(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        candidates = []
        if ticker:
            clean = ticker.strip()
            if "." in clean:
                base = clean.split(".")[0]
                candidates.append(f"{base}.DE")
                candidates.append(clean)
            else:
                candidates.append(f"{clean}.DE")
                candidates.append(clean)

        for cand in candidates:
            try:
                yf_ticker = yf.Ticker(cand)
                hist = yf_ticker.history(period="5d")
                if hist is None or hist.empty:
                    continue

                close_col = next(
                    (c for c in hist.columns if str(c).lower() == "close"), None
                )
                if close_col is None:
                    continue

                if target_date is not None:
                    matching = hist[hist.index.date == target_date]
                    if matching.empty:
                        continue
                    row = matching.iloc[-1]
                    quote_date = target_date
                else:
                    row = hist.iloc[-1]
                    quote_date = hist.index[-1].date()

                raw_price = row[close_col]
                if raw_price is None or pd_is_na(raw_price):
                    continue

                price = Decimal(str(round(float(raw_price), 4)))
                if price <= Decimal("0"):
                    continue

                return price, quote_date, self.name
            except Exception as exc:
                logger.debug("XetraProvider candidate '%s' failed: %s", cand, exc)

        logger.warning(
            "XetraProvider: Kein Kurs für WKN=%s, ISIN=%s, Ticker=%s ermittelt.",
            wkn,
            isin,
            ticker,
        )
        return None

    async def fetch_price(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        return await asyncio.to_thread(
            self.fetch_price_sync, wkn, isin, ticker, target_date
        )


class YahooFinanceProvider:
    """Fallback provider: Queries historical closing prices via Yahoo Finance API (yfinance)."""

    name: str = "yfinance"

    def __init__(self) -> None:
        pass

    def fetch_price_sync(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        clean_ticker = (ticker or "").strip()
        if not clean_ticker:
            logger.debug("YahooFinanceProvider: Kein Ticker-Symbol übergeben.")
            return None

        try:
            yf_ticker = yf.Ticker(clean_ticker)
            hist = yf_ticker.history(period="5d")

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

            price = Decimal(str(round(float(raw_price), 4)))
            if price <= Decimal("0"):
                logger.warning(
                    "Unplausibler Schlusskurs <= 0 (%s) für Ticker '%s' am %s.",
                    price,
                    clean_ticker,
                    quote_date,
                )
                return None

            return price, quote_date, self.name

        except Exception as exc:
            logger.warning(
                "Fehler bei Yahoo-Finance-Kursabfrage für Ticker '%s': %s",
                clean_ticker,
                exc,
            )
            return None

    async def fetch_price(
        self,
        wkn: str,
        isin: str | None = None,
        ticker: str | None = None,
        target_date: datetime.date | None = None,
    ) -> tuple[Decimal, datetime.date, str] | None:
        return await asyncio.to_thread(
            self.fetch_price_sync, wkn, isin, ticker, target_date
        )


def pd_is_na(val: Any) -> bool:
    """Helper to detect pandas/numpy NaN or None values."""
    if val is None:
        return True
    try:
        import math

        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False

