import datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data_recorder.core.database import get_db_session
from data_recorder.models.wertpapiere import WknWertDatum
from data_recorder.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finance", tags=["Wertpapiere & Finanzen"])


class StockPriceItemResponse(BaseModel):
    """Schema for a single stock price quotation."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    wkn_id: int
    wkn: str | None = None
    name: str | None = None
    ticker: str | None = None
    datum: datetime.date
    wert: float


class UpdatePricesResponse(BaseModel):
    """Schema for stock prices update response."""

    status: str
    message: str
    updated_count: int
    data: list[StockPriceItemResponse] = []


def get_wertpapiere_db():
    """Dependency provider for wertpapiere schema database session."""
    for session in get_db_session("wertpapiere"):
        yield session


def _serialize_stock_record(record: WknWertDatum) -> StockPriceItemResponse:
    wkn = record.etf.wkn if record.etf else None
    name = record.etf.name if record.etf else None
    ticker = record.etf.ticker_yahoo if record.etf else None

    return StockPriceItemResponse(
        id=record.id,
        wkn_id=record.wkn_id,
        wkn=wkn,
        name=name,
        ticker=ticker,
        datum=record.datum,
        wert=float(record.wert),
    )


@router.post(
    "/update-prices",
    response_model=UpdatePricesResponse,
    summary="Manueller Tradegate-Kursabfrage Trigger",
    description=(
        "Ermittelt für alle aktiven Wertpapiere mit Yahoo-Ticker (.TG) "
        "den aktuellen Schlusskurs und speichert ihn idempotent in wkn_wert_datum."
    ),
)
async def update_prices(
    session: Session = Depends(get_wertpapiere_db),
) -> Any:
    """Manuell ausgelöste Kursaktualisierung für alle aktiven Wertpapiere."""
    service = StockPriceService()
    active_securities = service.get_active_securities(session)

    if not active_securities:
        return UpdatePricesResponse(
            status="ok",
            message="Keine aktiven Wertpapiere mit Yahoo-Ticker vorhanden.",
            updated_count=0,
            data=[],
        )

    records = await service.poll_and_save(session=session)

    if not records:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "status": "error",
                "message": "Keine Kurse von Yahoo Finance ermittelt (Anbieter nicht erreichbar oder keine Kursdaten erhalten).",
                "updated_count": 0,
                "data": [],
            },
        )

    serialized_data = [_serialize_stock_record(r) for r in records]
    return UpdatePricesResponse(
        status="ok",
        message=f"{len(records)} Kurs(e) erfolgreich aktualisiert.",
        updated_count=len(records),
        data=serialized_data,
    )


@router.get(
    "/latest",
    response_model=list[StockPriceItemResponse],
    summary="Neueste Kurswerte aller Wertpapiere",
    description="Liefert die jeweils aktuellsten Notierungen aus der Tabelle wkn_wert_datum.",
)
async def get_latest_prices(
    session: Session = Depends(get_wertpapiere_db),
) -> Any:
    """Gibt die neuesten erfassten Kurse aus wertpapiere.wkn_wert_datum zurück."""
    # Find latest date per wkn_id
    subquery = (
        select(
            WknWertDatum.wkn_id,
            func.max(WknWertDatum.datum).label("max_datum"),
        )
        .group_by(WknWertDatum.wkn_id)
        .subquery()
    )

    stmt = (
        select(WknWertDatum)
        .join(
            subquery,
            (WknWertDatum.wkn_id == subquery.c.wkn_id)
            & (WknWertDatum.datum == subquery.c.max_datum),
        )
        .order_by(WknWertDatum.wkn_id)
    )

    records = session.execute(stmt).scalars().all()
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keine Kurswerte in der Datenbank vorhanden.",
        )

    return [_serialize_stock_record(r) for r in records]
