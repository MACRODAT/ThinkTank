"""core/agent_scheduler.py — Heartbeat scheduler for all active agents."""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional
import aiosqlite
from core.database import DB_PATH

logger = logging.getLogger(__name__)

# Global state visible to the API
heartbeat_state = {
    "current_agent_id":   None,
    "current_agent_name": None,
    "current_started_at": None,
    "next_agent_id":      None,
    "next_agent_name":    None,
    "queue":              [],          # [{id, name, dept_id, scheduled_at}]
    "history":            [],          # last 20 completions
    "tick":               0,
}

_scheduler_task: Optional[asyncio.Task] = None
_TICK_SECONDS = 10          # 1 heartbeat tick = 10 real seconds


async def _load_due_agents(tick: int):
    """Return agents whose heartbeat_interval divides the current tick."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, name, dept_id, heartbeat_interval, title, role
            FROM agents WHERE status='active'
            ORDER BY is_ceo DESC, heartbeat_interval ASC
        """) as cur:
            all_agents = [dict(r) for r in await cur.fetchall()]

    due = []
    for a in all_agents:
        interval = max(1, a["heartbeat_interval"])
        if tick % interval == 0:
            due.append(a)
    return due


async def _run_one(agent: dict):
    """Run one agent heartbeat and update global state."""
    from core.agent_runner import run_agent_heartbeat

    heartbeat_state["current_agent_id"]   = agent["id"]
    heartbeat_state["current_agent_name"] = agent["name"]
    heartbeat_state["current_started_at"] = datetime.utcnow().isoformat()

    try:
        result = await run_agent_heartbeat(agent["id"])
        entry = {
            "agent_id":   agent["id"],
            "agent_name": agent["name"],
            "dept_id":    agent["dept_id"],
            "ran_at":     datetime.utcnow().isoformat(),
            "ok":         result.get("ok", False),
            "summary":    result.get("summary", ""),
            "actions":    result.get("actions_taken", []),
        }
    except Exception as e:
        logger.error(f"Scheduler: heartbeat failed for {agent['name']}: {e}")
        entry = {
            "agent_id":   agent["id"],
            "agent_name": agent["name"],
            "dept_id":    agent["dept_id"],
            "ran_at":     datetime.utcnow().isoformat(),
            "ok":         False,
            "summary":    str(e),
            "actions":    [],
        }

    # Prepend to history (keep last 30)
    heartbeat_state["history"].insert(0, entry)
    if len(heartbeat_state["history"]) > 30:
        heartbeat_state["history"].pop()

    heartbeat_state["current_agent_id"]   = None
    heartbeat_state["current_agent_name"] = None
    heartbeat_state["current_started_at"] = None


async def _scheduler_loop():
    """Main loop: every TICK_SECONDS, find due agents and run them sequentially."""
    logger.info("🤖 Agent heartbeat scheduler started")
    while True:
        await asyncio.sleep(_TICK_SECONDS)
        heartbeat_state["tick"] += 1
        tick = heartbeat_state["tick"]

        try:
            due = await _load_due_agents(tick)
            if not due:
                continue

            # Build queue for UI visibility
            heartbeat_state["queue"] = [
                {"id": a["id"], "name": a["name"], "dept_id": a["dept_id"]}
                for a in due
            ]

            for i, agent in enumerate(due):
                # Show next
                if i + 1 < len(due):
                    nxt = due[i + 1]
                    heartbeat_state["next_agent_id"]   = nxt["id"]
                    heartbeat_state["next_agent_name"] = nxt["name"]
                else:
                    heartbeat_state["next_agent_id"]   = None
                    heartbeat_state["next_agent_name"] = None

                await _run_one(agent)
                # Small gap between agents to avoid hammering the AI
                await asyncio.sleep(2)

            heartbeat_state["queue"] = []

        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")


def start_agent_scheduler():
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        loop = asyncio.get_event_loop()
        _scheduler_task = loop.create_task(_scheduler_loop())
        logger.info("✓ Agent scheduler task created")
