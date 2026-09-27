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
from data_recorder.services.hibiscus_service import HibiscusService
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


class ScanHibiscusRequest(BaseModel):
    """Optional filter parameters for Hibiscus scan."""

    account_filters: list[str] | None = None


class HibiscusImportedItemResponse(BaseModel):
    """Schema for a single imported Hibiscus transaction."""

    umsatz_id: int
    wkn: str | None = None
    isin: str | None = None
    typ: str
    datum: str
    betrag: float


class ScanHibiscusResponse(BaseModel):
    """Schema for Hibiscus scan response."""

    status: str
    message: str
    scanned_count: int
    imported_count: int
    skipped_count: int
    sparplaene_count: int
    dividenden_count: int
    details: list[HibiscusImportedItemResponse] = []


def get_wertpapiere_db():
    """Dependency provider for wertpapiere schema database session."""
    for session in get_db_session("wertpapiere"):
        yield session


def get_hibiscus_db():
    """Dependency provider for hibiscus schema database session."""
    for session in get_db_session("hibiscus"):
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


@router.post(
    "/scan-hibiscus",
    response_model=ScanHibiscusResponse,
    summary="Manueller Hibiscus-Kontoauszug-Scanner Trigger",
    description=(
        "Liest neue Buchungen aus der Hibiscus-Umsatztabelle, extrahiert WKNs/ISINs "
        "und bucht Sparpläne in wkn_invest_datum sowie Dividenden in wkn_ertrag_datum."
    ),
)
async def scan_hibiscus(
    request: ScanHibiscusRequest | None = None,
    session_wp: Session = Depends(get_wertpapiere_db),
    session_hib: Session = Depends(get_hibiscus_db),
) -> Any:
    """Manuell ausgelöster Hibiscus-Scan für Sparpläne & Dividenden."""
    service = HibiscusService()
    account_filters = request.account_filters if request else None

    result = service.scan_and_import(
        session_wertpapiere=session_wp,
        session_hibiscus=session_hib,
        account_filters=account_filters,
    )

    items = [
        HibiscusImportedItemResponse(
            umsatz_id=d["umsatz_id"],
            wkn=d.get("wkn"),
            isin=d.get("isin"),
            typ=d["typ"],
            datum=d["datum"],
            betrag=d["betrag"],
        )
        for d in result.details
    ]

    return ScanHibiscusResponse(
        status="ok",
        message=(
            f"{result.scanned_count} Buchungen gescannt, "
            f"{result.imported_count} importiert ({result.sparplaene_count} Sparpläne, "
            f"{result.dividenden_count} Dividenden), {result.skipped_count} übersprungen."
        ),
        scanned_count=result.scanned_count,
        imported_count=result.imported_count,
        skipped_count=result.skipped_count,
        sparplaene_count=result.sparplaene_count,
        dividenden_count=result.dividenden_count,
        details=items,
    )
