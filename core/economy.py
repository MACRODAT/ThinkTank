"""
core/economy.py — Points economy engine for Central Think Tank.
Config-driven: all cost/award values editable via UI.
"""
from __future__ import annotations
import uuid, json, logging
from datetime import datetime, date
from typing import Optional
import aiosqlite
from core.database import DB_PATH

logger = logging.getLogger(__name__)

# ── Default cost table ────────────────────────────────────────────────────────
_DEFAULT_COSTS: dict[str, int] = {
    "weekly_allocation":              200,
    "project_create_ceo":              50,
    "project_create_agent":           100,
    "draft_strategy_create_ceo":       80,
    "draft_strategy_create_agent":    160,
    "draft_strategy_approved":        180,
    "draft_strategy_revised":           2,
    "draft_strategy_rejected":         20,
    "draft_strategy_overdue_day":       5,
    "draft_other_create":              20,
    "draft_other_approved":            40,
    "draft_other_rejected_founder":    80,
    "draft_revision_award":             1,
    "founder_mail_send":               35,
    "endeavor_rejected_ceo":          125,
    "endeavor_rejected_agent":        180,
    "endeavor_approved_ceo":          150,
    "endeavor_task_approved":          10,
    "endeavor_task_rejected":           5,
    "agent_spawn":                     50,
    "web_search":                      10,
    "mail_ceo_to_ceo":                  1,
    "mail_ceo_to_agent":                2,
    "mail_agent_to_agent":              1,
    "mail_agent_to_ceo":               10,
    "mail_send":                        1,
    "mail_receive":                    -1,
    "heartbeat_agent":                  1,
    "heartbeat_ceo":                    5,
    "ceo_chat_to_founder":             20,
    "tool_check_offline":              10,
    "tool_get_time":                    2,
}

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
    "draft_other_rejected_founder":   "Founder rejects approved draft",
    "draft_revision_award":           "Edit/revise any draft → award",
    "founder_mail_send":              "Send message to Founder",
    "endeavor_rejected_ceo":          "Endeavor rejected (CEO created)",
    "endeavor_rejected_agent":        "Endeavor rejected (agent created)",
    "endeavor_approved_ceo":          "Endeavor approved (CEO created) → award",
    "endeavor_task_approved":         "Task added to endeavor approved → award",
    "endeavor_task_rejected":         "Task added to endeavor rejected",
    "agent_spawn":                    "Spawn new agent",
    "web_search":                     "Web search call (per attempt)",
    "mail_ceo_to_ceo":                "Mail: CEO → other dept CEO",
    "mail_ceo_to_agent":              "Mail: CEO → other dept agent",
    "mail_agent_to_agent":            "Mail: agent → other dept agent",
    "mail_agent_to_ceo":              "Mail: agent → other dept CEO",
    "mail_send":                      "Send any mail (base cost)",
    "mail_receive":                   "Receive mail (credit)",
    "heartbeat_agent":                "Agent heartbeat",
    "heartbeat_ceo":                  "CEO heartbeat",
    "ceo_chat_to_founder":            "CEO initiates chat with Founder",
    "tool_check_offline":             "Tool: check_offline",
    "tool_get_time":                  "Tool: get_time",
}

AWARD_EVENTS = {
    "weekly_allocation", "draft_strategy_approved", "draft_other_approved",
    "draft_revision_award", "endeavor_approved_ceo", "endeavor_task_approved",
    "mail_fee_recv", "transfer_in", "founder_award",
    "loan_received", "loan_repayment_recv", "loan_interest_recv", "loan_offer_return",
}


class InsufficientPointsError(Exception):
    pass


async def _load_points_config() -> dict[str, int]:
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


# ── DB init ───────────────────────────────────────────────────────────────────

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
                seller_dept  TEXT NOT NULL DEFAULT 'founder',
                price        INTEGER DEFAULT 0,
                for_sale     INTEGER DEFAULT 1,
                listed_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                sold_to_dept TEXT DEFAULT '',
                sold_at      TEXT DEFAULT ''
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS marketplace_extensions (
                id               TEXT PRIMARY KEY,
                ext_id           TEXT NOT NULL,
                ext_name         TEXT NOT NULL,
                owner_dept       TEXT NOT NULL,
                price_ownership  INTEGER DEFAULT 0,
                price_usage      INTEGER DEFAULT 0,
                description      TEXT DEFAULT '',
                for_sale         INTEGER DEFAULT 1,
                flash_expires    TEXT DEFAULT '',
                listed_at        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ext_ownership (
                id          TEXT PRIMARY KEY,
                ext_id      TEXT NOT NULL,
                dept_id     TEXT NOT NULL,
                type        TEXT DEFAULT 'usage',
                acquired_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                UNIQUE(ext_id, dept_id)
            )""")
        await db.commit()
    # Loans tables via separate migration
    await _ensure_loans_table()


# ── Core transaction ──────────────────────────────────────────────────────────

async def transact(dept_id: str, event: str, delta: int,
                   note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT OR IGNORE INTO dept_points (dept_id, balance) VALUES (?,0)",
            (dept_id.upper(),)
        )
        async with db.execute("SELECT balance FROM dept_points WHERE dept_id=?", (dept_id.upper(),)) as cur:
            row = await cur.fetchone()
        cur_bal = row["balance"] if row else 0
        new_bal = cur_bal - delta
        await db.execute(
            "UPDATE dept_points SET balance=?, updated_at=? WHERE dept_id=?",
            (new_bal, datetime.utcnow().isoformat(), dept_id.upper())
        )
        lid = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO point_ledger (id,dept_id,event,delta,balance,note,ref_id,agent_id) VALUES (?,?,?,?,?,?,?,?)",
            (lid, dept_id.upper(), event, -delta, new_bal, note, ref_id, agent_id)
        )
        await db.commit()
    logger.info(f"[ECONOMY] {dept_id} {event} Δ={-delta} → {new_bal} | {note}")
    return new_bal


async def deduct(dept_id: str, event: str, points: int,
                 note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    """Deduct points. Raises InsufficientPointsError if balance < -50 (buffer for loans)."""
    if dept_id.upper() == "FOUNDER":
        return 0
    bal = await get_balance(dept_id)
    # Exempt certain repayment events from the check
    if (bal - points) < -50 and event not in (
        "loan_repayment", "loan_disbursement", "loan_interest",
        "mail_fee_recv", "transfer_out",
    ):
        raise InsufficientPointsError(
            f"{dept_id} insufficient points: has {bal}, needs {points} for '{event}'"
        )
    return await transact(dept_id, event, points, note, ref_id, agent_id)


async def award(dept_id: str, event: str, points: int,
                note: str = "", ref_id: str = "", agent_id: str = "") -> int:
    return await transact(dept_id, event, -points, note, ref_id, agent_id)


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


async def get_web_search_metrics(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM point_ledger WHERE event='web_search' ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


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
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM point_ledger WHERE dept_id=? AND event='weekly_allocation' AND note LIKE ?",
                (dept_id, f"%{week_key}%")
            ) as cur:
                already = await cur.fetchone()
        if not already:
            await award(dept_id, "weekly_allocation", alloc, f"Weekly allocation {week_key}")
            logger.info(f"[ECONOMY] Weekly allocation: {dept_id} +{alloc}")


# ── Loans ─────────────────────────────────────────────────────────────────────

async def _ensure_loans_table():
    async with aiosqlite.connect(DB_PATH) as db:
        # Directed loans (lender → specific borrower, immediate disbursement)
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
        # Open loan OFFERS on the market — no borrower yet
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loan_offers (
                id             TEXT PRIMARY KEY,
                lender_dept    TEXT NOT NULL,
                principal      INTEGER NOT NULL,
                interest_rate  REAL NOT NULL DEFAULT 0.1,
                due_days       INTEGER DEFAULT 30,
                description    TEXT DEFAULT '',
                status         TEXT DEFAULT 'open',
                borrower_dept  TEXT DEFAULT '',
                loan_id        TEXT DEFAULT '',
                created_at     TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                accepted_at    TEXT DEFAULT '',
                retracted_at   TEXT DEFAULT ''
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loan_accrual_log (
                loan_id    TEXT NOT NULL,
                accrued_on TEXT NOT NULL,
                amount     INTEGER NOT NULL,
                PRIMARY KEY (loan_id, accrued_on)
            )""")
        # Migrations for existing installations
        for sql in [
            "ALTER TABLE loan_offers ADD COLUMN description TEXT DEFAULT ''",
        ]:
            try:
                await db.execute(sql)
            except Exception:
                pass
        await db.commit()


# ── Directed loan (lender → specific borrower immediately) ────────────────────

async def create_loan(lender_dept: str, borrower_dept: str,
                       principal: int, interest_rate: float = 0.1,
                       due_date: str = "") -> str:
    """Lender gives points directly to borrower. Returns loan ID."""
    await _ensure_loans_table()
    if lender_dept.upper() != "FOUNDER":
        bal = await get_balance(lender_dept)
        if bal < principal:
            raise InsufficientPointsError(f"{lender_dept} only has {bal} pts, cannot lend {principal}")
        await deduct(lender_dept, "loan_disbursement", principal, f"Loan to {borrower_dept}")
    await transact(borrower_dept, "loan_received", -principal, f"Loan from {lender_dept}")
    lid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO point_loans (id,lender_dept,borrower_dept,principal,interest_rate,outstanding,due_date) VALUES (?,?,?,?,?,?,?)",
            (lid, lender_dept.upper(), borrower_dept.upper(), principal, interest_rate, principal, due_date)
        )
        await db.commit()
    logger.info(f"[LOAN] {lender_dept}→{borrower_dept}: {principal} pts @ {interest_rate*100:.1f}%")
    return lid


# ── Open loan offer (posted to market, no borrower yet) ───────────────────────

async def create_loan_offer(
    lender_dept:   str,
    principal:     int,
    interest_rate: float = 0.10,
    due_days:      int   = 30,
    description:   str   = "",
) -> str:
    """
    Post an open loan offer to the market. Capital is deducted from lender
    (held in escrow) unless lender is FOUNDER.
    Returns offer ID.
    """
    await _ensure_loans_table()
    # Deduct capital from lender (held until accepted or retracted)
    if lender_dept.upper() != "FOUNDER":
        bal = await get_balance(lender_dept)
        if bal < principal:
            raise InsufficientPointsError(
                f"{lender_dept} only has {bal} pts, cannot offer loan of {principal}"
            )
        await deduct(lender_dept, "loan_offer_escrow", principal,
                     f"Loan offer escrow {principal} pts @ {interest_rate*100:.1f}%")

    oid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO loan_offers (id,lender_dept,principal,interest_rate,due_days,description) VALUES (?,?,?,?,?,?)",
            (oid, lender_dept.upper(), principal, interest_rate, due_days, description)
        )
        await db.commit()
    logger.info(f"[LOAN OFFER] {lender_dept}: {principal} pts @ {interest_rate*100:.1f}% for {due_days}d")
    return oid


async def retract_loan_offer(offer_id: str) -> dict:
    """Cancel an open offer and return capital to lender."""
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM loan_offers WHERE id=?", (offer_id,)) as cur:
            offer = await cur.fetchone()
    if not offer:
        return {"error": "Offer not found"}
    offer = dict(offer)
    if offer["status"] != "open":
        return {"error": f"Offer is already {offer['status']}"}

    # Return escrow to lender
    if offer["lender_dept"].upper() != "FOUNDER":
        await award(offer["lender_dept"], "loan_offer_return", offer["principal"],
                    f"Loan offer retracted — capital returned")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE loan_offers SET status='retracted', retracted_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), offer_id)
        )
        await db.commit()
    return {"ok": True, "returned": offer["principal"], "to": offer["lender_dept"]}


async def accept_loan_offer(offer_id: str, borrower_dept: str) -> dict:
    """
    Accept an open loan offer. Capital is transferred from escrow → borrower.
    A normal loan record is created for repayment tracking.
    """
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM loan_offers WHERE id=? AND status='open'", (offer_id,)) as cur:
            offer = await cur.fetchone()
    if not offer:
        return {"error": "Offer not found or already taken"}
    offer = dict(offer)

    if borrower_dept.upper() == offer["lender_dept"].upper():
        return {"error": "Cannot borrow from yourself"}

    # Create the loan (no deduction from lender — already in escrow)
    lid = str(uuid.uuid4())
    from datetime import timedelta
    due_date = (datetime.utcnow() + timedelta(days=offer["due_days"])).date().isoformat()

    # Credit borrower — escrow is already gone from lender
    await transact(borrower_dept, "loan_received", -offer["principal"],
                   f"Loan accepted from {offer['lender_dept']} (offer {offer_id[:8]})")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO point_loans (id,lender_dept,borrower_dept,principal,interest_rate,outstanding,due_date) VALUES (?,?,?,?,?,?,?)",
            (lid, offer["lender_dept"].upper(), borrower_dept.upper(),
             offer["principal"], offer["interest_rate"], offer["principal"], due_date)
        )
        await db.execute(
            "UPDATE loan_offers SET status='accepted', borrower_dept=?, loan_id=?, accepted_at=? WHERE id=?",
            (borrower_dept.upper(), lid, datetime.utcnow().isoformat(), offer_id)
        )
        await db.commit()

    logger.info(f"[LOAN OFFER ACCEPTED] {offer['lender_dept']}→{borrower_dept}: {offer['principal']} pts")
    return {"ok": True, "loan_id": lid, "principal": offer["principal"], "due_date": due_date}


async def list_loan_offers(status: str = "open") -> list[dict]:
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status == "all":
            async with db.execute("SELECT * FROM loan_offers ORDER BY created_at DESC") as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM loan_offers WHERE status=? ORDER BY created_at DESC", (status,)
            ) as cur:
                rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── Directed loan repayment ───────────────────────────────────────────────────

async def repay_loan(loan_id: str, amount: int, repayer_dept: str) -> dict:
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM point_loans WHERE id=?", (loan_id,)) as cur:
            loan = await cur.fetchone()
    if not loan: return {"error": "Loan not found"}
    loan = dict(loan)
    if loan["status"] != "active": return {"error": "Loan already closed"}
    pay = min(amount, loan["outstanding"])
    bal = await get_balance(repayer_dept)
    if bal < pay:
        raise InsufficientPointsError(f"Need {pay} pts to repay, have {bal}")
    await deduct(repayer_dept, "loan_repayment", pay, f"Repay loan {loan_id[:8]}", loan_id)
    await transact(loan["lender_dept"], "loan_repayment_recv", -pay, f"Repayment on {loan_id[:8]}", loan_id)
    new_out = loan["outstanding"] - pay
    async with aiosqlite.connect(DB_PATH) as db:
        if new_out <= 0:
            await db.execute(
                "UPDATE point_loans SET outstanding=0, status='repaid', repaid_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), loan_id)
            )
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
            async with db.execute(
                "SELECT 1 FROM loan_accrual_log WHERE loan_id=? AND accrued_on=?", (lid, today)
            ) as cur:
                already = await cur.fetchone()
            if already: continue
            interest = max(1, int(loan["outstanding"] * loan["interest_rate"] / 365))
            new_out  = loan["outstanding"] + interest
            await db.execute(
                "INSERT OR IGNORE INTO loan_accrual_log (loan_id,accrued_on,amount) VALUES (?,?,?)",
                (lid, today, interest)
            )
            await db.execute("UPDATE point_loans SET outstanding=? WHERE id=?", (new_out, lid))
            await db.commit()
        await deduct(loan["borrower_dept"], "loan_interest", interest,
                     f"Daily interest on {lid[:8]}", lid)
        await transact(loan["lender_dept"], "loan_interest_recv", -interest,
                       f"Interest on {lid[:8]}", lid)


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
    await _ensure_loans_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM point_loans WHERE listed_on_market=1 AND status='active' ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
