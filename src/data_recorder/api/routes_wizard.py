"""API and Web routes for the mobile meter reading wizard."""

from __future__ import annotations

import datetime
from decimal import Decimal
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from data_recorder.core.database import get_db_session
from data_recorder.models.verbrauch import Messwert, Zaehler
from data_recorder.services.exif_service import extract_capture_datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["wizard"])


def get_default_unit(typ: str) -> str:
    """Returns standard unit based on meter category."""
    typ_upper = typ.upper()
    if any(k in typ_upper for k in ("WASSER", "VOLUMEN", "ÖL", "OEL")):
        return "M3"
    return "KWH"


def format_german_number(val: Decimal | float | int) -> str:
    """Formats numeric value with German thousand separators and decimal commas."""
    formatted = f"{float(val):,.2f}"
    # Convert 12,450.50 -> 12.450,50
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


@router.get("/api/zaehler", summary="List active meters with latest readings")
async def list_zaehler(
    active_only: bool = True,
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieves all active meters and attaches their most recent reading."""
    today = datetime.date.today()
    stmt = select(Zaehler)
    if active_only:
        stmt = stmt.where(Zaehler.ausbau_dt >= today)
    stmt = stmt.order_by(Zaehler.typ.asc(), Zaehler.id.asc())

    zaehler_list = session.scalars(stmt).all()
    results: list[dict[str, Any]] = []

    for z in zaehler_list:
        latest_reading_stmt = (
            select(Messwert)
            .where(Messwert.zaehler_id == z.id)
            .order_by(desc(Messwert.datum), desc(Messwert.id))
            .limit(1)
        )
        latest_mw = session.scalars(latest_reading_stmt).first()

        unit = latest_mw.einheit if latest_mw else get_default_unit(z.typ)
        last_val = float(latest_mw.wert) if latest_mw else None
        last_date = latest_mw.datum.isoformat() if latest_mw else None

        results.append(
            {
                "id": z.id,
                "geraete_nr": z.geraete_nr,
                "typ": z.typ,
                "einbau_dt": z.einbau_dt.isoformat(),
                "ausbau_dt": z.ausbau_dt.isoformat(),
                "is_active": z.ausbau_dt >= today,
                "einheit": unit,
                "last_wert": last_val,
                "last_datum": last_date,
            }
        )

    return results


@router.get("/api/zaehler/{zaehler_id}/latest", summary="Get meter and latest reading")
async def get_zaehler_latest(
    zaehler_id: int,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieves meter details and the previous measurement for plausibility checking."""
    zaehler = session.get(Zaehler, zaehler_id)
    if not zaehler:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zähler mit ID {zaehler_id} nicht gefunden",
        )

    latest_reading_stmt = (
        select(Messwert)
        .where(Messwert.zaehler_id == zaehler.id)
        .order_by(desc(Messwert.datum), desc(Messwert.id))
        .limit(1)
    )
    latest_mw = session.scalars(latest_reading_stmt).first()

    unit = latest_mw.einheit if latest_mw else get_default_unit(zaehler.typ)
    last_val = float(latest_mw.wert) if latest_mw else None
    last_date = latest_mw.datum.isoformat() if latest_mw else None

    formatted_str = None
    if latest_mw:
        german_date = latest_mw.datum.strftime("%d.%m.%Y")
        german_val = format_german_number(latest_mw.wert)
        formatted_str = f"Letzter Stand (vom {german_date}): {german_val} {unit}"

    return {
        "zaehler_id": zaehler.id,
        "geraete_nr": zaehler.geraete_nr,
        "typ": zaehler.typ,
        "einheit": unit,
        "last_wert": last_val,
        "last_datum": last_date,
        "formatted_last_reading": formatted_str,
    }


@router.post("/api/wizard/extract-date", summary="Extract capture date from uploaded receipt")
async def extract_date_from_photo(
    foto: UploadFile = File(...),
) -> dict[str, Any]:
    """Extracts the picture capture timestamp from EXIF metadata with fallback to today."""
    content = await foto.read()
    sentinel = datetime.datetime(1970, 1, 1, 0, 0, 0)
    extracted = extract_capture_datetime(content, fallback=sentinel)

    if extracted == sentinel:
        captured_dt = datetime.datetime.now()
        has_exif = False
    else:
        captured_dt = extracted
        has_exif = True

    return {
        "success": True,
        "date": captured_dt.strftime("%Y-%m-%d"),
        "datetime": captured_dt.isoformat(),
        "has_exif": has_exif,
    }
