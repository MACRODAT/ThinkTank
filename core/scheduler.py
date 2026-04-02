"""
core/scheduler.py — APScheduler setup. Triggers each department on its cron schedule.
"""
from __future__ import annotations
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.config import config

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        tz = getattr(config.think_tank, "timezone", "UTC")
        _scheduler = AsyncIOScheduler(timezone=tz)
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
        # dept_schedules.HF is a DotDict with a .cron attribute
        dept_cfg = getattr(dept_schedules, dept_id, None)
        if dept_cfg is None:
            logger.warning(f"No schedule config for {dept_id}, skipping.")
            continue

        # Handle both DotDict (has .cron) and plain string
        if hasattr(dept_cfg, "cron"):
            cron_str = str(dept_cfg.cron)
        else:
            cron_str = str(dept_cfg)

        parts = cron_str.strip().split()
        if len(parts) != 5:
            logger.warning(f"Invalid cron expression for {dept_id}: '{cron_str}'")
            continue

        minute, hour, day, month, day_of_week = parts

        # Use default-argument capture to avoid closure-over-loop-variable bug
        def make_job(d):
            async def _run():
                await run_department(d)
            return _run

        scheduler.add_job(
            make_job(dept_id),
            CronTrigger(
                minute=minute, hour=hour,
                day=day, month=month, day_of_week=day_of_week,
            ),
            id=f"dept_{dept_id}",
            name=f"{dept_id} Department Cycle",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info(f"Scheduled {dept_id} → {cron_str}")

    # Daily email digest
    digest_hour = int(getattr(config.email, "digest_hour", 18))
    scheduler.add_job(
        send_draft_digest,
        CronTrigger(hour=digest_hour, minute=0),
        id="email_digest",
        name="Daily Draft Digest",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started.")
