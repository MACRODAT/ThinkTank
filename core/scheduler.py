"""
core/scheduler.py — APScheduler setup. Triggers each department on its cron schedule.
"""
from __future__ import annotations
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.config import config

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            timezone=getattr(config.think_tank, "timezone", "UTC")
        )
    return _scheduler


def setup_scheduler():
    from core.orchestrator import run_department
    from services.email_notifier import send_draft_digest

    scheduler = get_scheduler()
    if not getattr(config.scheduler, "enabled", True):
        logger.info("Scheduler disabled in config.")
        return

    dept_schedules = config.scheduler.departments

    for dept_id in ["HF", "FIN", "RES", "ING", "STR"]:
        cron_obj = getattr(dept_schedules, dept_id, None)
        if cron_obj is None:
            continue
        cron_str = str(getattr(cron_obj, "cron", cron_obj))
        parts = cron_str.split()
        if len(parts) != 5:
            logger.warning(f"Invalid cron for {dept_id}: {cron_str}")
            continue
        minute, hour, day, month, day_of_week = parts

        async def _run(d=dept_id):
            await run_department(d)

        scheduler.add_job(
            _run,
            CronTrigger(minute=minute, hour=hour, day=day,
                        month=month, day_of_week=day_of_week),
            id=f"dept_{dept_id}",
            name=f"{dept_id} Department Cycle",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info(f"Scheduled {dept_id} → cron: {cron_str}")

    digest_hour = getattr(config.email, "digest_hour", 18)
    scheduler.add_job(
        send_draft_digest,
        CronTrigger(hour=digest_hour, minute=0),
        id="email_digest",
        name="Daily Draft Digest",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started.")
