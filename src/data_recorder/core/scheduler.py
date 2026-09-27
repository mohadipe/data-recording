import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from data_recorder.services.ebus_service import EbusService

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
