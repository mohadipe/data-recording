import datetime
from decimal import Decimal
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_recorder.core.database import get_db_session
from data_recorder.models.verbrauch import WaermepumpeStundenwert
from data_recorder.services.ebus_service import EbusService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ebus", tags=["eBUS"])


class WaermepumpeDataResponse(BaseModel):
    """Schema for heat pump hourly metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    zeitstempel: datetime.datetime
    aussentemperatur: float | None = None
    vorlauf_temp: float | None = None
    ruecklauf_temp: float | None = None
    ertrag_gesamt_kwh: float | None = None
    strom_gesamt_kwh: float | None = None
    ertrag_heizen_kwh: float | None = None
    strom_heizen_kwh: float | None = None
    ertrag_warmwasser_kwh: float | None = None
    strom_warmwasser_kwh: float | None = None
    cop_aktuell: float | None = None


class PollNowResponse(BaseModel):
    """Schema for poll-now trigger response."""

    status: str
    message: str
    data: WaermepumpeDataResponse | None = None


def _to_float(val: Decimal | float | None) -> float | None:
    return float(val) if val is not None else None


def _serialize_record(record: WaermepumpeStundenwert) -> WaermepumpeDataResponse:
    return WaermepumpeDataResponse(
        id=record.id,
        zeitstempel=record.zeitstempel,
        aussentemperatur=_to_float(record.aussentemperatur),
        vorlauf_temp=_to_float(record.vorlauf_temp),
        ruecklauf_temp=_to_float(record.ruecklauf_temp),
        ertrag_gesamt_kwh=_to_float(record.ertrag_gesamt_kwh),
        strom_gesamt_kwh=_to_float(record.strom_gesamt_kwh),
        ertrag_heizen_kwh=_to_float(record.ertrag_heizen_kwh),
        strom_heizen_kwh=_to_float(record.strom_heizen_kwh),
        ertrag_warmwasser_kwh=_to_float(record.ertrag_warmwasser_kwh),
        strom_warmwasser_kwh=_to_float(record.strom_warmwasser_kwh),
        cop_aktuell=_to_float(record.cop_aktuell),
    )


@router.post(
    "/poll-now",
    response_model=PollNowResponse,
    summary="Manueller eBUS aroTHERM Trigger",
    description="Fragt den ebusd sofort ab, extrahiert die aroTHERM-Messwerte und speichert sie stündlich idempotent in MySQL.",
)
async def poll_now() -> Any:
    """Manuell ausgelöstes Polling der eBUS aroTHERM-Messwerte."""
    service = EbusService()
    record = await service.poll_and_save()

    if record is None:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "status": "error",
                "message": "eBUS-Daemon nicht erreichbar oder keine Daten erhalten",
                "data": None,
            },
        )

    return PollNowResponse(
        status="ok",
        message="eBUS-Daten erfolgreich abgefragt und gespeichert.",
        data=_serialize_record(record),
    )


@router.get(
    "/latest",
    response_model=WaermepumpeDataResponse,
    summary="Letzter erfasster eBUS-Messwert",
    description="Liefert den aktuellsten stündlichen Wärmepumpen-Datensatz aus der Datenbank.",
)
async def get_latest(
    session: Session = Depends(get_db_session),
) -> Any:
    """Gibt den neuesten stündlichen Datensatz zurück."""
    stmt = (
        select(WaermepumpeStundenwert)
        .order_by(WaermepumpeStundenwert.zeitstempel.desc())
        .limit(1)
    )
    record = session.execute(stmt).scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keine eBUS-Messwerte in der Datenbank vorhanden.",
        )

    return _serialize_record(record)
