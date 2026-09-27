import asyncio
from dataclasses import dataclass, field
import datetime
from decimal import Decimal, InvalidOperation
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_recorder.core.config import get_settings
from data_recorder.core.database import get_db_session
from data_recorder.models.verbrauch import WaermepumpeStundenwert

logger = logging.getLogger(__name__)


@dataclass
class EbusMetrics:
    """Extracted metrics from ebusd aroTHERM response."""

    zeitstempel: datetime.datetime
    aussentemperatur: Decimal | None = None
    vorlauf_temp: Decimal | None = None
    ruecklauf_temp: Decimal | None = None
    ertrag_gesamt_kwh: Decimal | None = None
    strom_gesamt_kwh: Decimal | None = None
    ertrag_heizen_kwh: Decimal | None = None
    strom_heizen_kwh: Decimal | None = None
    ertrag_warmwasser_kwh: Decimal | None = None
    strom_warmwasser_kwh: Decimal | None = None
    cop_aktuell: Decimal | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


def calculate_cop(
    yield_heating: Decimal | None,
    energy_heating: Decimal | None,
    yield_hot_water: Decimal | None,
    energy_hot_water: Decimal | None,
    yield_total: Decimal | None = None,
    energy_total: Decimal | None = None,
) -> Decimal | None:
    """Calculates Coefficient of Performance (COP / Arbeitszahl).

    Primary formula:
        COP = (YieldHeating + YieldHotWater) / (EnergyInputHeating + EnergyInputHotWater)
    Fallback formula (if heating/hotwater separate counters not available or sum is zero):
        COP = YieldTotal / EnergyInputTotal
    """
    total_yield = Decimal(0)
    has_yield = False
    if yield_heating is not None:
        total_yield += yield_heating
        has_yield = True
    if yield_hot_water is not None:
        total_yield += yield_hot_water
        has_yield = True

    total_energy = Decimal(0)
    has_energy = False
    if energy_heating is not None:
        total_energy += energy_heating
        has_energy = True
    if energy_hot_water is not None:
        total_energy += energy_hot_water
        has_energy = True

    if has_yield and has_energy and total_energy > Decimal(0):
        cop = total_yield / total_energy
        return Decimal(str(round(cop, 2)))

    # Fallback to total counters
    if (
        yield_total is not None
        and energy_total is not None
        and energy_total > Decimal(0)
    ):
        cop = yield_total / energy_total
        return Decimal(str(round(cop, 2)))

    return None


def _to_decimal(val: Any) -> Decimal | None:
    """Converts a value to Decimal safely."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str or val_str in ("-", "null", "none", "no data stored"):
            return None
        # Split on semicolon if multi-value string
        if ";" in val_str:
            val_str = val_str.split(";")[0]
        try:
            return Decimal(val_str)
        except InvalidOperation:
            return None
    return None


def _extract_numeric_from_node(node: Any) -> Decimal | None:
    """Extracts a numeric Decimal from an ebusd JSON node.

    Handles structures like:
      - 32.5
      - "32.5"
      - {"value": 32.5}
      - {"values": {"temp": {"value": 32.5}}}
      - {"values": {"0": {"value": 32.5}}}
      - {"values": {"value": 32.5}}
      - {"values": [32.5]}
    """
    if node is None:
        return None

    if isinstance(node, (int, float, str)):
        return _to_decimal(node)

    if isinstance(node, dict):
        # Direct value key
        if "value" in node:
            return _extract_numeric_from_node(node["value"])

        if "values" in node:
            values_obj = node["values"]
            if isinstance(values_obj, (int, float, str)):
                return _to_decimal(values_obj)
            if isinstance(values_obj, list) and values_obj:
                return _extract_numeric_from_node(values_obj[0])
            if isinstance(values_obj, dict):
                # Search for preferred sub-keys
                for preferred in ("value", "val", "temp", "energy", "0"):
                    if preferred in values_obj:
                        return _extract_numeric_from_node(values_obj[preferred])
                # Otherwise take first value
                for v in values_obj.values():
                    extracted = _extract_numeric_from_node(v)
                    if extracted is not None:
                        return extracted

        # If dict has no "values", inspect sub-nodes
        for preferred in ("value", "val", "temp", "energy", "0"):
            if preferred in node:
                return _extract_numeric_from_node(node[preferred])
        for v in node.values():
            extracted = _extract_numeric_from_node(v)
            if extracted is not None:
                return extracted

    if isinstance(node, list) and node:
        return _extract_numeric_from_node(node[0])

    return None


class EbusService:
    """Service to interact with the ebusd daemon and extract aroTHERM heat pump metrics."""

    def __init__(self, ebusd_url: str | None = None) -> None:
        self.ebusd_url = ebusd_url or get_settings().EBUSD_URL

    def _find_message_node(
        self, data: dict[str, Any], aliases: list[str]
    ) -> Any | None:
        """Finds a message node matching any alias (case-insensitive) across all circuits."""
        lower_aliases = {alias.lower() for alias in aliases}

        # Check top-level keys
        for key, value in data.items():
            if key.lower() in lower_aliases:
                return value

        # Check circuits (e.g., hmu, ctlv3, broadcast, vr_71)
        for circuit_name, circuit_data in data.items():
            if isinstance(circuit_data, dict):
                # Check circuit/messages
                messages = circuit_data.get("messages", circuit_data)
                if isinstance(messages, dict):
                    for msg_name, msg_node in messages.items():
                        if msg_name.lower() in lower_aliases:
                            return msg_node

        return None

    def extract_metrics(
        self, data: dict[str, Any], zeitstempel: datetime.datetime | None = None
    ) -> EbusMetrics:
        """Extracts and calculates all relevant metrics from ebusd JSON payload."""
        if zeitstempel is None:
            zeitstempel = datetime.datetime.now().replace(
                minute=0, second=0, microsecond=0
            )

        # 1. Total energy & yield
        energy_total_node = self._find_message_node(
            data,
            [
                "EnergyInputTotal",
                "TotalEnergyUsage",
                "PrEnergySum",
                "ConsumedElectricalEnergyTotal",
            ],
        )
        yield_total_node = self._find_message_node(
            data, ["YieldTotal", "SolarYieldTotal", "TotalYield"]
        )

        # 2. Heating breakdown
        yield_heating_node = self._find_message_node(
            data, ["YieldHeating", "YieldHc", "HeatGeneratedHeating"]
        )
        energy_heating_node = self._find_message_node(
            data,
            [
                "EnergyInputHeating",
                "EnergyInputHc",
                "ConsumedElectricalEnergyHeating",
            ],
        )

        # 3. Hot water breakdown
        yield_hw_node = self._find_message_node(
            data, ["YieldHotWater", "YieldHwc", "HeatGeneratedDomesticHotWater"]
        )
        energy_hw_node = self._find_message_node(
            data,
            [
                "EnergyInputHotWater",
                "EnergyInputHwc",
                "ConsumedElectricalEnergyDomesticHotWater",
            ],
        )

        # 4. Temperatures
        outdoor_temp_node = self._find_message_node(
            data,
            [
                "OutdoorTemp",
                "Outsidetemp",
                "DisplayedOutsideTemp",
                "OutsideTempAvg",
                "TestOutdoorTemp",
            ],
        )
        flow_temp_node = self._find_message_node(
            data, ["FlowTemp", "Hc1FlowTemp", "SystemFlowTemp"]
        )
        return_temp_node = self._find_message_node(
            data, ["ReturnTemp", "Hc1ReturnTemp", "ReturnTemperature"]
        )

        # Convert to Decimals
        ertrag_gesamt = _extract_numeric_from_node(yield_total_node)
        strom_gesamt = _extract_numeric_from_node(energy_total_node)
        ertrag_heizen = _extract_numeric_from_node(yield_heating_node)
        strom_heizen = _extract_numeric_from_node(energy_heating_node)
        ertrag_ww = _extract_numeric_from_node(yield_hw_node)
        strom_ww = _extract_numeric_from_node(energy_hw_node)
        aussentemperatur = _extract_numeric_from_node(outdoor_temp_node)
        vorlauf_temp = _extract_numeric_from_node(flow_temp_node)
        ruecklauf_temp = _extract_numeric_from_node(return_temp_node)

        # Fallback for Vorlauf / Rücklauf from Status01 message if available
        if vorlauf_temp is None or ruecklauf_temp is None:
            status01_node = self._find_message_node(data, ["Status01"])
            if status01_node and isinstance(status01_node, dict):
                values = status01_node.get("values", status01_node)
                if isinstance(values, dict):
                    if vorlauf_temp is None:
                        vorlauf_temp = _to_decimal(
                            values.get("temp", {}).get("value")
                            if isinstance(values.get("temp"), dict)
                            else values.get("temp")
                        )
                    if ruecklauf_temp is None:
                        ruecklauf_temp = _to_decimal(
                            values.get("temp_1", {}).get("value")
                            if isinstance(values.get("temp_1"), dict)
                            else values.get("temp_1")
                        )

        # Calculate COP
        cop = calculate_cop(
            yield_heating=ertrag_heizen,
            energy_heating=strom_heizen,
            yield_hot_water=ertrag_ww,
            energy_hot_water=strom_ww,
            yield_total=ertrag_gesamt,
            energy_total=strom_gesamt,
        )

        return EbusMetrics(
            zeitstempel=zeitstempel,
            aussentemperatur=aussentemperatur,
            vorlauf_temp=vorlauf_temp,
            ruecklauf_temp=ruecklauf_temp,
            ertrag_gesamt_kwh=ertrag_gesamt,
            strom_gesamt_kwh=strom_gesamt,
            ertrag_heizen_kwh=ertrag_heizen,
            strom_heizen_kwh=strom_heizen,
            ertrag_warmwasser_kwh=ertrag_ww,
            strom_warmwasser_kwh=strom_ww,
            cop_aktuell=cop,
            raw_data=data,
        )

    async def fetch_ebusd_data(
        self,
        url: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> dict[str, Any] | None:
        """Fetches /data from ebusd via HTTP with retry on transient bus collisions/timeouts."""
        target_url = url or self.ebusd_url
        timeout = httpx.Timeout(10.0, connect=5.0)

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(target_url)
                    if response.is_error:
                        response.raise_for_status()
                    return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
                if attempt < max_retries:
                    logger.warning(
                        "eBUS-Abfrage fehlgeschlagen (Versuch %d/%d): %s. Wiederhole in %.1fs...",
                        attempt,
                        max_retries,
                        exc,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.warning(
                        "eBUS nicht erreichbar nach %d Versuchen (%s): %s. Job wird beim nächsten Zyklus wiederholt.",
                        max_retries,
                        target_url,
                        exc,
                    )
                    return None

        return None

    def save_metrics_to_db(
        self, metrics: EbusMetrics, session: Session
    ) -> WaermepumpeStundenwert:
        """Saves or updates metrics in waermepumpe_stundenwert table idempotently."""
        stmt = select(WaermepumpeStundenwert).where(
            WaermepumpeStundenwert.zeitstempel == metrics.zeitstempel
        )
        record = session.execute(stmt).scalar_one_or_none()

        if record is None:
            record = WaermepumpeStundenwert(
                zeitstempel=metrics.zeitstempel,
                aussentemperatur=metrics.aussentemperatur,
                vorlauf_temp=metrics.vorlauf_temp,
                ruecklauf_temp=metrics.ruecklauf_temp,
                ertrag_gesamt_kwh=metrics.ertrag_gesamt_kwh,
                strom_gesamt_kwh=metrics.strom_gesamt_kwh,
                ertrag_heizen_kwh=metrics.ertrag_heizen_kwh,
                strom_heizen_kwh=metrics.strom_heizen_kwh,
                ertrag_warmwasser_kwh=metrics.ertrag_warmwasser_kwh,
                strom_warmwasser_kwh=metrics.strom_warmwasser_kwh,
                cop_aktuell=metrics.cop_aktuell,
            )
            session.add(record)
        else:
            # Update existing record
            if metrics.aussentemperatur is not None:
                record.aussentemperatur = metrics.aussentemperatur
            if metrics.vorlauf_temp is not None:
                record.vorlauf_temp = metrics.vorlauf_temp
            if metrics.ruecklauf_temp is not None:
                record.ruecklauf_temp = metrics.ruecklauf_temp
            if metrics.ertrag_gesamt_kwh is not None:
                record.ertrag_gesamt_kwh = metrics.ertrag_gesamt_kwh
            if metrics.strom_gesamt_kwh is not None:
                record.strom_gesamt_kwh = metrics.strom_gesamt_kwh
            if metrics.ertrag_heizen_kwh is not None:
                record.ertrag_heizen_kwh = metrics.ertrag_heizen_kwh
            if metrics.strom_heizen_kwh is not None:
                record.strom_heizen_kwh = metrics.strom_heizen_kwh
            if metrics.ertrag_warmwasser_kwh is not None:
                record.ertrag_warmwasser_kwh = metrics.ertrag_warmwasser_kwh
            if metrics.strom_warmwasser_kwh is not None:
                record.strom_warmwasser_kwh = metrics.strom_warmwasser_kwh
            if metrics.cop_aktuell is not None:
                record.cop_aktuell = metrics.cop_aktuell

        session.commit()
        session.refresh(record)
        return record

    async def poll_and_save(
        self,
        session: Session | None = None,
        timestamp: datetime.datetime | None = None,
        url: str | None = None,
    ) -> WaermepumpeStundenwert | None:
        """Polls ebusd, extracts metrics and persists them to the database."""
        target_dt = (timestamp or datetime.datetime.now()).replace(
            minute=0, second=0, microsecond=0
        )
        data = await self.fetch_ebusd_data(url=url)
        if data is None:
            return None

        metrics = self.extract_metrics(data, zeitstempel=target_dt)

        if session is not None:
            return self.save_metrics_to_db(metrics, session)

        # Use new database session
        for db in get_db_session("verbrauch"):
            return self.save_metrics_to_db(metrics, db)

        return None
