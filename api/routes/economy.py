"""api/routes/economy.py — Points economy + marketplace API."""
from __future__ import annotations
import uuid, json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Request
import aiosqlite
from core.database import DB_PATH
from core.economy import (
    get_balance, get_all_balances, get_ledger,
    founder_adjust, award, deduct, transact,
    get_web_search_metrics,
    _load_points_config, _save_points_config,
    _DEFAULT_COSTS, COST_LABELS, AWARD_EVENTS,
    create_loan, repay_loan, list_loans, list_market_loans,
    create_loan_offer, retract_loan_offer, accept_loan_offer, list_loan_offers,
    get_loan_summary, InsufficientPointsError,
)

router = APIRouter(tags=["economy"])


# ── Balances ──────────────────────────────────────────────────────────────────

@router.get("/api/economy/balances")
async def all_balances():
    return await get_all_balances()


@router.get("/api/economy/balance/{dept_id}")
async def dept_balance(dept_id: str):
    bal = await get_balance(dept_id.upper())
    return {"dept_id": dept_id.upper(), "balance": bal}


@router.get("/api/economy/ledger/{dept_id}")
async def dept_ledger(dept_id: str, limit: int = 100):
    return await get_ledger(dept_id.upper(), limit)


@router.post("/api/economy/adjust")
async def manual_adjust(
    dept_id: str = Body(...),
    points:  int = Body(...),
    note:    str = Body(""),
):
    """Founder manual award/deduct."""
    new_bal = await founder_adjust(dept_id.upper(), points, note)
    return {"ok": True, "dept_id": dept_id.upper(), "new_balance": new_bal}


@router.post("/api/economy/transfer")
async def transfer_points(
    from_dept: str = Body(...),
    to_dept:   str = Body(...),
    points:    int = Body(...),
    note:      str = Body(""),
):
    """CEO-to-CEO point transfer (approved by provider dept)."""
    if points <= 0:
        return {"error": "Points must be positive"}
    bal = await get_balance(from_dept.upper())
    if bal < points:
        return {"error": f"Insufficient points: {bal} < {points}"}
    await deduct(from_dept.upper(), "transfer_out", points, f"Transfer to {to_dept}: {note}")
    await award (to_dept.upper(),   "transfer_in",  points, f"Transfer from {from_dept}: {note}")
    return {"ok": True,
            "from_balance": await get_balance(from_dept.upper()),
            "to_balance":   await get_balance(to_dept.upper())}


# ── Web search metrics ────────────────────────────────────────────────────────

@router.get("/api/economy/search-metrics")
async def search_metrics(limit: int = 100):
    return await get_web_search_metrics(limit)


# ── Points config ─────────────────────────────────────────────────────

@router.get("/api/economy/config")
async def get_points_config():
    cfg = await _load_points_config()
    return {
        "config": cfg,
        "defaults": _DEFAULT_COSTS,
        "labels": COST_LABELS,
        "award_events": list(AWARD_EVENTS),
    }


@router.post("/api/economy/config")
async def save_points_config(request: Request):
    data = await request.json()
    await _save_points_config(data)
    return {"ok": True}


# ── Loans ─────────────────────────────────────────────────────────────────────

@router.get("/api/economy/loans")
async def get_loans(dept_id: Optional[str] = None):
    if dept_id:
        return await list_loans(dept_id.upper())
    return await list_market_loans()


@router.get("/api/economy/loans/market")
async def get_market_loans():
    return await list_market_loans()


@router.post("/api/economy/loans/create")
async def create_loan_endpoint(
    lender_dept:   str   = Body(...),
    borrower_dept: str   = Body(...),
    principal:     int   = Body(...),
    interest_rate: float = Body(0.10),
    due_date:      str   = Body(""),
    list_on_market: bool = Body(False),
):
    try:
        lid = await create_loan(lender_dept.upper(), borrower_dept.upper(),
                                 principal, interest_rate, due_date)
        if list_on_market:
            import aiosqlite
            from core.database import DB_PATH
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE point_loans SET listed_on_market=1, market_price=? WHERE id=?",
                    (principal, lid)
                )
                await db.commit()
        return {"ok": True, "loan_id": lid}
    except InsufficientPointsError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/economy/loans/{loan_id}/repay")
async def repay_loan_endpoint(
    loan_id:     str,
    amount:      int = Body(...),
    repayer_dept:str = Body(...),
):
    try:
        return await repay_loan(loan_id, amount, repayer_dept.upper())
    except InsufficientPointsError as e:
        return {"error": str(e)}


@router.post("/api/economy/loans/{loan_id}/list-market")
async def list_loan_on_market(
    loan_id:      str,
    market_price: int = Body(...),
):
    import aiosqlite
    from core.database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE point_loans SET listed_on_market=1, market_price=? WHERE id=?",
            (market_price, loan_id)
        )
        await db.commit()
    return {"ok": True}


@router.post("/api/economy/loans/{loan_id}/buy")
async def buy_loan(
    loan_id:    str,
    buyer_dept: str = Body(...),
):
    """Transfer loan ownership — buyer pays market_price, becomes new lender."""
    import aiosqlite
    from core.database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM point_loans WHERE id=? AND listed_on_market=1 AND status='active'",
                               (loan_id,)) as cur:
            loan = await cur.fetchone()
    if not loan:
        return {"error": "Loan not found or not on market"}
    loan = dict(loan)
    price = loan["market_price"]
    try:
        await deduct(buyer_dept.upper(), "loan_purchase", price,
                     f"Bought loan {loan_id[:8]}", loan_id)
        await award(loan["lender_dept"], "loan_sale", price,
                    f"Sold loan {loan_id[:8]}", loan_id)
    except InsufficientPointsError as e:
        return {"error": str(e)}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE point_loans SET lender_dept=?, listed_on_market=0 WHERE id=?",
            (buyer_dept.upper(), loan_id)
        )
        await db.commit()
    return {"ok": True, "new_lender": buyer_dept}


@router.post("/api/economy/loan-offers")
async def post_loan_offer(
    lender_dept:   str   = Body(...),
    principal:     int   = Body(...),
    interest_rate: float = Body(0.10),
    due_days:      int   = Body(30),
    description:   str   = Body(""),
):
    try:
        oid = await create_loan_offer(lender_dept.upper(), principal, interest_rate, due_days, description)
        return {"ok": True, "offer_id": oid}
    except InsufficientPointsError as e:
        return {"error": str(e)}

@router.get("/api/economy/loan-offers")
async def get_loan_offers(status: str = "open"):
    return await list_loan_offers(status)

@router.post("/api/economy/loan-offers/{oid}/accept")
async def accept_offer(oid: str, borrower_dept: str = Body(..., embed=True)):
    return await accept_loan_offer(oid, borrower_dept.upper())

@router.post("/api/economy/loan-offers/{oid}/retract")
async def retract_offer(oid: str):
    return await retract_loan_offer(oid)

# ══════════════════════════════════════════════════════════════════════════════
#  MARKETPLACE
# ══════════════════════════════════════════════════════════════════════════════

def _row(r): return dict(r) if r else None
def _rows(rs): return [dict(r) for r in rs]


# ── Agent marketplace ─────────────────────────────────────────────────────────

@router.get("/api/marketplace/agents")
async def list_marketplace_agents():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT m.*, a.name, a.role, a.title, a.personality, a.tone,
                   a.profile_image_url, a.extra_models, a.model_override,
                   a.dept_id as current_dept
            FROM marketplace_agents m
            JOIN agents a ON m.agent_id = a.id
            WHERE m.for_sale = 1
            ORDER BY m.listed_at DESC
        """) as cur:
            return _rows(await cur.fetchall())


@router.get("/api/marketplace/agents/all")
async def all_marketplace_listings():
    """All listings including sold ones."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT m.*, a.name, a.role, a.title, a.personality, a.profile_image_url
            FROM marketplace_agents m
            JOIN agents a ON m.agent_id = a.id
            ORDER BY m.listed_at DESC
        """) as cur:
            return _rows(await cur.fetchall())


@router.post("/api/marketplace/agents/list")
async def list_agent_for_sale(
    agent_id:    str = Body(...),
    seller_dept: str = Body("founder"),
    price:       int = Body(0),
):
    """Put an agent on the marketplace."""
    lid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        # Remove existing active listings for same agent
        await db.execute("UPDATE marketplace_agents SET for_sale=0 WHERE agent_id=?", (agent_id,))
        await db.execute(
            "INSERT INTO marketplace_agents (id,agent_id,seller_dept,price,for_sale) VALUES (?,?,?,?,1)",
            (lid, agent_id, seller_dept, price)
        )
        # Mark agent as in marketplace
        await db.execute("UPDATE agents SET status='marketplace' WHERE id=?", (agent_id,))
        await db.commit()
    return {"ok": True, "listing_id": lid}


@router.post("/api/marketplace/agents/{listing_id}/buy")
async def buy_agent(
    listing_id: str,
    buyer_dept: str = Body(...),
    note:       str = Body(""),
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM marketplace_agents WHERE id=? AND for_sale=1", (listing_id,)
        ) as cur:
            listing = _row(await cur.fetchone())
        if not listing:
            return {"error": "Listing not found or already sold"}
        price     = listing["price"]
        agent_id  = listing["agent_id"]
        seller    = listing["seller_dept"]
        # Check buyer has enough points
        bal = await get_balance(buyer_dept)
        if price > 0 and bal < price:
            return {"error": f"Insufficient points. Need {price}, have {bal}."}
        # Charge buyer
        if price > 0:
            await deduct(buyer_dept, "agent_purchase", price, f"Bought agent {agent_id[:8]}")
            if seller != "founder":
                await award(seller, "agent_sale", price, f"Sold agent {agent_id[:8]}")
        # Transfer agent to buyer dept
        await db.execute(
            "UPDATE agents SET dept_id=?, status='active', parent_agent_id=NULL WHERE id=?",
            (buyer_dept.upper(), agent_id)
        )
        await db.execute(
            "UPDATE marketplace_agents SET for_sale=0, sold_to_dept=?, sold_at=? WHERE id=?",
            (buyer_dept, datetime.utcnow().isoformat(), listing_id)
        )
        await db.commit()
    return {"ok": True, "agent_id": agent_id, "new_dept": buyer_dept}


@router.post("/api/marketplace/agents/{listing_id}/fire-to-pool")
async def fire_agent_to_pool(listing_id: str):
    """Fire fires the agent directly back to free pool."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT agent_id FROM marketplace_agents WHERE id=?", (listing_id,)) as cur:
            row = _row(await cur.fetchone())
        if not row:
            return {"error": "Not found"}
        await db.execute(
            "UPDATE marketplace_agents SET for_sale=1, seller_dept='founder', price=0 WHERE id=?",
            (listing_id,)
        )
        await db.execute("UPDATE agents SET status='marketplace' WHERE id=?", (row["agent_id"],))
        await db.commit()
    return {"ok": True}


# ── Extension marketplace ─────────────────────────────────────────────────────

@router.get("/api/marketplace/extensions")
async def list_ext_marketplace():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT m.*, 
              (SELECT COUNT(*) FROM ext_ownership eo WHERE eo.ext_id=m.ext_id) as buyer_count
            FROM marketplace_extensions m
            WHERE m.for_sale=1
            ORDER BY m.listed_at DESC
        """) as cur:
            rows = _rows(await cur.fetchall())
    # Flag flash sales
    now = datetime.utcnow().isoformat()
    for r in rows:
        r["flash_active"] = bool(r.get("flash_expires") and r["flash_expires"] > now)
    return rows


@router.post("/api/marketplace/extensions/list")
async def list_extension(
    ext_id:          str = Body(...),
    ext_name:        str = Body(...),
    owner_dept:      str = Body(...),
    price_ownership: int = Body(0),
    price_usage:     int = Body(0),
    description:     str = Body(""),
    flash_hours:     int = Body(0),
):
    """List an extension on the marketplace."""
    eid  = str(uuid.uuid4())
    flash = ""
    if flash_hours > 0:
        from datetime import timedelta
        flash = (datetime.utcnow() + timedelta(hours=flash_hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO marketplace_extensions (id,ext_id,ext_name,owner_dept,price_ownership,price_usage,description,flash_expires) VALUES (?,?,?,?,?,?,?,?)",
            (eid, ext_id, ext_name, owner_dept, price_ownership, price_usage, description, flash)
        )
        await db.commit()
    return {"ok": True, "listing_id": eid}


@router.post("/api/marketplace/extensions/{listing_id}/buy")
async def buy_extension(
    listing_id: str,
    buyer_dept: str = Body(...),
    buy_type:   str = Body("usage"),  # "ownership" | "usage"
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM marketplace_extensions WHERE id=? AND for_sale=1", (listing_id,)
        ) as cur:
            listing = _row(await cur.fetchone())
        if not listing:
            return {"error": "Not found"}
        price = listing["price_ownership"] if buy_type == "ownership" else listing["price_usage"]
        now   = datetime.utcnow().isoformat()
        # Flash sale check
        if listing.get("flash_expires") and listing["flash_expires"] < now:
            return {"error": "Flash sale has expired"}
        # Flash: only original requesting dept for first 24h
        # (simplified: any dept after flash)
        bal = await get_balance(buyer_dept)
        if price > 0 and bal < price:
            return {"error": f"Need {price} pts, have {bal}"}
        if price > 0:
            await deduct(buyer_dept, "ext_purchase", price, f"Ext {listing['ext_name']}")
            if listing["owner_dept"] not in ("founder",""):
                await award(listing["owner_dept"], "ext_sale", price, f"Ext sale {listing['ext_name']}")
        oid = str(uuid.uuid4())
        await db.execute(
            "INSERT OR REPLACE INTO ext_ownership (id,ext_id,dept_id,type) VALUES (?,?,?,?)",
            (oid, listing["ext_id"], buyer_dept, buy_type)
        )
        # If ownership sold, remove from marketplace
        if buy_type == "ownership":
            await db.execute("UPDATE marketplace_extensions SET for_sale=0 WHERE id=?", (listing_id,))
        await db.commit()
    return {"ok": True, "type": buy_type}


@router.get("/api/marketplace/extensions/owned/{dept_id}")
async def dept_owned_extensions(dept_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ext_ownership WHERE dept_id=? ORDER BY acquired_at DESC",
            (dept_id.upper(),)
        ) as cur:
            return _rows(await cur.fetchall())
