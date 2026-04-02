"""api/routes/admin.py"""
import uuid
import aiosqlite
from fastapi import APIRouter, Body
from core.database import DB_PATH, set_context, get_context

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit")
async def audit_log(limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/context/{dept_id}")
async def dept_context(dept_id: str):
    return await get_context(dept_id)


@router.post("/context/{dept_id}")
async def set_dept_context(
    dept_id: str,
    key: str = Body(...),
    value: str = Body(...),
):
    await set_context(dept_id, key, value)
    return {"ok": True}


@router.get("/projects")
async def all_projects():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT p.*, d.name as dept_name FROM projects p
            JOIN departments d ON p.dept_id=d.id
            ORDER BY p.dept_id, p.priority
        """) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/projects")
async def add_project(
    dept_id: str = Body(...),
    name: str = Body(...),
    description: str = Body(""),
    priority: str = Body("normal"),
):
    pid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO projects (id,dept_id,name,description,priority) VALUES (?,?,?,?,?)",
            (pid, dept_id, name, description, priority)
        )
        await db.commit()
    return {"project_id": pid}
