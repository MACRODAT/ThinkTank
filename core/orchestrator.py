"""
core/orchestrator.py — Central coordinator. Manages department agents and triggers cycles.
"""
from __future__ import annotations
import logging
from typing import Dict
from departments.hf   import HFAgent
from departments.fin  import FINAgent
from departments.res  import RESAgent
from departments.ing  import INGAgent
from departments.str_ import STRAgent
from core.database import log_event
from core.draft_vault import pending_count
from services.email_notifier import send_draft_digest

logger = logging.getLogger(__name__)

AGENTS: Dict[str, object] = {
    "HF":  HFAgent(),
    "FIN": FINAgent(),
    "RES": RESAgent(),
    "ING": INGAgent(),
    "STR": STRAgent(),
}


async def run_department(dept_id: str):
    agent = AGENTS.get(dept_id)
    if not agent:
        logger.error(f"Unknown department: {dept_id}")
        return
    await agent.run_cycle()
    count = await pending_count()
    if count > 0:
        try:
            await send_draft_digest()
        except Exception as e:
            logger.warning(f"Email digest failed: {e}")


async def run_all():
    """Run all departments in strategic order: STR → RES → HF → ING → FIN."""
    order = ["STR", "RES", "HF", "ING", "FIN"]
    await log_event(None, "orchestrator_run", "Full think tank cycle started")
    for dept_id in order:
        await run_department(dept_id)
    await log_event(None, "orchestrator_run", "Full think tank cycle complete")


def get_agent(dept_id: str):
    return AGENTS.get(dept_id)
