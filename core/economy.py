"""
core/economy.py — Points economy engine for Central Think Tank.
All point transactions go through this module.
Config-driven: all cost/award values are editable via the PointsConfig page.
"""
from __future__ import annotations
import uuid, json, logging
from datetime import datetime, date
from typing import Optional
import aiosqlite
from core.database import DB_PATH

logger = logging.getLogger(__name__)

# ── Default cost table (all editable via UI) ──────────────────────────────────
_DEFAULT_COSTS: dict[str, int] = {
    "weekly_allocation":              200,
    "project_create_ceo":              50,
    "project_create_agent":           100,
    "draft_strategy_create_ceo":       80,
    "draft_strategy_create_agent":    160,
    "draft_strategy_approved":        180,   # award
    "draft_strategy_revised":           2,   # cost per edit
    "draft_strategy_rejected":         20,   # cost when scrapped
    "draft_strategy_overdue_day":       5,   # cost per day pending
    "draft_other_create":              20,
    "draft_other_approved":            40,   # award
    "draft_other_rejected_founder":    80,   # cost when founder rejects approved draft
    "draft_revision_award":             1,   # award per edit
    "founder_mail_send":               35,
    "endeavor_rejected_ceo":          125,
    "endeavor_rejected_agent":        180,
    "endeavor_approved_ceo":          150,   # award
    "endeavor_task_approved":          10,   # award
    "endeavor_task_rejected":           5,
    "agent_spawn":                     50,
    "web_search":                      10,
    "mail_ceo_to_ceo":                  1,
    "mail_ceo_to_agent":                2,
    "mail_agent_to_agent":              1,
    "mail_agent_to_ceo":               10,
    "heartbeat_agent":                  1,
    "heartbeat_ceo":                    5,
    "ceo_chat_to_founder":             20,
    "tool_check_offline":              10,
    "tool_get_time":                    2,
}

# Labels shown in the UI
COST_LABELS: dict[str, str] = {
    "weekly_allocation":              "Weekly allocation (Fridays)",
    "project_create_ceo":             "Create project (CEO)",
    "project_create_agent":           "Create project (agent)",
    "draft_strategy_create_ceo":      "Create strategy draft (CEO)",
    "draft_strategy_create_agent":    "Create strategy draft (agent)",
    "draft_strategy_approved":        "Strategy draft approved → award",
    "draft_strategy_revised":         "Strategy draft revised (per edit)",
    "draft_strategy_rejected":        "Strategy draft scrapped/rejected",
    "draft_strategy_overdue_day":     "Strategy draft overdue (per day)",
    "draft_other_create":             "Create other draft",
    "draft_other_approved":           "Other draft approved → award",
    "draft_other_rejected_founder":   "Founder rejects approved draft (cost to dept)",
    "draft_revision_award":           "Edit/revise any draft → award",
    "founder_mail_send":              "Send message to Founder",
    "endeavor_rejected_ceo":          "Endeavor rejected (CEO created)",
    "endeavor_rejected_agent":        "Endeavor rejected (agent created)",
    "endeavor_approved_ceo":          "Endeavor approved (CEO created) → award",
    "endeavor_task_approved":         "Task added to endeavor approved → award",
    "endeavor_task_rejected":         "Task added to endeavor rejected",
    "agent_spawn":                    "Spawn new agent",
    "web_search":                     "Web search call (per attempt)",
    "mail_ceo_to_ceo":                "Mail: CEO → other dept CEO (fee)",
    "mail_ceo_to_agent":              "Mail: CEO → other dept agent (fee)",
    "mail_agent_to_agent":            "Mail: agent → other dept agent (fee)",
    "mail_agent_to_ceo":              "Mail: agent → other dept CEO (fee)",
    "heartbeat_agent":                "Agent heartbeat",
    "heartbeat_ceo":                  "CEO heartbeat",
    "ceo_chat_to_founder":            "CEO initiates chat with Founder",
    "tool_check_offline":             "Tool: check_offline",
    "tool_get_time":                  "Tool: get_time",
}

# award = these events give points (positive = gain)
AWARD_EVENTS = {
    "weekly_allocation", "draft_strategy_approved", "draft_other_approved",
    "draft_revision_award", "endeavor_approved_ceo", "endeavor_task_approved",
    "mail_fee_recv", "transfer_in", "founder_award",
}


async def _load_points_config() -> dict[str, int]:
    """Load per-event costs from settings DB, merging with defaults."""
    try:
        from api.routes.settings import _load
        s   = await _load()
        raw = s.get("points_config", "{}")
        stored = json.loads(raw) if raw else {}
        merged = dict(_DEFAULT_COSTS)
        for k, v in stored.items():
            if k in merged:
                try: merged[k] = int(v)
                except: pass
        return merged
    except Exception:
        return dict(_DEFAULT_COSTS)


async def _save_points_config(cfg: dict[str, int]):
    try:
        from api.routes.settings import _load, _save
        s = await _load()
        s["points_config"] = json.dumps({k: int(v) for k, v in cfg.items()})
        await _save(s)
    except Exception as e:
        logger.error(f"Failed to save points config: {e}")


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
                id         TEXT PRIMARY KEY,
                dept_id    TEXT NOT NULL,
                event      TEXT NOT NULL,
                delta      INTEGER NOT NULL,
                balance    INTEGER NOT NULL,
                note       TEXT DEFAULT '',
                ref_id     TEXT DEFAULT '',
                agent_id   TEXT DEFAULT '',
                created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ledger_dept ON point_ledger(dept_id, created_at)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS draft_overdue_log (
                draft_id    TEXT NOT NULL,
                charged_day TEXT NOT NULL,
                PRIMARY KEY (draft_id, charged_day)
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_agents (
                id           TEXT PRIMARY KEY,
                agent_id     TEXT NOT NULL,
                seller_dept  TEXT DEFAULT 'founder',
                price        INTEGER DEFAULT 0,
                for_sale     INTEGER DEFAULT 1,
                listed_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                sold_to_dept TEXT DEFAULT '',
                sold_at      TEXT DEFAULT ''
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
                id          TEXT PRIMARY KEY,
                ext_id      TEXT NOT NULL,
                dept_id     TEXT NOT NULL,
                type        TEXT DEFAULT 'usage',
                acquired_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_allocation_log (
                week_key TEXT NOT NULL,
                dept_id  TEXT NOT NULL,
                PRIMARY KEY (week_key, dept_id)
            )""")
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dropped_files (
                id         TEXT PRIMARY KEY,
                filename   TEXT NOT NULL,
                content    TEXT DEFAULT '',
                file_type  TEXT DEFAULT '',
                summary    TEXT DEFAULT '',
                metadata   TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        # Seed initial balances
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
    """delta>0=cost(deduct), delta<0=award(gain). Returns new balance."""
    if delta == 0:
        return await get_balance(dept_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT balance FROM dept_points WHERE dept_id=?", (dept_id,)) as cur:
            row = await cur.fetchone()
        current = row["balance"] if row else 0
        new_bal = current - delta
        await db.execute(
            "INSERT OR REPLACE INTO dept_points (dept_id, balance, updated_at) VALUES (?,?,?)",
            (dept_id, new_bal, datetime.utcnow().isoformat())
        )
        await db.execute(
            "INSERT INTO point_ledger (id,dept_id,event,delta,balance,note,ref_id,agent_id) VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), dept_id, event, -delta, new_bal, note, ref_id, agent_id)
        )
        await db.commit()
    logger.info(f"[ECONOMY] {dept_id} {event} Δ={-delta} → {new_bal} | {note}")
    return new_bal


async def award(dept_id: str, event: str, points: int,
                note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    return await transact(dept_id, event, -points, note, ref_id, agent_id)


async def deduct(dept_id: str, event: str, points: int,
                 note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    """Deduct points. Raises InsufficientPointsError if balance would go below -50 (buffer for loans)."""
    bal = await get_balance(dept_id)
    # Allow slight negative (up to -50) as buffer, but block deeply negative depts
    if points > 0 and bal < 0 and event not in ("weekly_allocation", "founder_award", "transfer_in",
                                                   "loan_repayment", "loan_disbursement", "mail_fee_recv"):
        raise InsufficientPointsError(
            f"{dept_id} has {bal} pts (negative budget). Cannot spend {points} pts on '{event}'."
        )
    return await transact(dept_id, event, points, note, ref_id, agent_id)


class InsufficientPointsError(Exception):
    pass


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
    if points >= 0:
        return await award(dept_id, "founder_award", points, note or "Founder award")
    return await deduct(dept_id, "founder_deduct", -points, note or "Founder deduction")


# ── Weekly allocation ─────────────────────────────────────────────────────────

async def run_weekly_allocation():
    week_key = f"{date.today().isocalendar()[0]}-W{date.today().isocalendar()[1]}"
    cfg = await _load_points_config()
    alloc = int(cfg.get("weekly_allocation", 200))
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
                await award(dept_id, "weekly_allocation", alloc, f"Weekly allocation {week_key}")


# ── Draft overdue fee ─────────────────────────────────────────────────────────

async def run_draft_overdue_fees():
    today = date.today().isoformat()
    cfg   = await _load_points_config()
    cost  = int(cfg.get("draft_strategy_overdue_day", 5))
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
            if not already and draft.get("created_at","")[:10] < today:
                await db.execute(
                    "INSERT OR IGNORE INTO draft_overdue_log (draft_id, charged_day) VALUES (?,?)",
                    (draft["id"], today)
                )
                await db.commit()
                await deduct(draft["dept_id"], "draft_strategy_overdue_day", cost,
                             f"Overdue strategy {draft['id'][:8]}", draft["id"])


# ── Mail fee ──────────────────────────────────────────────────────────────────

async def charge_mail_fee(from_dept: str, to_dept: str,
                           from_is_ceo: bool, to_is_ceo: bool):
    if from_dept == to_dept:
        return  # intra-dept: free
    cfg = await _load_points_config()
    if from_is_ceo and to_is_ceo:
        cost = int(cfg.get("mail_ceo_to_ceo", 1))
    elif from_is_ceo:
        cost = int(cfg.get("mail_ceo_to_agent", 2))
    elif to_is_ceo:
        cost = int(cfg.get("mail_agent_to_ceo", 10))
    else:
        cost = int(cfg.get("mail_agent_to_agent", 1))
    await deduct(from_dept, "mail_fee_sent", cost, f"Mail to {to_dept}")
    await award (to_dept,   "mail_fee_recv", cost, f"Mail fee from {from_dept}")


# ── Web search ────────────────────────────────────────────────────────────────

async def log_web_search(agent_id: str, agent_name: str, dept_id: str,
                          query: str, provider: str, success: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO web_search_log (id,agent_id,agent_name,dept_id,query,provider,success) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), agent_id, agent_name, dept_id, query, provider, 1 if success else 0)
        )
        await db.commit()
    cfg = await _load_points_config()
    await deduct(dept_id, "web_search", int(cfg.get("web_search", 10)),
                 f"Web search: {query[:40]}", agent_id=agent_id)


async def get_web_search_metrics(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM web_search_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── Loans ─────────────────────────────────────────────────────────────────────

async def _ensure_loans_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS point_loans (
                id              TEXT PRIMARY KEY,
                lender_dept     TEXT NOT NULL,
                borrower_dept   TEXT NOT NULL,
                principal       INTEGER NOT NULL,
                interest_rate   REAL NOT NULL DEFAULT 0.1,
                outstanding     INTEGER NOT NULL,
                status          TEXT DEFAULT 'active',
                listed_on_market INTEGER DEFAULT 0,
                market_price    INTEGER DEFAULT 0,
                due_date        TEXT DEFAULT '',
                created_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                repaid_at       TEXT DEFAULT ''
            )""")
        # Accrue-interest log
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loan_accrual_log (
                loan_id    TEXT NOT NULL,
                accrued_on TEXT NOT NULL,
                amount     INTEGER NOT NULL,
                PRIMARY KEY (loan_id, accrued_on)
            )""")
        await db.commit()


async def create_loan(lender_dept: str, borrower_dept: str,
                       principal: int, interest_rate: float = 0.1,
                       due_date: str = "") -> str:
    """Lender gives points to borrower. Returns loan ID."""
    await _ensure_loans_table()
    # Check lender has enough
    bal = await get_balance(lender_dept)
    if bal < principal:
        raise InsufficientPointsError(f"{lender_dept} only has {bal} pts, cannot lend {principal}")
    lid = str(uuid.uuid4())
    # Transfer points
    await deduct(lender_dept, "loan_disbursement", principal, f"Loan to {borrower_dept}", lid)
    await transact(borrower_dept, "loan_received", -principal, f"Loan from {lender_dept}", lid)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO point_loans (id,lender_dept,borrower_dept,principal,interest_rate,outstanding,due_date) VALUES (?,?,?,?,?,?,?)",
            (lid, lender_dept.upper(), borrower_dept.upper(), principal, interest_rate, principal, due_date)
        )
        await db.commit()
    logger.info(f"[LOAN] {lender_dept}→{borrower_dept}: {principal} pts @ {interest_rate*100:.1f}%")
    return lid


async def repay_loan(loan_id: str, amount: int, repayer_dept: str) -> dict:
    """Partial or full repayment."""
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM point_loans WHERE id=?", (loan_id,)) as cur:
            loan = await cur.fetchone()
    if not loan: return {"error": "Loan not found"}
    loan = dict(loan)
    if loan["status"] != "active": return {"error": "Loan already closed"}
    pay  = min(amount, loan["outstanding"])
    bal  = await get_balance(repayer_dept)
    if bal < pay:
        raise InsufficientPointsError(f"Need {pay} pts to repay, have {bal}")
    await deduct(repayer_dept, "loan_repayment", pay, f"Repay loan {loan_id[:8]}", loan_id)
    await transact(loan["lender_dept"], "loan_repayment_recv", -pay, f"Repayment on loan {loan_id[:8]}", loan_id)
    new_out = loan["outstanding"] - pay
    async with aiosqlite.connect(DB_PATH) as db:
        if new_out <= 0:
            await db.execute("UPDATE point_loans SET outstanding=0, status='repaid', repaid_at=? WHERE id=?",
                             (datetime.utcnow().isoformat(), loan_id))
        else:
            await db.execute("UPDATE point_loans SET outstanding=? WHERE id=?", (new_out, loan_id))
        await db.commit()
    return {"ok": True, "paid": pay, "remaining": max(0, new_out)}


async def accrue_loan_interest():
    """Called daily. Adds interest to outstanding loans."""
    await _ensure_loans_table()
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM point_loans WHERE status='active' AND outstanding>0") as cur:
            loans = [dict(r) for r in await cur.fetchall()]
    for loan in loans:
        lid = loan["id"]
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM loan_accrual_log WHERE loan_id=? AND accrued_on=?",
                                   (lid, today)) as cur:
                already = await cur.fetchone()
            if already: continue
            interest = max(1, int(loan["outstanding"] * loan["interest_rate"] / 365))
            new_out  = loan["outstanding"] + interest
            await db.execute("INSERT OR IGNORE INTO loan_accrual_log (loan_id,accrued_on,amount) VALUES (?,?,?)",
                             (lid, today, interest))
            await db.execute("UPDATE point_loans SET outstanding=? WHERE id=?", (new_out, lid))
            await db.commit()
        # Charge borrower the accrued interest
        await deduct(loan["borrower_dept"], "loan_interest", interest,
                     f"Daily interest on loan {lid[:8]}", lid)
        await transact(loan["lender_dept"], "loan_interest_recv", -interest,
                       f"Interest on loan {lid[:8]}", lid)


async def list_loans(dept_id: str) -> list[dict]:
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM point_loans WHERE lender_dept=? OR borrower_dept=? ORDER BY created_at DESC",
            (dept_id.upper(), dept_id.upper())
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_loan_summary(dept_id: str) -> str:
    loans = await list_loans(dept_id)
    borrowed = sum(l["outstanding"] for l in loans if l["borrower_dept"] == dept_id and l["status"] == "active")
    lent     = sum(l["outstanding"] for l in loans if l["lender_dept"]   == dept_id and l["status"] == "active")
    parts = []
    if borrowed: parts.append(f"Owe {borrowed} pts")
    if lent:     parts.append(f"Lent out {lent} pts")
    return ", ".join(parts) if parts else "No active loans"


async def list_market_loans() -> list[dict]:
    """Loans listed on the marketplace."""
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM point_loans WHERE listed_on_market=1 AND status='active' ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
