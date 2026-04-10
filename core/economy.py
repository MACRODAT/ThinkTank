"""
core/economy.py — Points economy engine for Central Think Tank.
All point transactions go through this module.
"""
from __future__ import annotations
import uuid, logging
from datetime import datetime, date
from typing import Optional
import aiosqlite
from core.database import DB_PATH

logger = logging.getLogger(__name__)

# ── Point costs/awards table ──────────────────────────────────────────────────
COSTS = {
    # Drafts
    "draft_strategy_create_ceo":     80,
    "draft_strategy_create_agent":  160,
    "draft_strategy_approved":     -180,   # award (negative = gain)
    "draft_strategy_revised":         2,   # per edit
    "draft_strategy_rejected":       20,   # scrapped
    "draft_strategy_overdue_day":     5,   # per day unapproved
    "draft_other_create":            20,
    "draft_other_approved":          -2,   # award
    "draft_other_rejected_by_founder":80,
    "draft_revision_award":          -1,   # award per edit on any draft
    # Projects
    "project_create_ceo":            50,
    "project_create_agent":         100,
    # Founder mail
    "founder_mail_send":             35,
    # Endeavors
    "endeavor_rejected_ceo":        125,
    "endeavor_rejected_agent":      180,
    "endeavor_approved_ceo":       -150,   # award
    "endeavor_task_approved":       -10,   # award
    "endeavor_task_rejected":         5,
    # Agents
    "agent_spawn":                   50,
    "agent_hire_marketplace":         0,   # price varies
    # Web search
    "web_search":                    10,
    # Mail (inter-dept only)
    "mail_ceo_to_ceo":                1,
    "mail_ceo_to_agent":              2,
    "mail_agent_to_agent":            1,
    "mail_agent_to_ceo":             10,
    # Heartbeats
    "heartbeat_agent":                1,
    "heartbeat_ceo":                  5,
    # CEO conversation with Founder
    "ceo_chat_to_founder":           20,
    # Tools
    "tool_check_offline":            10,
    "tool_get_time":                  2,
    # Weekly allocation (negative = gain)
    "weekly_allocation":           -200,
}


# ── DB initialisation ─────────────────────────────────────────────────────────

async def init_economy_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dept_points (
                dept_id    TEXT PRIMARY KEY,
                balance    INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS point_ledger (
                id          TEXT PRIMARY KEY,
                dept_id     TEXT NOT NULL,
                event       TEXT NOT NULL,
                delta       INTEGER NOT NULL,
                balance     INTEGER NOT NULL,
                note        TEXT DEFAULT '',
                ref_id      TEXT DEFAULT '',
                agent_id    TEXT DEFAULT '',
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ledger_dept ON point_ledger(dept_id, created_at)")
        # Track which drafts already had their overdue fee charged per day
        await db.execute("""
            CREATE TABLE IF NOT EXISTS draft_overdue_log (
                draft_id    TEXT NOT NULL,
                charged_day TEXT NOT NULL,
                PRIMARY KEY (draft_id, charged_day)
            )""")
        # Marketplace
        await db.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_agents (
                id            TEXT PRIMARY KEY,
                agent_id      TEXT NOT NULL,
                seller_dept   TEXT DEFAULT 'founder',
                price         INTEGER DEFAULT 0,
                for_sale      INTEGER DEFAULT 1,
                listed_at     TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                sold_to_dept  TEXT DEFAULT '',
                sold_at       TEXT DEFAULT ''
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_extensions (
                id              TEXT PRIMARY KEY,
                ext_id          TEXT NOT NULL,
                ext_name        TEXT NOT NULL,
                owner_dept      TEXT NOT NULL,
                price_ownership INTEGER DEFAULT 0,
                price_usage     INTEGER DEFAULT 0,
                for_sale        INTEGER DEFAULT 1,
                listed_at       TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                flash_expires   TEXT DEFAULT '',
                description     TEXT DEFAULT ''
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ext_ownership (
                id         TEXT PRIMARY KEY,
                ext_id     TEXT NOT NULL,
                dept_id    TEXT NOT NULL,
                type       TEXT DEFAULT 'usage',
                acquired_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        # Weekly allocation log so we don't double-allocate
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_allocation_log (
                week_key TEXT NOT NULL,
                dept_id  TEXT NOT NULL,
                PRIMARY KEY (week_key, dept_id)
            )""")
        # Web search metrics
        await db.execute("""
            CREATE TABLE IF NOT EXISTS web_search_log (
                id         TEXT PRIMARY KEY,
                agent_id   TEXT DEFAULT '',
                agent_name TEXT DEFAULT '',
                dept_id    TEXT DEFAULT '',
                query      TEXT DEFAULT '',
                provider   TEXT DEFAULT '',
                success    INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        # File drops
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dropped_files (
                id          TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                content     TEXT DEFAULT '',
                file_type   TEXT DEFAULT '',
                summary     TEXT DEFAULT '',
                metadata    TEXT DEFAULT '{}',
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        # Seed initial balances for all departments
        try:
            async with db.execute("SELECT id FROM departments") as cur:
                depts = [row[0] for row in await cur.fetchall()]
            for dept_id in depts:
                await db.execute(
                    "INSERT OR IGNORE INTO dept_points (dept_id, balance) VALUES (?,?)",
                    (dept_id, 200)
                )
        except Exception:
            pass
        await db.commit()


# ── Core transaction ──────────────────────────────────────────────────────────

async def transact(dept_id: str, event: str, delta: int = 0,
                   note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    """
    Apply delta to dept balance. delta>0 = cost/deduct, delta<0 = award/gain.
    Returns new balance. Logs to ledger.
    """
    if delta == 0:
        return await get_balance(dept_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT balance FROM dept_points WHERE dept_id=?", (dept_id,)
        ) as cur:
            row = await cur.fetchone()
        current = row["balance"] if row else 0
        new_bal = current - delta  # delta>0 means cost → subtract
        await db.execute(
            "INSERT OR REPLACE INTO dept_points (dept_id, balance, updated_at) VALUES (?,?,?)",
            (dept_id, new_bal, datetime.utcnow().isoformat())
        )
        await db.execute(
            "INSERT INTO point_ledger (id,dept_id,event,delta,balance,note,ref_id,agent_id) VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), dept_id, event, -delta, new_bal, note, ref_id, agent_id)
        )
        await db.commit()
    logger.info(f"[ECONOMY] {dept_id} {event} delta={-delta} → balance={new_bal} | {note}")
    return new_bal


async def award(dept_id: str, event: str, points: int,
                note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    """Award points (positive number = gain)."""
    return await transact(dept_id, event, -points, note, ref_id, agent_id)


async def deduct(dept_id: str, event: str, points: int,
                 note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    """Deduct points (positive number = cost)."""
    return await transact(dept_id, event, points, note, ref_id, agent_id)


async def get_balance(dept_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT balance FROM dept_points WHERE dept_id=?", (dept_id,)) as cur:
            row = await cur.fetchone()
    return row["balance"] if row else 0


async def get_all_balances() -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT dept_id, balance FROM dept_points ORDER BY balance DESC") as cur:
            rows = await cur.fetchall()
    return {r["dept_id"]: r["balance"] for r in rows}


async def get_ledger(dept_id: str, limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM point_ledger WHERE dept_id=? ORDER BY created_at DESC LIMIT ?",
            (dept_id, limit)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def founder_adjust(dept_id: str, points: int, note: str = "") -> int:
    """Founder manual adjustment. Positive = award, negative = deduct."""
    if points >= 0:
        return await award(dept_id, "founder_award", points, note or "Founder award")
    else:
        return await deduct(dept_id, "founder_deduct", -points, note or "Founder deduction")


# ── Weekly allocation ─────────────────────────────────────────────────────────

async def run_weekly_allocation():
    """Called every Friday at 22:00. Awards 200 points to each dept."""
    week_key = f"{date.today().isocalendar()[0]}-W{date.today().isocalendar()[1]}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM departments WHERE active=1") as cur:
            depts = [row[0] for row in await cur.fetchall()]
        for dept_id in depts:
            async with db.execute(
                "SELECT 1 FROM weekly_allocation_log WHERE week_key=? AND dept_id=?",
                (week_key, dept_id)
            ) as cur:
                already = await cur.fetchone()
            if not already:
                await db.execute(
                    "INSERT OR IGNORE INTO weekly_allocation_log (week_key, dept_id) VALUES (?,?)",
                    (week_key, dept_id)
                )
                await db.commit()
                await award(dept_id, "weekly_allocation", 200, f"Weekly allocation {week_key}")


# ── Draft overdue fee ─────────────────────────────────────────────────────────

async def run_draft_overdue_fees():
    """Called daily. Charges 5 pts/day for pending strategy drafts."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id,dept_id,created_at FROM drafts WHERE draft_type='strategy' AND status='pending'"
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
        for draft in rows:
            async with db.execute(
                "SELECT 1 FROM draft_overdue_log WHERE draft_id=? AND charged_day=?",
                (draft["id"], today)
            ) as cur:
                already = await cur.fetchone()
            if not already:
                created = draft.get("created_at","")[:10]
                if created < today:  # Only if older than today
                    await db.execute(
                        "INSERT OR IGNORE INTO draft_overdue_log (draft_id, charged_day) VALUES (?,?)",
                        (draft["id"], today)
                    )
                    await db.commit()
                    await deduct(draft["dept_id"], "draft_strategy_overdue_day", 5,
                                 f"Overdue strategy draft {draft['id'][:8]}", draft["id"])


# ── Mail fee helper ───────────────────────────────────────────────────────────

async def charge_mail_fee(from_dept: str, to_dept: str,
                           from_is_ceo: bool, to_is_ceo: bool):
    """Charge sender and award receiver for inter-dept mail."""
    if from_dept == to_dept:
        return  # Intra-dept: free
    if from_is_ceo and to_is_ceo:
        cost = COSTS["mail_ceo_to_ceo"]
    elif from_is_ceo and not to_is_ceo:
        cost = COSTS["mail_ceo_to_agent"]
    elif not from_is_ceo and to_is_ceo:
        cost = COSTS["mail_agent_to_ceo"]
    else:
        cost = COSTS["mail_agent_to_agent"]
    await deduct(from_dept, "mail_fee_sent",  cost, f"Mail to {to_dept}")
    await award (to_dept,   "mail_fee_recv",  cost, f"Mail fee from {from_dept}")


# ── Web search log ────────────────────────────────────────────────────────────

async def log_web_search(agent_id: str, agent_name: str, dept_id: str,
                          query: str, provider: str, success: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO web_search_log (id,agent_id,agent_name,dept_id,query,provider,success) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), agent_id, agent_name, dept_id, query, provider, 1 if success else 0)
        )
        await db.commit()
    await deduct(dept_id, "web_search", COSTS["web_search"],
                 f"Web search: {query[:40]}", agent_id=agent_id)


async def get_web_search_metrics(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM web_search_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
