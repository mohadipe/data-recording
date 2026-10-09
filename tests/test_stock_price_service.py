import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base
from data_recorder.models.wertpapiere import Etf, WknKursDatum
from data_recorder.services.stock_price_providers import (
    TradegateProvider,
    YahooFinanceProvider,
)
from data_recorder.services.stock_price_service import (
    StockPriceResult,
    StockPriceService,
)


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session for wertpapiere."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"verbrauch": None, "wertpapiere": None}},
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


def _create_mock_history_df(dates: list[datetime.date], prices: list[float]) -> pd.DataFrame:
    """Helper to create a realistic pandas DataFrame matching yfinance Ticker.history output."""
    idx = pd.to_datetime(dates)
    return pd.DataFrame(
        {
            "Open": [p * 0.99 for p in prices],
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.98 for p in prices],
            "Close": prices,
            "Volume": [1000 * (i + 1) for i in range(len(prices))],
        },
        index=idx,
    )


# ==============================================================================
# 1. TRADEGATE PROVIDER TESTS
# ==============================================================================

def test_tradegate_provider_parse_html_price():
    """Tests extracting prices with German comma decimals from Tradegate HTML."""
    provider = TradegateProvider()

    html_sample_strong = """
    <tr>
        <th>Last</th>
        <td class="longprice"><strong id="last">131,725</strong></td>
    </tr>
    """
    assert provider._parse_html_price(html_sample_strong) == Decimal("131.725")

    html_sample_thousands = """
    <tr>
        <th>Last</th>
        <td class="longprice"><strong id="last">1.250,50</strong></td>
    </tr>
    """
    assert provider._parse_html_price(html_sample_thousands) == Decimal("1250.50")

    html_sample_td_fallback = """
    <td class="longprice"><strong>18,94</strong></td>
    """
    assert provider._parse_html_price(html_sample_td_fallback) == Decimal("18.94")


def test_tradegate_provider_parse_invalid_html():
    """Tests that missing or zero price returns None."""
    provider = TradegateProvider()
    assert provider._parse_html_price("<html><body>No price here</body></html>") is None
    assert provider._parse_html_price('<strong id="last">0,00</strong>') is None
    assert provider._parse_html_price('<strong id="last">-5,00</strong>') is None


def test_tradegate_provider_fetch_price_sync_success():
    """Tests successful Tradegate HTTP fetch with mocked response."""
    provider = TradegateProvider()
    mock_html = '<tr><td class="longprice"><strong id="last">80,96</strong></td></tr>'.encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_html
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = provider.fetch_price_sync(wkn="A1T8FV", isin="IE00B8GKDB10")
        assert res is not None
        price, quote_date, source = res
        assert price == Decimal("80.96")
        assert quote_date == datetime.date.today()
        assert source == "tradegate"
        mock_urlopen.assert_called_once()


def test_tradegate_provider_fetch_price_sync_error_handling():
    """Tests that network timeouts or HTTP errors return None cleanly."""
    provider = TradegateProvider()

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        res = provider.fetch_price_sync(wkn="A1T8FV", isin="IE00B8GKDB10")
        assert res is None


# ==============================================================================
# 2. YAHOO FINANCE PROVIDER TESTS
# ==============================================================================

def test_yahoo_finance_provider_success():
    """Tests YahooFinanceProvider fetching latest closing price."""
    provider = YahooFinanceProvider()
    dates = [datetime.date(2026, 9, 25)]
    df = _create_mock_history_df(dates, [100.45])

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("yfinance.Ticker", return_value=mock_ticker):
        res = provider.fetch_price_sync(wkn="A0RPWH", ticker="EUNL.TG")
        assert res is not None
        price, quote_date, source = res
        assert price == Decimal("100.45")
        assert quote_date == datetime.date(2026, 9, 25)
        assert source == "yfinance"


def test_yahoo_finance_provider_empty_or_error():
    """Tests YahooFinanceProvider when yfinance returns empty history or throws exception."""
    provider = YahooFinanceProvider()

    # Empty df
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    with patch("yfinance.Ticker", return_value=mock_ticker):
        assert provider.fetch_price_sync(wkn="A0RPWH", ticker="INVALID.TG") is None

    # Exception
    mock_ticker.history.side_effect = RuntimeError("Rate limited")
    with patch("yfinance.Ticker", return_value=mock_ticker):
        assert provider.fetch_price_sync(wkn="A0RPWH", ticker="EUNL.TG") is None


# ==============================================================================
# 3. STOCK PRICE SERVICE & PROVIDER CHAIN TESTS
# ==============================================================================

def test_get_active_securities_returns_all_active_with_identifier(db_session: Session):
    """Verifies that all active securities with either ISIN, WKN or Ticker are returned."""
    etf1 = Etf(wkn="A0RPWH", isin="IE00B4L5Y983", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    etf2 = Etf(wkn="A1JX52", isin="IE00B3RBWM25", name="Vanguard All-World", ticker_yahoo=None, aktiv=True)
    etf3 = Etf(wkn="A2PKXG", isin=None, name="Vanguard Acc", ticker_yahoo="   ", aktiv=True)
    etf4 = Etf(wkn="LYX0CA", isin="FR0010527275", name="Lyxor DAX", ticker_yahoo="DAX.DE", aktiv=False)

    db_session.add_all([etf1, etf2, etf3, etf4])
    db_session.commit()

    service = StockPriceService()
    active_securities = service.get_active_securities(db_session)

    # etf1, etf2, etf3 are active with WKN/ISIN
    assert len(active_securities) == 3
    wkns = {s.wkn for s in active_securities}
    assert "A0RPWH" in wkns
    assert "A1JX52" in wkns
    assert "A2PKXG" in wkns
    assert "LYX0CA" not in wkns  # Inactive


def test_stock_price_service_prefers_tradegate_over_yahoo():
    """Verifies that Tradegate is tried first and Yahoo Finance is not called if Tradegate succeeds."""
    mock_tg = MagicMock(spec=TradegateProvider)
    mock_tg.name = "tradegate"
    mock_tg.fetch_price_sync.return_value = (Decimal("131.725"), datetime.date(2026, 10, 9), "tradegate")

    mock_yf = MagicMock(spec=YahooFinanceProvider)
    mock_yf.name = "yfinance"

    service = StockPriceService(providers=[mock_tg, mock_yf])
    res = service.fetch_closing_price_sync(ticker_symbol="EUNL.DE", wkn="A0RPWH", isin="IE00B4L5Y983")

    assert res is not None
    price, quote_date, source = res
    assert price == Decimal("131.725")
    assert source == "tradegate"

    mock_tg.fetch_price_sync.assert_called_once_with(
        wkn="A0RPWH", isin="IE00B4L5Y983", ticker="EUNL.DE", target_date=None
    )
    mock_yf.fetch_price_sync.assert_not_called()


def test_stock_price_service_fallback_to_yahoo_when_tradegate_fails():
    """Verifies that when Tradegate returns None, the service falls back to Yahoo Finance."""
    mock_tg = MagicMock(spec=TradegateProvider)
    mock_tg.name = "tradegate"
    mock_tg.fetch_price_sync.return_value = None

    mock_yf = MagicMock(spec=YahooFinanceProvider)
    mock_yf.name = "yfinance"
    mock_yf.fetch_price_sync.return_value = (Decimal("130.50"), datetime.date(2026, 10, 8), "yfinance")

    service = StockPriceService(providers=[mock_tg, mock_yf])
    res = service.fetch_closing_price_sync(ticker_symbol="EUNL.DE", wkn="A0RPWH", isin="IE00B4L5Y983")

    assert res is not None
    price, quote_date, source = res
    assert price == Decimal("130.50")
    assert source == "yfinance"

    mock_tg.fetch_price_sync.assert_called_once()
    mock_yf.fetch_price_sync.assert_called_once()


def test_stock_price_service_all_providers_fail():
    """Verifies that if all providers fail, None is returned without raising an unhandled exception."""
    mock_tg = MagicMock(spec=TradegateProvider)
    mock_tg.name = "tradegate"
    mock_tg.fetch_price_sync.return_value = None

    mock_yf = MagicMock(spec=YahooFinanceProvider)
    mock_yf.name = "yfinance"
    mock_yf.fetch_price_sync.return_value = None

    service = StockPriceService(providers=[mock_tg, mock_yf])
    res = service.fetch_closing_price_sync(ticker_symbol="INVALID", wkn="UNKNOWN")
    assert res is None


def test_save_stock_price_insert_and_idempotent_update(db_session: Session):
    """Tests inserting and updating price records in wkn_kurs_datum."""
    etf = Etf(wkn="A0RPWH", isin="IE00B4L5Y983", name="MSCI World", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    service = StockPriceService()

    # 1. Insert
    rec1 = service.save_stock_price(
        wkn_id=etf.id,
        datum=datetime.date(2026, 10, 9),
        kurs=Decimal("131.725"),
        session=db_session,
    )
    assert isinstance(rec1, WknKursDatum)
    assert rec1.id is not None
    assert rec1.kurs == Decimal("131.725")

    # 2. Idempotent Update
    rec2 = service.save_stock_price(
        wkn_id=etf.id,
        datum=datetime.date(2026, 10, 9),
        kurs=Decimal("132.00"),
        session=db_session,
    )
    assert rec2.id == rec1.id
    assert rec2.kurs == Decimal("132.00")

    records = db_session.execute(
        select(WknKursDatum).where(WknKursDatum.wkn_id == etf.id)
    ).scalars().all()
    assert len(records) == 1
    assert records[0].kurs == Decimal("132.00")


@pytest.mark.asyncio
async def test_poll_and_save_workflow(db_session: Session):
    """Tests poll_and_save full batch workflow with mock provider."""
    etf1 = Etf(wkn="A0RPWH", isin="IE00B4L5Y983", name="MSCI World", depot="cortal_consors", aktiv=True)
    etf2 = Etf(wkn="A1T8FV", isin="IE00B8GKDB10", name="High Dividend", depot="scalable_capital", aktiv=True)
    db_session.add_all([etf1, etf2])
    db_session.commit()

    mock_provider = MagicMock()
    mock_provider.name = "mock_provider"

    async def mock_fetch(wkn, isin=None, ticker=None, target_date=None, **kwargs):
        if wkn == "A0RPWH":
            return (Decimal("131.75"), datetime.date(2026, 10, 9), "mock_provider")
        elif wkn == "A1T8FV":
            return (Decimal("80.96"), datetime.date(2026, 10, 9), "mock_provider")
        return None

    mock_provider.fetch_price = mock_fetch

    service = StockPriceService(providers=[mock_provider])
    results = await service.poll_and_save(session=db_session)

    assert len(results) == 2
    prices = {r.etf.wkn: r.kurs for r in results}
    assert prices["A0RPWH"] == Decimal("131.75")
    assert prices["A1T8FV"] == Decimal("80.96")

    # Test filtering by depot
    results_scalable = await service.poll_and_save(session=db_session, depot="scalable_capital")
    assert len(results_scalable) == 1
    assert results_scalable[0].etf.wkn == "A1T8FV"


# ==============================================================================
# 4. GETTEX & XETRA PROVIDER TESTS & ROUTING
# ==============================================================================

def test_gettex_provider_success():
    """Tests GettexProvider candidate ticker handling and price fetch."""
    from data_recorder.services.stock_price_providers import GettexProvider

    provider = GettexProvider()
    dates = [datetime.date(2026, 10, 9)]
    df = _create_mock_history_df(dates, [131.71])

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
        res = provider.fetch_price_sync(wkn="A0RPWH", ticker="EUNL.DE", isin="IE00B4L5Y983")
        assert res is not None
        price, quote_date, source = res
        assert price == Decimal("131.71")
        assert source == "gettex"
        # Verify it tried .MU first
        mock_yf.assert_any_call("EUNL.MU")


def test_xetra_provider_success():
    """Tests XetraProvider candidate ticker handling and price fetch."""
    from data_recorder.services.stock_price_providers import XetraProvider

    provider = XetraProvider()
    dates = [datetime.date(2026, 10, 9)]
    df = _create_mock_history_df(dates, [131.64])

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
        res = provider.fetch_price_sync(wkn="A0RPWH", ticker="EUNL.TG", isin="IE00B4L5Y983")
        assert res is not None
        price, quote_date, source = res
        assert price == Decimal("131.64")
        assert source == "xetra"
        mock_yf.assert_any_call("EUNL.DE")


def test_routing_by_handelsplatz_and_depot():
    """Tests that get_providers_for_security selects the correct primary provider."""
    service = StockPriceService()

    # 1. gettex / Scalable Capital
    etf_scalable = Etf(wkn="A0RPWH", depot="scalable_capital", handelsplatz="gettex")
    providers_gettex = service.get_providers_for_security(etf_scalable)
    assert providers_gettex[0].name == "gettex"

    # 2. Xetra
    etf_xetra = Etf(wkn="A0RPWH", depot="scalable_capital", handelsplatz="xetra")
    providers_xetra = service.get_providers_for_security(etf_xetra)
    assert providers_xetra[0].name == "xetra"

    # 3. Tradegate / Consorsbank
    etf_consors = Etf(wkn="A0RPWH", depot="cortal_consors", handelsplatz="tradegate")
    providers_tg = service.get_providers_for_security(etf_consors)
    assert providers_tg[0].name == "tradegate"

