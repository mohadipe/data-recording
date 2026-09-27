import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from data_recorder.services.ebus_service import EbusService
from data_recorder.services.oil_price_service import OilPriceService
from data_recorder.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def ebus_hourly_poll_job() -> None:
    """Stündlicher Hintergrund-Job zur Abfrage und Speicherung der eBUS-Wärmepumpendaten."""
    logger.info("Starte stündlichen eBUS aroTHERM Polling-Job...")
    try:
        service = EbusService()
        result = await service.poll_and_save()
        if result:
            logger.info(
                "eBUS Polling-Job erfolgreich abgeschlossen: Zeitstempel=%s, COP=%s, ErtragTotal=%s, StromTotal=%s",
                result.zeitstempel,
                result.cop_aktuell,
                result.ertrag_gesamt_kwh,
                result.strom_gesamt_kwh,
            )
        else:
            logger.warning(
                "eBUS Polling-Job konnte keine Daten abrufen oder speichern (eBUS ggf. vorübergehend nicht erreichbar)."
            )
    except Exception as exc:
        logger.error(
            "Unerwarteter Fehler im eBUS Polling-Job: %s. Scheduler läuft ungestört weiter.",
            exc,
            exc_info=True,
        )


async def oil_price_weekly_poll_job() -> None:
    """Wöchentlicher Hintergrund-Job zur Abfrage und Speicherung des regionalen Heizölpreises (Montags 08:00 Uhr)."""
    logger.info("Starte wöchentlichen Heizölpreis-Polling-Job...")
    try:
        service = OilPriceService()
        result = await service.poll_and_save()
        if result:
            logger.info(
                "Heizölpreis-Job erfolgreich abgeschlossen: Datum=%s, PLZ=%s, Menge=%dL, Preis/L=%s €",
                result.datum,
                result.plz,
                result.menge_liter,
                result.preis_pro_liter,
            )
        else:
            logger.warning(
                "Heizölpreis-Job konnte keinen Preis erfassen (Anbieter vorübergehend nicht erreichbar oder kein Angebot)."
            )
    except Exception as exc:
        logger.error(
            "Unerwarteter Fehler im Heizölpreis-Polling-Job: %s. Scheduler läuft ungestört weiter.",
            exc,
            exc_info=True,
        )


async def stock_price_daily_poll_job() -> None:
    """Täglicher Hintergrund-Job (Mo-Fr 22:30 Uhr) zur Abfrage und Speicherung der Tradegate-Schlusskurse."""
    logger.info("Starte täglichen Tradegate/Yahoo-Finance Kursabfrage-Job...")
    try:
        service = StockPriceService()
        results = await service.poll_and_save()
        if results:
            logger.info(
                "Tradegate Kursabfrage-Job erfolgreich abgeschlossen: %d Kurse aktualisiert.",
                len(results),
            )
        else:
            logger.warning(
                "Tradegate Kursabfrage-Job konnte keine Kurse aktualisieren (keine aktiven Wertpapiere oder Yahoo Finance nicht erreichbar)."
            )
    except Exception as exc:
        logger.error(
            "Unerwarteter Fehler im Tradegate Kursabfrage-Job: %s. Scheduler läuft ungestört weiter.",
            exc,
            exc_info=True,
        )


def init_scheduler() -> AsyncIOScheduler:
    """Initializes and configures the APScheduler instance with all scheduled jobs."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()

    # Register ebus hourly job at minute 0 (every hour on the hour)
    if _scheduler.get_job("ebus_hourly_poll") is None:
        _scheduler.add_job(
            ebus_hourly_poll_job,
            trigger=CronTrigger(minute=0),
            id="ebus_hourly_poll",
            name="Stündliches eBUS aroTHERM Polling",
            replace_existing=True,
            misfire_grace_time=300,
        )

    # Register oil price weekly job on Mondays at 08:00
    if _scheduler.get_job("oil_price_weekly_poll") is None:
        _scheduler.add_job(
            oil_price_weekly_poll_job,
            trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
            id="oil_price_weekly_poll",
            name="Wöchentliches Heizölpreis-Polling (Montag 08:00)",
            replace_existing=True,
            misfire_grace_time=3600,
        )

    # Register stock price daily job Monday to Friday at 22:30 (after Tradegate close)
    if _scheduler.get_job("stock_price_daily_poll") is None:
        _scheduler.add_job(
            stock_price_daily_poll_job,
            trigger=CronTrigger(day_of_week="mon-fri", hour=22, minute=30),
            id="stock_price_daily_poll",
            name="Tägliche Tradegate-Kursabfrage (Mo-Fr 22:30)",
            replace_existing=True,
            misfire_grace_time=3600,
        )

    return _scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    """Returns the current scheduler instance."""
    return _scheduler


def start_scheduler() -> None:
    """Starts the background scheduler if not already running."""
    scheduler = init_scheduler()
    if not scheduler.running:
        logger.info("Starte APScheduler Hintergrund-Dienst...")
        scheduler.start()


def shutdown_scheduler(wait: bool = False) -> None:
    """Gracefully shuts down the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("Stoppe APScheduler Hintergrund-Dienst...")
        _scheduler.shutdown(wait=wait)
        _scheduler = None
