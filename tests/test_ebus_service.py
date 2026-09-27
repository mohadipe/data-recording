import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base
from data_recorder.models.verbrauch import WaermepumpeStundenwert
from data_recorder.services.ebus_service import (
    EbusMetrics,
    EbusService,
    calculate_cop,
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


SAMPLE_AROTHERM_PAYLOAD = {
    "global": {
        "version": "ebusd 26.1.26.1",
        "running": True,
        "signal": True,
    },
    "broadcast": {
        "Outsidetemp": {
            "name": "Outsidetemp",
            "values": {
                "temp": {"value": 14.50}
            },
        }
    },
    "hmu": {
        "FlowTemp": {
            "name": "FlowTemp",
            "values": {
                "temp": {"value": 32.80}
            },
        },
        "ReturnTemp": {
            "name": "ReturnTemp",
            "values": {
                "temp": {"value": 28.40}
            },
        },
        "YieldHeating": {
            "name": "YieldHeating",
            "values": {
                "energy": {"value": 15420.50}
            },
        },
        "EnergyInputHeating": {
            "name": "EnergyInputHeating",
            "values": {
                "energy": {"value": 3855.125}
            },
        },
        "YieldHotWater": {
            "name": "YieldHotWater",
            "values": {
                "energy": {"value": 2840.00}
            },
        },
        "EnergyInputHotWater": {
            "name": "EnergyInputHotWater",
            "values": {
                "energy": {"value": 946.67}
            },
        },
        "YieldTotal": {
            "name": "YieldTotal",
            "values": {
                "energy": {"value": 18260.50}
            },
        },
        "EnergyInputTotal": {
            "name": "EnergyInputTotal",
            "values": {
                "energy": {"value": 4801.795}
            },
        },
    },
}


def test_cop_calculation_heating_and_hotwater():
    """Tests COP calculation using (YieldHeating + YieldHotWater) / (EnergyInputHeating + EnergyInputHotWater)."""
    cop = calculate_cop(
        yield_heating=Decimal("15420.50"),
        energy_heating=Decimal("3855.125"),
        yield_hot_water=Decimal("2840.00"),
        energy_hot_water=Decimal("946.67"),
    )
    # Total yield = 18260.50, Total input = 4801.795 -> 18260.50 / 4801.795 = 3.8028... -> 3.80
    assert cop == Decimal("3.80")


def test_cop_calculation_total_fallback():
    """Tests fallback to YieldTotal / EnergyInputTotal if heating/hw inputs are missing or 0."""
    cop = calculate_cop(
        yield_heating=Decimal("0"),
        energy_heating=Decimal("0"),
        yield_hot_water=Decimal("0"),
        energy_hot_water=Decimal("0"),
        yield_total=Decimal("10000.00"),
        energy_total=Decimal("2500.00"),
    )
    assert cop == Decimal("4.00")


def test_cop_calculation_zero_division():
    """Tests that zero energy input returns None without crashing."""
    assert calculate_cop(None, None, None, None) is None
    assert calculate_cop(Decimal("100"), Decimal("0"), None, None) is None
    assert calculate_cop(Decimal("100"), None, Decimal("50"), Decimal("0")) is None


def test_extract_metrics_arotherm_payload():
    """Tests extracting metrics from full aroTHERM VWL 105/6 payload."""
    service = EbusService()
    target_dt = datetime.datetime(2026, 9, 27, 11, 0, 0)
    metrics = service.extract_metrics(SAMPLE_AROTHERM_PAYLOAD, zeitstempel=target_dt)

    assert metrics.zeitstempel == target_dt
    assert metrics.aussentemperatur == Decimal("14.50")
    assert metrics.vorlauf_temp == Decimal("32.80")
    assert metrics.ruecklauf_temp == Decimal("28.40")
    assert metrics.ertrag_heizen_kwh == Decimal("15420.50")
    assert metrics.strom_heizen_kwh == Decimal("3855.125")
    assert metrics.ertrag_warmwasser_kwh == Decimal("2840.00")
    assert metrics.strom_warmwasser_kwh == Decimal("946.67")
    assert metrics.ertrag_gesamt_kwh == Decimal("18260.50")
    assert metrics.strom_gesamt_kwh == Decimal("4801.795")
    assert metrics.cop_aktuell == Decimal("3.80")


def test_extract_metrics_with_status01_fallback():
    """Tests extracting FlowTemp and ReturnTemp from HMU Status01 when standalone messages are missing."""
    service = EbusService()
    payload = {
        "hmu": {
            "Status01": {
                "values": {
                    "temp": {"value": 35.5},
                    "temp_1": {"value": 29.0},
                }
            },
            "YieldTotal": {"values": {"value": 5000.0}},
            "EnergyInputTotal": {"values": {"value": 1250.0}},
        },
        "broadcast": {
            "Outsidetemp": {"values": {"value": 11.2}},
        },
    }
    metrics = service.extract_metrics(payload)
    assert metrics.vorlauf_temp == Decimal("35.5")
    assert metrics.ruecklauf_temp == Decimal("29.0")
    assert metrics.aussentemperatur == Decimal("11.2")
    assert metrics.ertrag_gesamt_kwh == Decimal("5000.0")
    assert metrics.strom_gesamt_kwh == Decimal("1250.0")
    assert metrics.cop_aktuell == Decimal("4.00")


@pytest.mark.asyncio
async def test_fetch_ebusd_data_success():
    """Tests successful HTTP GET from ebusd."""
    service = EbusService()
    url = "http://192.168.2.125:58888/data"
    mock_response = httpx.Response(
        200,
        json=SAMPLE_AROTHERM_PAYLOAD,
        request=httpx.Request("GET", url),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        data = await service.fetch_ebusd_data(url)
        assert data == SAMPLE_AROTHERM_PAYLOAD
        assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_fetch_ebusd_data_retry_and_zero_crash():
    """Tests retry mechanism on bus collision / timeout and graceful failure handling."""
    service = EbusService()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectTimeout("Connection timed out")
        data = await service.fetch_ebusd_data("http://192.168.2.125:58888/data", max_retries=2, retry_delay=0.01)
        assert data is None
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_ebusd_data_retry_eventual_success():
    """Tests that a transient bus collision succeeds on subsequent retry."""
    service = EbusService()
    url = "http://192.168.2.125:58888/data"
    success_response = httpx.Response(
        200,
        json=SAMPLE_AROTHERM_PAYLOAD,
        request=httpx.Request("GET", url),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [httpx.ReadTimeout("Bus busy"), success_response]
        data = await service.fetch_ebusd_data(url, max_retries=3, retry_delay=0.01)
        assert data == SAMPLE_AROTHERM_PAYLOAD
        assert mock_get.call_count == 2


def test_save_metrics_to_db_and_idempotency(db_session: Session):
    """Tests saving metrics to database and strictly idempotent hourly updates."""
    service = EbusService()
    dt = datetime.datetime(2026, 9, 27, 11, 0, 0)
    metrics1 = EbusMetrics(
        zeitstempel=dt,
        aussentemperatur=Decimal("14.50"),
        vorlauf_temp=Decimal("32.80"),
        ruecklauf_temp=Decimal("28.40"),
        ertrag_gesamt_kwh=Decimal("18260.50"),
        strom_gesamt_kwh=Decimal("4801.80"),
        ertrag_heizen_kwh=Decimal("15420.50"),
        strom_heizen_kwh=Decimal("3855.10"),
        ertrag_warmwasser_kwh=Decimal("2840.00"),
        strom_warmwasser_kwh=Decimal("946.70"),
        cop_aktuell=Decimal("3.80"),
    )

    # First insert
    saved1 = service.save_metrics_to_db(metrics1, db_session)
    assert saved1.id is not None
    assert saved1.cop_aktuell == Decimal("3.80")

    # Verify 1 record in DB
    records = db_session.execute(select(WaermepumpeStundenwert)).scalars().all()
    assert len(records) == 1

    # Second call for the exact same hour with updated COP (idempotency check)
    metrics2 = EbusMetrics(
        zeitstempel=dt,
        aussentemperatur=Decimal("15.00"),
        vorlauf_temp=Decimal("33.00"),
        ruecklauf_temp=Decimal("28.50"),
        ertrag_gesamt_kwh=Decimal("18270.00"),
        strom_gesamt_kwh=Decimal("4805.00"),
        ertrag_heizen_kwh=Decimal("15430.00"),
        strom_heizen_kwh=Decimal("3858.00"),
        ertrag_warmwasser_kwh=Decimal("2840.00"),
        strom_warmwasser_kwh=Decimal("947.00"),
        cop_aktuell=Decimal("3.81"),
    )
    saved2 = service.save_metrics_to_db(metrics2, db_session)
    assert saved2.id == saved1.id
    assert saved2.cop_aktuell == Decimal("3.81")
    assert saved2.aussentemperatur == Decimal("15.00")

    # Still only 1 record in DB!
    records_after = db_session.execute(select(WaermepumpeStundenwert)).scalars().all()
    assert len(records_after) == 1


@pytest.mark.asyncio
async def test_poll_and_save_success(db_session: Session):
    """Tests full poll_and_save workflow with mocked ebusd and SQLite session."""
    service = EbusService()
    dt = datetime.datetime(2026, 9, 27, 12, 0, 0)

    with patch.object(service, "fetch_ebusd_data", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = SAMPLE_AROTHERM_PAYLOAD
        saved = await service.poll_and_save(session=db_session, timestamp=dt)
        assert saved is not None
        assert saved.zeitstempel == dt
        assert saved.ertrag_gesamt_kwh == Decimal("18260.50")
        assert saved.cop_aktuell == Decimal("3.80")


@pytest.mark.asyncio
async def test_poll_and_save_failure_handled(db_session: Session):
    """Tests poll_and_save returns None without crashing when ebusd is unreachable."""
    service = EbusService()

    with patch.object(service, "fetch_ebusd_data", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None
        saved = await service.poll_and_save(session=db_session)
        assert saved is None


@pytest.mark.asyncio
async def test_poll_and_save_default_session(db_session: Session):
    """Tests poll_and_save creates and uses get_db_session when session argument is None."""
    service = EbusService()
    dt = datetime.datetime(2026, 9, 27, 13, 0, 0)

    def mock_get_session(schema: str = "verbrauch"):
        yield db_session

    with patch.object(service, "fetch_ebusd_data", new_callable=AsyncMock) as mock_fetch, \
         patch("data_recorder.services.ebus_service.get_db_session", side_effect=mock_get_session):
        mock_fetch.return_value = SAMPLE_AROTHERM_PAYLOAD
        saved = await service.poll_and_save(session=None, timestamp=dt)
        assert saved is not None
        assert saved.zeitstempel == dt
        assert saved.cop_aktuell == Decimal("3.80")
