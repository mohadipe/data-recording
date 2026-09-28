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


def test_get_active_securities_filters_only_active_with_ticker(db_session: Session):
    """Verifies that only securities with aktiv=True AND non-empty ticker_yahoo are returned."""
    # 1. Active with ticker -> should be returned
    etf1 = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    # 2. Active without ticker -> should NOT be returned
    etf2 = Etf(wkn="A1JX52", name="Vanguard FTSE All-World", ticker_yahoo=None, aktiv=True)
    # 3. Active with empty ticker string -> should NOT be returned
    etf3 = Etf(wkn="A2PKXG", name="Vanguard Acc", ticker_yahoo="   ", aktiv=True)
    # 4. Inactive with ticker -> should NOT be returned
    etf4 = Etf(wkn="LYX0CA", name="Lyxor DAX", ticker_yahoo="DAX.DE", aktiv=False)

    db_session.add_all([etf1, etf2, etf3, etf4])
    db_session.commit()

    service = StockPriceService()
    active_securities = service.get_active_securities(db_session)

    assert len(active_securities) == 1
    assert active_securities[0].wkn == "A0RPWH"
    assert active_securities[0].ticker_yahoo == "EUNL.TG"


def test_fetch_closing_price_sync_latest_success():
    """Tests fetching the latest closing price when no target_date is given."""
    service = StockPriceService()
    dates = [datetime.date(2026, 9, 23), datetime.date(2026, 9, 24), datetime.date(2026, 9, 25)]
    df = _create_mock_history_df(dates, [98.20, 99.10, 100.45])

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
        res = service.fetch_closing_price_sync("EUNL.TG")
        assert res is not None
        price, quote_date = res
        assert price == Decimal("100.45")
        assert quote_date == datetime.date(2026, 9, 25)
        mock_yf.assert_called_once_with("EUNL.TG")


def test_fetch_closing_price_sync_specific_date():
    """Tests fetching the closing price for a specific historical date within the history window."""
    service = StockPriceService()
    dates = [datetime.date(2026, 9, 23), datetime.date(2026, 9, 24), datetime.date(2026, 9, 25)]
    df = _create_mock_history_df(dates, [98.20, 99.10, 100.45])

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("yfinance.Ticker", return_value=mock_ticker):
        target = datetime.date(2026, 9, 24)
        res = service.fetch_closing_price_sync("EUNL.TG", target_date=target)
        assert res is not None
        price, quote_date = res
        assert price == Decimal("99.10")
        assert quote_date == target


def test_fetch_closing_price_sync_date_not_found():
    """Tests that requesting a date not present in history returns None."""
    service = StockPriceService()
    dates = [datetime.date(2026, 9, 24), datetime.date(2026, 9, 25)]
    df = _create_mock_history_df(dates, [99.10, 100.45])

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("yfinance.Ticker", return_value=mock_ticker):
        target = datetime.date(2026, 9, 20)
        res = service.fetch_closing_price_sync("EUNL.TG", target_date=target)
        assert res is None


def test_fetch_closing_price_sync_empty_df():
    """Tests handling when yfinance returns an empty DataFrame."""
    service = StockPriceService()
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()

    with patch("yfinance.Ticker", return_value=mock_ticker):
        res = service.fetch_closing_price_sync("INVALID.TG")
        assert res is None


def test_fetch_closing_price_sync_exception_zero_crash():
    """Tests that any network or library error in yfinance is caught cleanly (zero crash policy)."""
    service = StockPriceService()
    mock_ticker = MagicMock()
    mock_ticker.history.side_effect = RuntimeError("Yahoo API Rate Limit / Network Down")

    with patch("yfinance.Ticker", return_value=mock_ticker):
        res = service.fetch_closing_price_sync("EUNL.TG")
        assert res is None


@pytest.mark.asyncio
async def test_fetch_closing_price_async_wrapper():
    """Tests the asynchronous wrapper around fetch_closing_price_sync."""
    service = StockPriceService()
    dates = [datetime.date(2026, 9, 25)]
    df = _create_mock_history_df(dates, [105.75])

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df

    with patch("yfinance.Ticker", return_value=mock_ticker):
        res = await service.fetch_closing_price("EUNL.TG")
        assert res is not None
        price, quote_date = res
        assert price == Decimal("105.75")
        assert quote_date == datetime.date(2026, 9, 25)


def test_save_stock_price_insert_new(db_session: Session):
    """Tests inserting a new price record in wkn_kurs_datum."""
    etf = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    service = StockPriceService()
    record = service.save_stock_price(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("101.50"),
        session=db_session,
    )

    assert isinstance(record, WknKursDatum)
    assert record.id is not None
    assert record.wkn_id == etf.id
    assert record.datum == datetime.date(2026, 9, 25)
    assert record.kurs == Decimal("101.50")

    # Verify directly from DB
    saved = db_session.execute(
        select(WknKursDatum).where(
            WknKursDatum.wkn_id == etf.id,
            WknKursDatum.datum == datetime.date(2026, 9, 25),
        )
    ).scalar_one()
    assert saved.kurs == Decimal("101.50")


def test_save_stock_price_idempotent_update(db_session: Session):
    """Tests that saving twice for the same wkn_id and datum updates the record rather than duplicating."""
    etf = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    service = StockPriceService()
    # First save: 101.50
    rec1 = service.save_stock_price(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("101.50"),
        session=db_session,
    )
    assert isinstance(rec1, WknKursDatum)
    assert rec1.kurs == Decimal("101.50")

    # Second save on same date: 102.80
    rec2 = service.save_stock_price(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("102.80"),
        session=db_session,
    )

    assert isinstance(rec2, WknKursDatum)
    assert rec2.id == rec1.id
    assert rec2.kurs == Decimal("102.80")

    # Count records in wkn_kurs_datum
    count = len(
        db_session.execute(
            select(WknKursDatum).where(
                WknKursDatum.wkn_id == etf.id,
                WknKursDatum.datum == datetime.date(2026, 9, 25),
            )
        )
        .scalars()
        .all()
    )
    assert count == 1


@pytest.mark.asyncio
async def test_poll_and_save_all_success(db_session: Session):
    """Tests full poll_and_save workflow updating multiple active securities."""
    etf1 = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    etf2 = Etf(wkn="A1JX52", name="Vanguard All-World", ticker_yahoo="VWRL.TG", aktiv=True)
    db_session.add_all([etf1, etf2])
    db_session.commit()

    service = StockPriceService()

    def mock_fetch_sync(ticker: str, target_date=None):
        if ticker == "EUNL.TG":
            return (Decimal("105.20"), datetime.date(2026, 9, 25))
        elif ticker == "VWRL.TG":
            return (Decimal("123.45"), datetime.date(2026, 9, 25))
        return None

    with patch.object(service, "fetch_closing_price_sync", side_effect=mock_fetch_sync):
        results = await service.poll_and_save(session=db_session)
        assert len(results) == 2
        assert all(isinstance(r, WknKursDatum) for r in results)

        prices = {r.wkn_id: r.kurs for r in results}
        assert prices[etf1.id] == Decimal("105.20")
        assert prices[etf2.id] == Decimal("123.45")


@pytest.mark.asyncio
async def test_poll_and_save_partial_failure_continues(db_session: Session):
    """Tests that if one security fails to fetch, others are still processed and saved successfully."""
    etf1 = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    etf2 = Etf(wkn="FAIL99", name="Broken Security", ticker_yahoo="BROKEN.TG", aktiv=True)
    db_session.add_all([etf1, etf2])
    db_session.commit()

    service = StockPriceService()

    def mock_fetch_sync(ticker: str, target_date=None):
        if ticker == "EUNL.TG":
            return (Decimal("105.20"), datetime.date(2026, 9, 25))
        return None

    with patch.object(service, "fetch_closing_price_sync", side_effect=mock_fetch_sync):
        results = await service.poll_and_save(session=db_session)
        assert len(results) == 1
        assert isinstance(results[0], WknKursDatum)
        assert results[0].wkn_id == etf1.id
        assert results[0].kurs == Decimal("105.20")


@pytest.mark.asyncio
async def test_poll_and_save_no_active_securities(db_session: Session):
    """Tests poll_and_save returns empty list when no active securities with ticker exist."""
    etf_inactive = Etf(wkn="INACT1", name="Inactive", ticker_yahoo="INA.TG", aktiv=False)
    db_session.add(etf_inactive)
    db_session.commit()

    service = StockPriceService()
    results = await service.poll_and_save(session=db_session)
    assert results == []


@pytest.mark.asyncio
async def test_poll_and_save_default_session_generator(db_session: Session):
    """Tests poll_and_save using get_db_session('wertpapiere') generator when session=None."""
    etf = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    service = StockPriceService()

    def fake_get_db_session(schema: str = "wertpapiere"):
        yield db_session

    with patch(
        "data_recorder.services.stock_price_service.get_db_session", side_effect=fake_get_db_session
    ):
        with patch.object(
            service,
            "fetch_closing_price_sync",
            return_value=(Decimal("99.99"), datetime.date(2026, 9, 25)),
        ):
            results = await service.poll_and_save(session=None)
            assert len(results) == 1
            assert isinstance(results[0], WknKursDatum)
            assert results[0].kurs == Decimal("99.99")


@pytest.mark.asyncio
async def test_poll_and_save_empty_generator():
    """Tests poll_and_save when get_db_session yields nothing."""
    service = StockPriceService()

    def empty_get_db_session(schema: str = "wertpapiere"):
        if False:
            yield None

    with patch(
        "data_recorder.services.stock_price_service.get_db_session",
        side_effect=empty_get_db_session,
    ):
        results = await service.poll_and_save(session=None)
        assert results == []


def test_fetch_closing_price_empty_ticker_returns_none():
    """Tests that empty or whitespace ticker symbols return None immediately."""
    service = StockPriceService()
    assert service.fetch_closing_price_sync("") is None
    assert service.fetch_closing_price_sync("   ") is None


def test_fetch_closing_price_no_close_column():
    """Tests handling when DataFrame is returned without a 'Close' column."""
    service = StockPriceService()
    mock_ticker = MagicMock()
    idx = pd.to_datetime([datetime.date(2026, 9, 25)])
    mock_ticker.history.return_value = pd.DataFrame({"Open": [100.0], "Volume": [100]}, index=idx)

    with patch("yfinance.Ticker", return_value=mock_ticker):
        assert service.fetch_closing_price_sync("EUNL.TG") is None


def test_fetch_closing_price_nan_price():
    """Tests handling when close price is NaN or None."""
    service = StockPriceService()
    mock_ticker = MagicMock()
    idx = pd.to_datetime([datetime.date(2026, 9, 25)])
    mock_ticker.history.return_value = pd.DataFrame({"Close": [float("nan")]}, index=idx)

    with patch("yfinance.Ticker", return_value=mock_ticker):
        assert service.fetch_closing_price_sync("EUNL.TG") is None


def test_fetch_closing_price_negative_or_zero_price():
    """Tests handling when close price is <= 0."""
    service = StockPriceService()
    mock_ticker = MagicMock()
    idx = pd.to_datetime([datetime.date(2026, 9, 25)])
    mock_ticker.history.return_value = pd.DataFrame({"Close": [0.0]}, index=idx)

    with patch("yfinance.Ticker", return_value=mock_ticker):
        assert service.fetch_closing_price_sync("EUNL.TG") is None


@pytest.mark.asyncio
async def test_process_securities_handles_unexpected_exception(db_session: Session):
    """Tests that an unexpected exception during save rolls back and does not abort remaining."""
    etf = Etf(wkn="ERR99", name="Error Security", ticker_yahoo="ERR.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    service = StockPriceService()
    with patch.object(
        service,
        "fetch_closing_price_sync",
        return_value=(Decimal("50.00"), datetime.date(2026, 9, 25)),
    ):
        with patch.object(service, "save_stock_price", side_effect=RuntimeError("DB Disk Full")):
            results = await service.poll_and_save(session=db_session)
            assert results == []


def test_pd_is_na_helper():
    """Tests pd_is_na with None, NaN, valid number, and unconvertible types."""
    from data_recorder.services.stock_price_service import pd_is_na

    assert pd_is_na(None) is True
    assert pd_is_na(float("nan")) is True
    assert pd_is_na(100.5) is False
    assert pd_is_na("not-a-number") is False


def test_stock_price_result_dataclass():
    """Tests StockPriceResult dataclass with kurs and backwards-compatible wert alias."""
    # Instantiation with kurs
    res1 = StockPriceResult(
        wkn_id=1,
        wkn="A0RPWH",
        ticker="EUNL.TG",
        datum=datetime.date(2026, 9, 25),
        kurs=Decimal("105.50"),
    )
    assert res1.kurs == Decimal("105.50")
    assert res1.wert == Decimal("105.50")

    # Instantiation with wert keyword argument
    res2 = StockPriceResult(
        wkn_id=2,
        wkn="A1JX52",
        ticker="VWRL.TG",
        datum=datetime.date(2026, 9, 25),
        wert=Decimal("123.45"),
    )
    assert res2.kurs == Decimal("123.45")
    assert res2.wert == Decimal("123.45")


def test_save_stock_price_wert_kwarg_backward_compatibility(db_session: Session):
    """Tests that calling save_stock_price with wert keyword argument saves to wkn_kurs_datum."""
    etf = Etf(wkn="A0RPWH", name="MSCI World", ticker_yahoo="EUNL.TG", aktiv=True)
    db_session.add(etf)
    db_session.commit()

    service = StockPriceService()
    record = service.save_stock_price(
        wkn_id=etf.id,
        datum=datetime.date(2026, 9, 25),
        wert=Decimal("99.50"),
        session=db_session,
    )
    assert isinstance(record, WknKursDatum)
    assert record.kurs == Decimal("99.50")

