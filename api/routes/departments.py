"""api/routes/departments.py"""
import asyncio
import aiosqlite
from fastapi import APIRouter
from core.database import DB_PATH
from core.mail_system import get_unread_count
from core.draft_vault import get_pending_drafts

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("")
async def list_departments():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM departments ORDER BY id") as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["unread_mail"] = await get_unread_count(d["id"])
        pending = await get_pending_drafts(d["id"])
        d["pending_drafts"] = len(pending)
        result.append(d)
    return result


# NOTE: /run-all MUST be declared before /{dept_id} to avoid route conflict
@router.post("/run-all")
async def trigger_all():
    from core.orchestrator import run_all
    asyncio.create_task(run_all())
    return {"status": "started", "message": "All department cycles launched"}


@router.get("/{dept_id}")
async def get_department(dept_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM departments WHERE id=?", (dept_id.upper(),)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Department '{dept_id}' not found"}
    d = dict(row)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM projects WHERE dept_id=? AND status='active'",
            (dept_id.upper(),)
        ) as cur:
            projs = await cur.fetchall()
    d["projects"] = [dict(p) for p in projs]
    return d


@router.post("/{dept_id}/run")
async def trigger_cycle(dept_id: str):
    from core.orchestrator import run_department
    asyncio.create_task(run_department(dept_id.upper()))
    return {"status": "started", "dept_id": dept_id.upper()}
