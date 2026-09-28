import datetime
import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from data_recorder.core.database import get_db_session
from data_recorder.models.wertpapiere import Etf, WknBestandDatum, WknKursDatum
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
    kurs: float
    wert: float | None = None


class HoldingItemResponse(BaseModel):
    """Schema for an active holding with current price and valuation."""

    model_config = ConfigDict(from_attributes=True)

    wkn_id: int
    wkn: str
    isin: str | None = None
    name: str | None = None
    ticker: str | None = None
    anteile: float
    bestand_datum: datetime.date | None = None
    kurs: float | None = None
    kurs_datum: datetime.date | None = None
    gesamtwert: float


class HoldingHistoryItemResponse(BaseModel):
    """Schema for a historical holding record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    wkn_id: int
    wkn: str
    name: str | None = None
    datum: datetime.date
    anteile: float
    erfasst_am: datetime.datetime


class CreateHoldingRequest(BaseModel):
    """Request payload for creating or updating a holding entry."""

    wkn_id: int
    datum: datetime.date
    anteile: Decimal = Field(gt=Decimal("0"), description="Anzahl der Anteile (> 0)")


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


def _serialize_stock_record(record: WknKursDatum) -> StockPriceItemResponse:
    wkn = record.etf.wkn if record.etf else None
    name = record.etf.name if record.etf else None
    ticker = record.etf.ticker_yahoo if record.etf else None
    kurs_val = float(record.kurs)

    return StockPriceItemResponse(
        id=record.id,
        wkn_id=record.wkn_id,
        wkn=wkn,
        name=name,
        ticker=ticker,
        datum=record.datum,
        kurs=kurs_val,
        wert=kurs_val,
    )


@router.post(
    "/update-prices",
    response_model=UpdatePricesResponse,
    summary="Manueller Tradegate-Kursabfrage Trigger",
    description=(
        "Ermittelt für alle aktiven Wertpapiere mit Yahoo-Ticker (.TG) "
        "den aktuellen Schlusskurs und speichert ihn idempotent in wkn_kurs_datum."
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
    description="Liefert die jeweils aktuellsten Notierungen aus der Tabelle wkn_kurs_datum.",
)
@router.get(
    "/latest-prices",
    response_model=list[StockPriceItemResponse],
    summary="Neueste Kurswerte aller Wertpapiere (Alias)",
    description="Liefert die jeweils aktuellsten Notierungen aus der Tabelle wkn_kurs_datum.",
    include_in_schema=False,
)
async def get_latest_prices(
    session: Session = Depends(get_wertpapiere_db),
) -> Any:
    """Gibt die neuesten erfassten Kurse aus wertpapiere.wkn_kurs_datum zurück."""
    # Find latest date per wkn_id
    subquery = (
        select(
            WknKursDatum.wkn_id,
            func.max(WknKursDatum.datum).label("max_datum"),
        )
        .group_by(WknKursDatum.wkn_id)
        .subquery()
    )

    stmt = (
        select(WknKursDatum)
        .options(joinedload(WknKursDatum.etf))
        .join(
            subquery,
            (WknKursDatum.wkn_id == subquery.c.wkn_id)
            & (WknKursDatum.datum == subquery.c.max_datum),
        )
        .order_by(WknKursDatum.wkn_id)
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


@router.get(
    "/holdings",
    response_model=list[HoldingItemResponse],
    summary="Aktuelle Anteilsbestände und Depotübersicht",
    description=(
        "Liefert alle aktiven Wertpapiere mit ihrem aktuellen Anteilsbestand, "
        "dem letzten Schlusskurs und dem berechneten Gesamtwert."
    ),
)
async def get_holdings(
    session: Session = Depends(get_wertpapiere_db),
) -> Any:
    """Gibt die Liste aller aktiven Wertpapiere mit aktuellem Bestand und Kurs zurück."""
    active_etfs = (
        session.execute(
            select(Etf)
            .where(Etf.aktiv.is_(True))
            .order_by(Etf.id)
        )
        .scalars()
        .all()
    )

    if not active_etfs:
        return []

    # Letzten Bestand je WKN ermitteln
    bestand_sub = (
        select(
            WknBestandDatum.wkn_id,
            func.max(WknBestandDatum.datum).label("max_datum"),
        )
        .group_by(WknBestandDatum.wkn_id)
        .subquery()
    )
    latest_bestaende = session.execute(
        select(WknBestandDatum).join(
            bestand_sub,
            (WknBestandDatum.wkn_id == bestand_sub.c.wkn_id)
            & (WknBestandDatum.datum == bestand_sub.c.max_datum),
        )
    ).scalars().all()
    bestand_map = {b.wkn_id: b for b in latest_bestaende}

    # Letzten Kurs je WKN ermitteln
    kurs_sub = (
        select(
            WknKursDatum.wkn_id,
            func.max(WknKursDatum.datum).label("max_datum"),
        )
        .group_by(WknKursDatum.wkn_id)
        .subquery()
    )
    latest_kurse = session.execute(
        select(WknKursDatum).join(
            kurs_sub,
            (WknKursDatum.wkn_id == kurs_sub.c.wkn_id)
            & (WknKursDatum.datum == kurs_sub.c.max_datum),
        )
    ).scalars().all()
    kurs_map = {k.wkn_id: k for k in latest_kurse}

    results: list[HoldingItemResponse] = []
    for etf in active_etfs:
        bestand = bestand_map.get(etf.id)
        kurs_rec = kurs_map.get(etf.id)

        anteile = float(bestand.anteile) if bestand else 0.0
        bestand_datum = bestand.datum if bestand else None
        kurs = float(kurs_rec.kurs) if kurs_rec else None
        kurs_datum = kurs_rec.datum if kurs_rec else None
        gesamtwert = round(anteile * kurs, 2) if kurs is not None else 0.0

        results.append(
            HoldingItemResponse(
                wkn_id=etf.id,
                wkn=etf.wkn,
                isin=etf.isin,
                name=etf.name,
                ticker=etf.ticker_yahoo,
                anteile=anteile,
                bestand_datum=bestand_datum,
                kurs=kurs,
                kurs_datum=kurs_datum,
                gesamtwert=gesamtwert,
            )
        )

    return results


@router.get(
    "/holdings/history",
    response_model=list[HoldingHistoryItemResponse],
    summary="Historie der Anteilsbestände",
    description="Liefert alle erfassten Stichtagsbestände absteigend nach Datum, optional gefiltert nach wkn_id.",
)
async def get_holdings_history(
    wkn_id: int | None = None,
    session: Session = Depends(get_wertpapiere_db),
) -> Any:
    """Liefert die Historie der Anteilsbestände (optional gefiltert nach wkn_id)."""
    stmt = (
        select(WknBestandDatum)
        .options(joinedload(WknBestandDatum.etf))
        .order_by(WknBestandDatum.datum.desc(), WknBestandDatum.id.desc())
    )
    if wkn_id is not None:
        stmt = stmt.where(WknBestandDatum.wkn_id == wkn_id)

    records = session.execute(stmt).scalars().all()
    return [
        HoldingHistoryItemResponse(
            id=r.id,
            wkn_id=r.wkn_id,
            wkn=r.etf.wkn if r.etf else "",
            name=r.etf.name if r.etf else None,
            datum=r.datum,
            anteile=float(r.anteile),
            erfasst_am=r.erfasst_am,
        )
        for r in records
    ]


@router.post(
    "/holdings",
    response_model=HoldingHistoryItemResponse,
    summary="Stichtagsbestand erfassen oder aktualisieren",
    description="Erfasst oder aktualisiert idempotent den Anteilsbestand für ein Wertpapier an einem Stichtag.",
)
async def create_or_update_holding(
    request: CreateHoldingRequest,
    session: Session = Depends(get_wertpapiere_db),
) -> Any:
    """Erfasst oder aktualisiert den Anteilsbestand eines Wertpapiers zu einem Stichtag."""
    etf = session.get(Etf, request.wkn_id)
    if not etf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wertpapier mit ID {request.wkn_id} nicht gefunden.",
        )

    stmt = select(WknBestandDatum).where(
        WknBestandDatum.wkn_id == request.wkn_id,
        WknBestandDatum.datum == request.datum,
    )
    record = session.execute(stmt).scalar_one_or_none()

    if record is None:
        record = WknBestandDatum(
            wkn_id=request.wkn_id,
            datum=request.datum,
            anteile=request.anteile,
        )
        session.add(record)
    else:
        record.anteile = request.anteile

    session.commit()
    session.refresh(record)

    return HoldingHistoryItemResponse(
        id=record.id,
        wkn_id=record.wkn_id,
        wkn=etf.wkn,
        name=etf.name,
        datum=record.datum,
        anteile=float(record.anteile),
        erfasst_am=record.erfasst_am,
    )


@router.delete(
    "/holdings/{id}",
    summary="Stichtagsbestand löschen",
    description="Löscht einen Stichtags-Anteilsbestand anhand seiner ID.",
)
async def delete_holding(
    id: int,
    session: Session = Depends(get_wertpapiere_db),
) -> Any:
    """Löscht einen Eintrag aus wkn_bestand_datum."""
    record = session.get(WknBestandDatum, id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bestandseintrag mit ID {id} nicht gefunden.",
        )

    session.delete(record)
    session.commit()
    return {"status": "ok", "message": f"Bestandseintrag {id} erfolgreich gelöscht."}
