"""API and Web routes for the mobile meter reading wizard."""

from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from data_recorder.core.database import get_db_session
from data_recorder.models.verbrauch import Messwert, Zaehler
from data_recorder.services.exif_service import extract_capture_datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["wizard"])

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse, summary="Mobile meter reading wizard home")
@router.get("/wizard", response_class=HTMLResponse, summary="Mobile meter reading wizard")
async def get_wizard_page(
    request: Request,
    zaehler_id: int | None = None,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    """Renders the mobile 3-step meter reading wizard."""
    today = datetime.date.today()
    stmt = (
        select(Zaehler)
        .where(Zaehler.ausbau_dt >= today)
        .order_by(Zaehler.typ.asc(), Zaehler.id.asc())
    )
    zaehler_list = session.scalars(stmt).all()

    meters_data = []
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

        formatted_reading = (
            f"Letzter Stand (vom {latest_mw.datum.strftime('%d.%m.%Y')}): {format_german_number(latest_mw.wert)} {unit}"
            if latest_mw
            else "Kein Stand erfasst"
        )
        meters_data.append(
            {
                "id": z.id,
                "geraete_nr": z.geraete_nr,
                "typ": z.typ,
                "einheit": unit,
                "last_wert": last_val,
                "last_datum": last_date,
                "formatted_reading": formatted_reading,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="wizard.html",
        context={
            "request": request,
            "meters": meters_data,
            "selected_zaehler_id": zaehler_id,
            "today_date": today.isoformat(),
        },
    )


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


@router.post("/wizard/submit", summary="Submit meter reading and upload receipt")
@router.post("/api/wizard/submit", summary="Submit meter reading (API alias)")
async def submit_reading(
    zaehler_id: int = Form(...),
    datum: str = Form(...),
    wert: Decimal = Form(...),
    einheit: str | None = Form(None),
    foto: UploadFile | None = File(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Saves a meter measurement to database and schedules receipt upload to Paperless-ngx."""
    try:
        reading_date = datetime.date.fromisoformat(datum.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültiges Datumsformat (erwartet: YYYY-MM-DD)",
        )

    zaehler = session.get(Zaehler, zaehler_id)
    if not zaehler:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zähler mit ID {zaehler_id} nicht gefunden",
        )

    # Determine unit
    if einheit and einheit.strip():
        selected_unit = einheit.strip().upper()
    else:
        prior_unit_stmt = (
            select(Messwert)
            .where(Messwert.zaehler_id == zaehler_id)
            .order_by(desc(Messwert.datum), desc(Messwert.id))
            .limit(1)
        )
        prior_unit_mw = session.scalars(prior_unit_stmt).first()
        selected_unit = prior_unit_mw.einheit if prior_unit_mw else get_default_unit(zaehler.typ)

    # Plausibility check: find most recent reading before the new date
    prior_reading_stmt = (
        select(Messwert)
        .where(Messwert.zaehler_id == zaehler_id, Messwert.datum < reading_date)
        .order_by(desc(Messwert.datum), desc(Messwert.id))
        .limit(1)
    )
    prior_reading = session.scalars(prior_reading_stmt).first()
    verbrauch = (wert - prior_reading.wert) if prior_reading else None

    # Idempotent DB insertion/update
    existing_stmt = select(Messwert).where(
        Messwert.zaehler_id == zaehler_id,
        Messwert.datum == reading_date,
    )
    existing_mw = session.scalars(existing_stmt).first()

    if existing_mw:
        existing_mw.wert = wert
        existing_mw.einheit = selected_unit
        messwert = existing_mw
    else:
        messwert = Messwert(
            zaehler_id=zaehler_id,
            datum=reading_date,
            wert=wert,
            einheit=selected_unit,
        )
        session.add(messwert)

    session.commit()
    session.refresh(messwert)

    # Find next active meter for convenient navigation
    today = datetime.date.today()
    next_zaehler_stmt = (
        select(Zaehler)
        .where(Zaehler.ausbau_dt >= today, Zaehler.id != zaehler_id)
        .order_by(Zaehler.typ.asc(), Zaehler.id.asc())
    )
    next_zaehler = session.scalars(next_zaehler_stmt).first()

    # Handle optional photo upload to Paperless-ngx asynchronously
    foto_uploaded = False
    if foto is not None and foto.filename:
        foto_bytes = await foto.read()
        if len(foto_bytes) > 0:
            foto_uploaded = True
            from data_recorder.services.paperless_service import PaperlessService

            paperless = PaperlessService()
            title = f"Zählerstand {zaehler.typ} {zaehler.geraete_nr} - {reading_date.strftime('%d.%m.%Y')}"
            created_dt = datetime.datetime.combine(reading_date, datetime.datetime.min.time())
            filename = foto.filename or f"zaehler_{zaehler_id}_{reading_date.isoformat()}.jpg"
            mime_type = foto.content_type or "image/jpeg"

            background_tasks.add_task(
                paperless.upload_document,
                file_content=foto_bytes,
                filename=filename,
                title=title,
                created=created_dt,
                mime_type=mime_type,
            )

    return {
        "success": True,
        "message": "Zählerstand erfolgreich gespeichert",
        "messwert_id": messwert.id,
        "zaehler_id": zaehler.id,
        "geraete_nr": zaehler.geraete_nr,
        "typ": zaehler.typ,
        "datum": reading_date.isoformat(),
        "wert": float(messwert.wert),
        "einheit": selected_unit,
        "vorheriger_wert": float(prior_reading.wert) if prior_reading else None,
        "verbrauch": float(verbrauch) if verbrauch is not None else None,
        "foto_uploaded": foto_uploaded,
        "next_zaehler_id": next_zaehler.id if next_zaehler else None,
    }

