"""api/routes/topics.py — Topics system for grouping mail, drafts, projects."""
from __future__ import annotations
import uuid
from typing import Optional
import aiosqlite
from fastapi import APIRouter, Body
from core.database import DB_PATH

router = APIRouter(prefix="/api/topics", tags=["topics"])

def _row(r): return dict(r) if r else None
def _rows(rs): return [dict(r) for r in rs]


async def _ensure_topics_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                color       TEXT DEFAULT '#58a6ff',
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
            )""")
        # Safe column additions to existing tables
        for sql in [
            "ALTER TABLE drafts ADD COLUMN topic_id TEXT DEFAULT ''",
            "ALTER TABLE mail_messages ADD COLUMN topic_id TEXT DEFAULT ''",
            "ALTER TABLE projects ADD COLUMN topic_id TEXT DEFAULT ''",
        ]:
            try:
                await db.execute(sql)
            except Exception:
                pass
        await db.commit()


@router.get("")
async def list_topics():
    await _ensure_topics_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM topics ORDER BY name") as cur:
            topics = _rows(await cur.fetchall())
    # Annotate with counts
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        for t in topics:
            async with db.execute("SELECT COUNT(*) as c FROM drafts WHERE topic_id=?", (t["id"],)) as cur:
                t["draft_count"] = (await cur.fetchone())["c"]
            async with db.execute("SELECT COUNT(*) as c FROM mail_messages WHERE topic_id=?", (t["id"],)) as cur:
                t["mail_count"] = (await cur.fetchone())["c"]
            async with db.execute("SELECT COUNT(*) as c FROM projects WHERE topic_id=?", (t["id"],)) as cur:
                t["project_count"] = (await cur.fetchone())["c"]
    return topics


@router.post("")
async def create_topic(
    name:        str = Body(...),
    description: str = Body(""),
    color:       str = Body("#58a6ff"),
):
    await _ensure_topics_table()
    tid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        # Check duplicate
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM topics WHERE LOWER(name)=LOWER(?)", (name,)) as cur:
            existing = await cur.fetchone()
        if existing:
            return {"id": existing["id"], "existing": True}
        await db.execute(
            "INSERT INTO topics (id, name, description, color) VALUES (?,?,?,?)",
            (tid, name, description, color)
        )
        await db.commit()
    return {"id": tid, "existing": False}


@router.put("/{tid}")
async def update_topic(
    tid:         str,
    name:        Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    color:       Optional[str] = Body(None),
):
    await _ensure_topics_table()
    async with aiosqlite.connect(DB_PATH) as db:
        if name:        await db.execute("UPDATE topics SET name=? WHERE id=?",        (name, tid))
        if description is not None:
                        await db.execute("UPDATE topics SET description=? WHERE id=?", (description, tid))
        if color:       await db.execute("UPDATE topics SET color=? WHERE id=?",       (color, tid))
        await db.commit()
    return {"ok": True}


@router.delete("/{tid}")
async def delete_topic(tid: str):
    await _ensure_topics_table()
    async with aiosqlite.connect(DB_PATH) as db:
        # Unlink from all items first
        await db.execute("UPDATE drafts SET topic_id='' WHERE topic_id=?", (tid,))
        await db.execute("UPDATE mail_messages SET topic_id='' WHERE topic_id=?", (tid,))
        await db.execute("UPDATE projects SET topic_id='' WHERE topic_id=?", (tid,))
        await db.execute("DELETE FROM topics WHERE id=?", (tid,))
        await db.commit()
    return {"ok": True}


@router.post("/{tid}/assign")
async def assign_topic(
    tid:       str,
    item_type: str = Body(...),   # "draft" | "mail" | "project"
    item_id:   str = Body(...),
):
    """Assign a topic to a draft, mail message, or project."""
    await _ensure_topics_table()
    table_map = {"draft": "drafts", "mail": "mail_messages", "project": "projects"}
    table = table_map.get(item_type)
    if not table:
        return {"error": f"Unknown item_type: {item_type}"}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE {table} SET topic_id=? WHERE id=?", (tid, item_id))
        await db.commit()
    return {"ok": True}


@router.get("/search")
async def search_topics(q: str = ""):
    """Search topics by name — used by agents to find existing topics before creating new ones."""
    await _ensure_topics_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, description, color FROM topics WHERE LOWER(name) LIKE LOWER(?) ORDER BY name LIMIT 10",
            (f"%{q}%",)
        ) as cur:
            return _rows(await cur.fetchall())
