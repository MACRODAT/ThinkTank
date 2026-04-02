"""
core/orchestrator.py — Central coordinator. Manages department agents and triggers cycles.

Agents are instantiated lazily to avoid circular imports during database seeding.
"""
from __future__ import annotations
import logging
from typing import Dict, Optional

from core.database import log_event
from core.draft_vault import pending_count
from services.email_notifier import send_draft_digest

logger = logging.getLogger(__name__)

# Lazy agent registry — populated on first use
_agents: Dict[str, object] = {}


def _get_agents() -> Dict[str, object]:
    """Import and instantiate department agents on first call."""
    global _agents
    if not _agents:
        from departments.hf   import HFAgent
        from departments.fin  import FINAgent
        from departments.res  import RESAgent
        from departments.ing  import INGAgent
        from departments.str_ import STRAgent
        _agents = {
            "HF":  HFAgent(),
            "FIN": FINAgent(),
            "RES": RESAgent(),
            "ING": INGAgent(),
            "STR": STRAgent(),
        }
    return _agents


async def run_department(dept_id: str):
    """Run a single department's autonomous cycle."""
    agents = _get_agents()
    agent = agents.get(dept_id.upper())
    if not agent:
        logger.error(f"Unknown department: {dept_id}")
        return
    await agent.run_cycle()
    # Notify after each cycle if drafts are waiting
    count = await pending_count()
    if count > 0:
        try:
            await send_draft_digest()
        except Exception as e:
            logger.warning(f"Email digest failed: {e}")


async def run_all():
    """Run all departments in strategic order: STR → RES → HF → ING → FIN."""
    await log_event(None, "orchestrator_run", "Full think tank cycle started")
    for dept_id in ["STR", "RES", "HF", "ING", "FIN"]:
        await run_department(dept_id)
    await log_event(None, "orchestrator_run", "Full think tank cycle complete")


def get_agent(dept_id: str) -> Optional[object]:
    return _get_agents().get(dept_id.upper())
