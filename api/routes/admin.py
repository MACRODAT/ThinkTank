"""api/routes/admin.py"""
import uuid
import aiosqlite
from fastapi import APIRouter, Body
from typing import Optional
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
async def set_dept_context(dept_id: str, key: str = Body(...), value: str = Body(...)):
    await set_context(dept_id, key, value)
    return {"ok": True}


# ── Projects CRUD ─────────────────────────────────────────────────────────────

@router.get("/projects")
async def all_projects(dept_id: Optional[str] = None, status: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        clauses, params = [], []
        if dept_id:
            clauses.append("p.dept_id=?"); params.append(dept_id.upper())
        if status:
            clauses.append("p.status=?"); params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        async with db.execute(f"""
            SELECT p.*, d.name as dept_name FROM projects p
            JOIN departments d ON p.dept_id=d.id
            {where}
            ORDER BY p.dept_id,
              CASE p.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
              WHEN 'normal' THEN 3 ELSE 4 END
        """, params) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, d.name as dept_name FROM projects p "
            "JOIN departments d ON p.dept_id=d.id WHERE p.id=?",
            (project_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else {"error": "Not found"}


@router.post("/projects")
async def add_project(
    dept_id:     str = Body(...),
    name:        str = Body(...),
    description: str = Body(""),
    priority:    str = Body("normal"),
    status:      str = Body("active"),
):
    pid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO projects (id,dept_id,name,description,priority,status) VALUES (?,?,?,?,?,?)",
            (pid, dept_id.upper(), name, description, priority, status)
        )
        await db.commit()
    return {"project_id": pid}


@router.post("/projects/{project_id}")
async def update_project(
    project_id:  str,
    name:        str = Body(...),
    description: str = Body(""),
    priority:    str = Body("normal"),
    status:      str = Body("active"),
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE projects SET name=?, description=?, priority=?, status=?,
               updated_at=strftime('%Y-%m-%dT%H:%M:%S','now') WHERE id=?""",
            (name, description, priority, status, project_id)
        )
        await db.commit()
    return {"ok": True}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        await db.commit()
    return {"ok": True}


# ── Department system prompt ──────────────────────────────────────────────────

@router.get("/dept-prompt/{dept_id}")
async def get_dept_prompt(dept_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, code, system_prompt, schedule FROM departments WHERE id=?",
            (dept_id.upper(),)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else {"error": "Not found"}


@router.post("/dept-prompt/{dept_id}")
async def save_dept_prompt(
    dept_id:       str,
    system_prompt: str           = Body(...),
    schedule:      Optional[str] = Body(None),
):
    async with aiosqlite.connect(DB_PATH) as db:
        if schedule:
            await db.execute(
                "UPDATE departments SET system_prompt=?, schedule=? WHERE id=?",
                (system_prompt, schedule, dept_id.upper())
            )
        else:
            await db.execute(
                "UPDATE departments SET system_prompt=? WHERE id=?",
                (system_prompt, dept_id.upper())
            )
        await db.commit()
    return {"ok": True}
