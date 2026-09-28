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
    Response,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from data_recorder.core.database import get_db_session
from data_recorder.models.verbrauch import Messwert, Zaehler
from data_recorder.services.exif_service import extract_capture_datetime
from data_recorder.services.shared_photo_service import SharedPhotoService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["wizard"])

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ZaehlerCreateRequest(BaseModel):
    """Schema for creating a new meter."""

    geraete_nr: str
    typ: str
    einbau_dt: datetime.date = Field(default_factory=datetime.date.today)
    ausbau_dt: datetime.date | None = None


class ZaehlerUpdateRequest(BaseModel):
    """Schema for updating meter metadata or lifespan dates."""

    geraete_nr: str | None = None
    typ: str | None = None
    einbau_dt: datetime.date | None = None
    ausbau_dt: datetime.date | None = None


class ZaehlerAusbauRequest(BaseModel):
    """Schema for marking a meter as decommissioned."""

    ausbau_dt: datetime.date = Field(default_factory=datetime.date.today)



def get_default_unit(typ: str) -> str:
    """Returns standard unit based on meter category."""
    typ_upper = typ.upper()
    if any(k in typ_upper for k in ("WASSER", "VOLUMEN", "ÖL", "OEL")):
        return "M3"
    return "KWH"


def format_german_number(val: Decimal | float | int | None) -> str:
    """Formats numeric value with German thousand separators and decimal commas."""
    if val is None:
        return "–"
    formatted = f"{float(val):,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def get_meter_readings_info(z: Zaehler, session: Session) -> dict[str, Any]:
    """Extracts meter details, active state, and latest measurement(s) including dual-values for heat meters."""
    today = datetime.date.today()
    is_dual = z.typ.upper() == "WAERME"

    if is_dual:
        kwh_stmt = (
            select(Messwert)
            .where(Messwert.zaehler_id == z.id, Messwert.einheit == "KWH")
            .order_by(desc(Messwert.datum), desc(Messwert.id))
            .limit(1)
        )
        m3_stmt = (
            select(Messwert)
            .where(Messwert.zaehler_id == z.id, Messwert.einheit == "M3")
            .order_by(desc(Messwert.datum), desc(Messwert.id))
            .limit(1)
        )
        mw_kwh = session.scalars(kwh_stmt).first()
        mw_m3 = session.scalars(m3_stmt).first()

        last_kwh_val = float(mw_kwh.wert) if mw_kwh else None
        last_m3_val = float(mw_m3.wert) if mw_m3 else None
        last_kwh_date = mw_kwh.datum.isoformat() if mw_kwh else None
        last_m3_date = mw_m3.datum.isoformat() if mw_m3 else None

        parts = []
        if mw_kwh:
            parts.append(f"{format_german_number(mw_kwh.wert)} kWh")
        if mw_m3:
            parts.append(f"{format_german_number(mw_m3.wert)} m³")

        latest_date = None
        if mw_kwh and mw_m3:
            latest_date = max(mw_kwh.datum, mw_m3.datum)
        elif mw_kwh:
            latest_date = mw_kwh.datum
        elif mw_m3:
            latest_date = mw_m3.datum

        date_prefix = f"(vom {latest_date.strftime('%d.%m.%Y')}): " if latest_date else ""
        formatted_reading = (
            f"Letzter Stand {date_prefix}{' • '.join(parts)}" if parts else "Kein Stand erfasst"
        )
        return {
            "id": z.id,
            "geraete_nr": z.geraete_nr,
            "typ": z.typ,
            "einbau_dt": z.einbau_dt.isoformat(),
            "ausbau_dt": z.ausbau_dt.isoformat(),
            "is_active": z.ausbau_dt >= today,
            "is_dual": True,
            "einheit": "KWH",
            "last_wert": last_kwh_val,
            "last_datum": last_kwh_date,
            "last_wert_kwh": last_kwh_val,
            "last_datum_kwh": last_kwh_date,
            "last_wert_m3": last_m3_val,
            "last_datum_m3": last_m3_date,
            "formatted_reading": formatted_reading,
            "formatted_kwh": f"Letzter Stand (vom {mw_kwh.datum.strftime('%d.%m.%Y')}): {format_german_number(mw_kwh.wert)} kWh" if mw_kwh else "Kein Stand erfasst",
            "formatted_m3": f"Letzter Stand (vom {mw_m3.datum.strftime('%d.%m.%Y')}): {format_german_number(mw_m3.wert)} m³" if mw_m3 else "Kein Stand erfasst",
        }
    else:
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
        return {
            "id": z.id,
            "geraete_nr": z.geraete_nr,
            "typ": z.typ,
            "einbau_dt": z.einbau_dt.isoformat(),
            "ausbau_dt": z.ausbau_dt.isoformat(),
            "is_active": z.ausbau_dt >= today,
            "is_dual": False,
            "einheit": unit,
            "last_wert": last_val,
            "last_datum": last_date,
            "last_wert_kwh": None,
            "last_datum_kwh": None,
            "last_wert_m3": None,
            "last_datum_m3": None,
            "formatted_reading": formatted_reading,
            "formatted_kwh": None,
            "formatted_m3": None,
        }


@router.get("/", response_class=HTMLResponse, summary="Mobile meter reading wizard home")
@router.get("/wizard", response_class=HTMLResponse, summary="Mobile meter reading wizard")
async def get_wizard_page(
    request: Request,
    zaehler_id: int | None = None,
    shared_photo_id: str | None = None,
    error: str | None = None,
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
    meters_data = [get_meter_readings_info(z, session) for z in zaehler_list]

    # Process shared photo prefill if passed
    shared_photo_data: dict[str, Any] | None = None
    if shared_photo_id:
        shared_service = SharedPhotoService()
        meta = shared_service.get_shared_photo_meta(shared_photo_id)
        if meta:
            shared_photo_data = {
                "id": meta.id,
                "filename": meta.original_filename,
                "capture_date": meta.capture_date,
                "has_exif": meta.has_exif,
                "is_heic": meta.is_heic,
                "preview_url": f"/api/wizard/shared-photo/{meta.id}?preview=1",
            }

    # Map error query param to user-friendly German message
    error_message: str | None = None
    if error == "empty_file":
        error_message = "Die geteilte Datei war leer. Bitte wähle ein gültiges Zählerfoto."
    elif error == "invalid_image":
        error_message = "Das geteilte Bildformat wird nicht unterstützt oder die Datei ist beschädigt."
    elif error:
        error_message = f"Fehler beim Übernehmen des Fotos ({error})."

    return templates.TemplateResponse(
        request=request,
        name="wizard.html",
        context={
            "request": request,
            "meters": meters_data,
            "selected_zaehler_id": zaehler_id,
            "today_date": today.isoformat(),
            "shared_photo": shared_photo_data,
            "error_message": error_message,
        },
    )


@router.get("/zaehler", response_class=HTMLResponse, summary="Meter management overview")
async def get_zaehler_page(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    """Renders the meter management page."""
    today = datetime.date.today()
    stmt = select(Zaehler).order_by(Zaehler.ausbau_dt.desc(), Zaehler.typ.asc(), Zaehler.id.asc())
    zaehler_list = session.scalars(stmt).all()

    meters_data = [get_meter_readings_info(z, session) for z in zaehler_list]
    try:
        default_ausbau = today.replace(year=today.year + 8).isoformat()
    except ValueError:
        default_ausbau = (today + datetime.timedelta(days=2922)).isoformat()

    return templates.TemplateResponse(
        request=request,
        name="zaehler.html",
        context={
            "request": request,
            "meters": meters_data,
            "today_date": today.isoformat(),
            "default_ausbau_date": default_ausbau,
        },
    )


@router.get("/api/zaehler", summary="List meters with latest readings")
async def list_zaehler(
    active_only: bool = True,
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieves all meters (active only or all) and attaches their most recent reading."""
    today = datetime.date.today()
    stmt = select(Zaehler)
    if active_only:
        stmt = stmt.where(Zaehler.ausbau_dt >= today)
    stmt = stmt.order_by(Zaehler.typ.asc(), Zaehler.id.asc())

    zaehler_list = session.scalars(stmt).all()
    return [get_meter_readings_info(z, session) for z in zaehler_list]


@router.post(
    "/api/zaehler",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new meter",
)
async def create_zaehler(
    payload: ZaehlerCreateRequest,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Creates a new meter entity."""
    today = datetime.date.today()
    ausbau = payload.ausbau_dt
    if not ausbau:
        try:
            ausbau = payload.einbau_dt.replace(year=payload.einbau_dt.year + 10)
        except ValueError:
            ausbau = payload.einbau_dt + datetime.timedelta(days=3652)

    zaehler = Zaehler(
        geraete_nr=payload.geraete_nr.strip(),
        typ=payload.typ.strip().upper(),
        einbau_dt=payload.einbau_dt,
        ausbau_dt=ausbau,
    )
    session.add(zaehler)
    session.commit()
    session.refresh(zaehler)

    return {
        "success": True,
        "message": f"Zähler {zaehler.geraete_nr} erfolgreich angelegt",
        "zaehler": {
            "id": zaehler.id,
            "geraete_nr": zaehler.geraete_nr,
            "typ": zaehler.typ,
            "einbau_dt": zaehler.einbau_dt.isoformat(),
            "ausbau_dt": zaehler.ausbau_dt.isoformat(),
            "is_active": zaehler.ausbau_dt >= today,
        },
    }


@router.patch("/api/zaehler/{zaehler_id}", summary="Update meter details")
@router.put("/api/zaehler/{zaehler_id}", summary="Update meter details")
async def update_zaehler(
    zaehler_id: int,
    payload: ZaehlerUpdateRequest,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Updates meter serial number, type, or lifespan dates."""
    zaehler = session.get(Zaehler, zaehler_id)
    if not zaehler:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zähler mit ID {zaehler_id} nicht gefunden",
        )

    if payload.geraete_nr is not None:
        zaehler.geraete_nr = payload.geraete_nr.strip()
    if payload.typ is not None:
        zaehler.typ = payload.typ.strip().upper()
    if payload.einbau_dt is not None:
        zaehler.einbau_dt = payload.einbau_dt
    if payload.ausbau_dt is not None:
        zaehler.ausbau_dt = payload.ausbau_dt

    session.commit()
    session.refresh(zaehler)
    today = datetime.date.today()

    return {
        "success": True,
        "message": f"Zähler {zaehler.geraete_nr} aktualisiert",
        "zaehler": {
            "id": zaehler.id,
            "geraete_nr": zaehler.geraete_nr,
            "typ": zaehler.typ,
            "einbau_dt": zaehler.einbau_dt.isoformat(),
            "ausbau_dt": zaehler.ausbau_dt.isoformat(),
            "is_active": zaehler.ausbau_dt >= today,
        },
    }


@router.post("/api/zaehler/{zaehler_id}/ausbau", summary="Decommission meter")
async def decommission_zaehler(
    zaehler_id: int,
    payload: ZaehlerAusbauRequest = ZaehlerAusbauRequest(),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Marks a meter as decommissioned by recording its removal date."""
    zaehler = session.get(Zaehler, zaehler_id)
    if not zaehler:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zähler mit ID {zaehler_id} nicht gefunden",
        )

    zaehler.ausbau_dt = payload.ausbau_dt
    session.commit()
    session.refresh(zaehler)
    today = datetime.date.today()

    return {
        "success": True,
        "message": f"Zähler {zaehler.geraete_nr} als ausgebaut markiert (Ausbaudatum: {zaehler.ausbau_dt.isoformat()})",
        "zaehler": {
            "id": zaehler.id,
            "geraete_nr": zaehler.geraete_nr,
            "typ": zaehler.typ,
            "einbau_dt": zaehler.einbau_dt.isoformat(),
            "ausbau_dt": zaehler.ausbau_dt.isoformat(),
            "is_active": zaehler.ausbau_dt >= today,
        },
    }


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

    info = get_meter_readings_info(zaehler, session)
    info["zaehler_id"] = zaehler.id
    info["formatted_last_reading"] = info["formatted_reading"]
    return info


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


@router.post("/wizard/share", summary="Receive shared photo from PWA Web Share Target")
async def receive_shared_photo(
    foto: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> RedirectResponse:
    """Receives photos shared into the PWA and redirects to the wizard with prefilled metadata."""
    shared_service = SharedPhotoService()
    # Trigger background cleanup of old shared uploads
    background_tasks.add_task(shared_service.cleanup_old_photos, 24)

    if not foto.filename and not foto.content_type:
        return RedirectResponse(
            url="/wizard?error=empty_file",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        content = await foto.read()
        if not content:
            return RedirectResponse(
                url="/wizard?error=empty_file",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        meta = shared_service.save_shared_photo(
            file_content=content,
            filename=foto.filename,
            content_type=foto.content_type,
        )
        return RedirectResponse(
            url=f"/wizard?shared_photo_id={meta.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as exc:
        logger.warning("Shared photo validation failed: %s", exc)
        return RedirectResponse(
            url="/wizard?error=invalid_image",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        logger.error("Unexpected error processing shared photo: %s", exc, exc_info=True)
        return RedirectResponse(
            url="/wizard?error=server_error",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/api/wizard/shared-photo/{photo_id}", summary="Get shared photo bytes (or JPEG preview)")
async def get_shared_photo(
    photo_id: str,
    preview: bool = False,
) -> Response:
    """Returns the raw or JPEG-preview bytes of a temporarily shared photo."""
    shared_service = SharedPhotoService()
    res = shared_service.get_shared_photo_bytes(photo_id, prefer_preview=preview)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geteiltes Foto mit ID {photo_id} nicht gefunden",
        )
    raw_bytes, media_type = res
    return Response(
        content=raw_bytes,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/api/wizard/shared-photo/{photo_id}/meta", summary="Get shared photo metadata")
async def get_shared_photo_metadata(
    photo_id: str,
) -> dict[str, Any]:
    """Returns metadata (EXIF capture date, format, filename) for a shared photo."""
    shared_service = SharedPhotoService()
    meta = shared_service.get_shared_photo_meta(photo_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geteiltes Foto mit ID {photo_id} nicht gefunden",
        )
    return {
        "id": meta.id,
        "filename": meta.original_filename,
        "content_type": meta.content_type,
        "file_size": meta.file_size_bytes,
        "capture_date": meta.capture_date,
        "capture_datetime": meta.capture_datetime,
        "has_exif": meta.has_exif,
        "is_heic": meta.is_heic,
        "preview_url": f"/api/wizard/shared-photo/{meta.id}?preview=1",
    }


@router.post("/wizard/submit", summary="Submit meter reading and upload receipt")
@router.post("/api/wizard/submit", summary="Submit meter reading (API alias)")
async def submit_reading(
    zaehler_id: int = Form(...),
    datum: str = Form(...),
    wert: Decimal | None = Form(None),
    wert_kwh: Decimal | None = Form(None),
    wert_m3: Decimal | None = Form(None),
    einheit: str | None = Form(None),
    foto: UploadFile | None = File(None),
    shared_photo_id: str | None = Form(None),
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

    if wert is None and wert_kwh is None and wert_m3 is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitte mindestens einen Zählerstand angeben",
        )

    is_dual = zaehler.typ.upper() == "WAERME" or (wert_kwh is not None and wert_m3 is not None)

    saved_records = []
    mw_kwh: Messwert | None = None
    mw_m3: Messwert | None = None
    verbrauch_kwh: Decimal | None = None
    verbrauch_m3: Decimal | None = None
    primary_mw: Messwert | None = None
    primary_prior_val: float | None = None
    primary_verbrauch: Decimal | None = None

    if wert_kwh is not None or wert_m3 is not None:
        if wert_kwh is not None:
            prior_kwh_stmt = (
                select(Messwert)
                .where(
                    Messwert.zaehler_id == zaehler_id,
                    Messwert.datum < reading_date,
                    Messwert.einheit == "KWH",
                )
                .order_by(desc(Messwert.datum), desc(Messwert.id))
                .limit(1)
            )
            prior_kwh = session.scalars(prior_kwh_stmt).first()
            verbrauch_kwh = (wert_kwh - prior_kwh.wert) if prior_kwh else None

            existing_kwh_stmt = select(Messwert).where(
                Messwert.zaehler_id == zaehler_id,
                Messwert.datum == reading_date,
                Messwert.einheit == "KWH",
            )
            existing_kwh = session.scalars(existing_kwh_stmt).first()
            if existing_kwh:
                existing_kwh.wert = wert_kwh
                mw_kwh = existing_kwh
            else:
                mw_kwh = Messwert(
                    zaehler_id=zaehler_id,
                    datum=reading_date,
                    wert=wert_kwh,
                    einheit="KWH",
                )
                session.add(mw_kwh)
            saved_records.append(mw_kwh)
            if primary_mw is None:
                primary_mw = mw_kwh
                primary_prior_val = float(prior_kwh.wert) if prior_kwh else None
                primary_verbrauch = verbrauch_kwh

        if wert_m3 is not None:
            prior_m3_stmt = (
                select(Messwert)
                .where(
                    Messwert.zaehler_id == zaehler_id,
                    Messwert.datum < reading_date,
                    Messwert.einheit == "M3",
                )
                .order_by(desc(Messwert.datum), desc(Messwert.id))
                .limit(1)
            )
            prior_m3 = session.scalars(prior_m3_stmt).first()
            verbrauch_m3 = (wert_m3 - prior_m3.wert) if prior_m3 else None

            existing_m3_stmt = select(Messwert).where(
                Messwert.zaehler_id == zaehler_id,
                Messwert.datum == reading_date,
                Messwert.einheit == "M3",
            )
            existing_m3 = session.scalars(existing_m3_stmt).first()
            if existing_m3:
                existing_m3.wert = wert_m3
                mw_m3 = existing_m3
            else:
                mw_m3 = Messwert(
                    zaehler_id=zaehler_id,
                    datum=reading_date,
                    wert=wert_m3,
                    einheit="M3",
                )
                session.add(mw_m3)
            saved_records.append(mw_m3)
            if primary_mw is None:
                primary_mw = mw_m3
                primary_prior_val = float(prior_m3.wert) if prior_m3 else None
                primary_verbrauch = verbrauch_m3

    else:
        # Standard single value
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
            selected_unit = (
                prior_unit_mw.einheit if prior_unit_mw else get_default_unit(zaehler.typ)
            )

        prior_reading_stmt = (
            select(Messwert)
            .where(
                Messwert.zaehler_id == zaehler_id,
                Messwert.datum < reading_date,
                Messwert.einheit == selected_unit,
            )
            .order_by(desc(Messwert.datum), desc(Messwert.id))
            .limit(1)
        )
        prior_reading = session.scalars(prior_reading_stmt).first()
        verbrauch = (
            (wert - prior_reading.wert) if (prior_reading and wert is not None) else None
        )

        existing_stmt = select(Messwert).where(
            Messwert.zaehler_id == zaehler_id,
            Messwert.datum == reading_date,
            Messwert.einheit == selected_unit,
        )
        existing_mw = session.scalars(existing_stmt).first()

        if existing_mw:
            existing_mw.wert = wert  # type: ignore[assignment]
            existing_mw.einheit = selected_unit
            primary_mw = existing_mw
        else:
            primary_mw = Messwert(
                zaehler_id=zaehler_id,
                datum=reading_date,
                wert=wert,  # type: ignore[arg-type]
                einheit=selected_unit,
            )
            session.add(primary_mw)
        saved_records.append(primary_mw)
        primary_verbrauch = verbrauch
        primary_prior_val = float(prior_reading.wert) if prior_reading else None

    session.commit()
    for rec in saved_records:
        session.refresh(rec)

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
    elif shared_photo_id and shared_photo_id.strip():
        shared_service = SharedPhotoService()
        shared_id = shared_photo_id.strip()
        shared_meta = shared_service.get_shared_photo_meta(shared_id)
        shared_bytes_info = shared_service.get_shared_photo_bytes(shared_id)
        if shared_meta and shared_bytes_info:
            raw_bytes, mime = shared_bytes_info
            foto_uploaded = True
            from data_recorder.services.paperless_service import PaperlessService

            paperless = PaperlessService()
            title = f"Zählerstand {zaehler.typ} {zaehler.geraete_nr} - {reading_date.strftime('%d.%m.%Y')}"
            created_dt = datetime.datetime.combine(reading_date, datetime.datetime.min.time())
            filename = shared_meta.original_filename or f"zaehler_{zaehler_id}_{reading_date.isoformat()}.jpg"

            background_tasks.add_task(
                paperless.upload_document,
                file_content=raw_bytes,
                filename=filename,
                title=title,
                created=created_dt,
                mime_type=mime,
            )
            # Clean up buffered shared photo file after submitting
            background_tasks.add_task(shared_service.delete_shared_photo, shared_id)

    return {
        "success": True,
        "message": "Zählerstand erfolgreich gespeichert",
        "messwert_id": primary_mw.id if primary_mw else None,
        "zaehler_id": zaehler.id,
        "geraete_nr": zaehler.geraete_nr,
        "typ": zaehler.typ,
        "datum": reading_date.isoformat(),
        "wert": float(primary_mw.wert) if primary_mw else None,
        "einheit": primary_mw.einheit if primary_mw else None,
        "vorheriger_wert": primary_prior_val,
        "verbrauch": float(primary_verbrauch) if primary_verbrauch is not None else None,
        "is_dual": is_dual,
        "wert_kwh": float(mw_kwh.wert) if mw_kwh else None,
        "verbrauch_kwh": float(verbrauch_kwh) if verbrauch_kwh is not None else None,
        "wert_m3": float(mw_m3.wert) if mw_m3 else None,
        "verbrauch_m3": float(verbrauch_m3) if verbrauch_m3 is not None else None,
        "foto_uploaded": foto_uploaded,
        "next_zaehler_id": next_zaehler.id if next_zaehler else None,
    }

