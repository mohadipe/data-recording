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
from data_recorder.models.verbrauch import HeizoelPreis
from data_recorder.services.oil_price_service import OilPriceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oil-price", tags=["Heizölpreis"])


class OilPriceResponse(BaseModel):
    """Schema for regional heating oil price record."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    datum: datetime.date
    plz: str
    menge_liter: int
    preis_pro_liter: float


class PollNowOilResponse(BaseModel):
    """Schema for poll-now trigger response."""

    status: str
    message: str
    data: OilPriceResponse | None = None


def _serialize_record(record: HeizoelPreis) -> OilPriceResponse:
    return OilPriceResponse(
        id=record.id,
        datum=record.datum,
        plz=record.plz,
        menge_liter=record.menge_liter,
        preis_pro_liter=float(record.preis_pro_liter),
    )


@router.post(
    "/poll-now",
    response_model=PollNowOilResponse,
    summary="Manueller Heizölpreis Trigger",
    description="Fragt den Heizölpreis sofort ab und speichert ihn idempotent in der Datenbank.",
)
async def poll_now() -> Any:
    """Manuell ausgelöstes Polling des aktuellen regionalen Heizölpreises."""
    service = OilPriceService()
    record = await service.poll_and_save()

    if record is None:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "status": "error",
                "message": "Heizölpreis-Anbieter nicht erreichbar oder keine Daten erhalten",
                "data": None,
            },
        )

    return PollNowOilResponse(
        status="ok",
        message="Heizölpreis erfolgreich abgefragt und gespeichert.",
        data=_serialize_record(record),
    )


@router.get(
    "/latest",
    response_model=OilPriceResponse,
    summary="Letzter erfasster Heizölpreis",
    description="Liefert die aktuellste Notierung des regionalen Heizölpreises aus der Datenbank.",
)
async def get_latest(
    session: Session = Depends(get_db_session),
) -> Any:
    """Gibt den neuesten erfassten Heizölpreis zurück."""
    stmt = (
        select(HeizoelPreis)
        .order_by(HeizoelPreis.datum.desc(), HeizoelPreis.id.desc())
        .limit(1)
    )
    record = session.execute(stmt).scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keine Heizölpreise in der Datenbank vorhanden.",
        )

    return _serialize_record(record)
