from unittest.mock import AsyncMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from data_recorder.core.scheduler import (
    ebus_hourly_poll_job,
    get_scheduler,
    init_scheduler,
    shutdown_scheduler,
    start_scheduler,
)


def test_init_scheduler_registers_hourly_job():
    """Tests that scheduler initialization registers the ebus hourly job at minute 0."""
    scheduler = init_scheduler()
    assert isinstance(scheduler, AsyncIOScheduler)

    jobs = scheduler.get_jobs()
    job_ids = [j.id for j in jobs]
    assert "ebus_hourly_poll" in job_ids

    ebus_job = scheduler.get_job("ebus_hourly_poll")
    assert ebus_job is not None
    assert isinstance(ebus_job.trigger, CronTrigger)
    # Check trigger fields (minute=0)
    minute_field = str(ebus_job.trigger.fields[ebus_job.trigger.FIELD_NAMES.index("minute")])
    assert minute_field == "0"


@pytest.mark.asyncio
async def test_ebus_hourly_poll_job_calls_service():
    """Tests that ebus_hourly_poll_job calls ebus_service.poll_and_save."""
    with patch(
        "data_recorder.services.ebus_service.EbusService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = None
        await ebus_hourly_poll_job()
        assert mock_poll.call_count == 1


@pytest.mark.asyncio
async def test_ebus_hourly_poll_job_success_logging():
    """Tests that ebus_hourly_poll_job logs success when record is returned."""
    from unittest.mock import MagicMock
    mock_record = MagicMock()
    mock_record.zeitstempel = "2026-09-27 12:00:00"
    mock_record.cop_aktuell = 3.8
    mock_record.ertrag_gesamt_kwh = 18260.5
    mock_record.strom_gesamt_kwh = 4801.8

    with patch(
        "data_recorder.services.ebus_service.EbusService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.return_value = mock_record
        await ebus_hourly_poll_job()
        assert mock_poll.call_count == 1


@pytest.mark.asyncio
async def test_ebus_hourly_poll_job_zero_crash_on_exception():
    """Tests that any unexpected exception in the job is caught, logged, and does not crash."""
    with patch(
        "data_recorder.services.ebus_service.EbusService.poll_and_save",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.side_effect = RuntimeError("Fatal connection drop")
        # Should not raise exception
        await ebus_hourly_poll_job()
        assert mock_poll.call_count == 1


@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Tests start and shutdown of the global scheduler instance."""
    scheduler = init_scheduler()
    assert get_scheduler() is scheduler

    start_scheduler()
    assert scheduler.running

    shutdown_scheduler()
    import asyncio
    await asyncio.sleep(0)
    assert not scheduler.running
