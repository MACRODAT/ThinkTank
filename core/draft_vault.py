"""
core/draft_vault.py — Stores and manages AI-generated drafts awaiting validation.
"""
from __future__ import annotations
import aiosqlite
import json
from typing import Optional, List, Dict
from core.database import DB_PATH, new_id, log_event


async def save_draft(dept_id: str, draft_type: str, title: str, content: str,
                     priority: str = "normal", related_project: Optional[str] = None,
                     metadata: dict = None) -> str:
    draft_id = new_id()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO drafts
              (id, dept_id, draft_type, title, content, priority, related_project, metadata)
            VALUES (?,?,?,?,?,?,?,?)
        """, (draft_id, dept_id, draft_type, title, content,
              priority, related_project, json.dumps(metadata or {})))
        await db.commit()
    await log_event(dept_id, "draft_created", f"[{draft_type.upper()}] {title}",
                    {"draft_id": draft_id, "priority": priority})
    return draft_id


async def get_pending_drafts(dept_id: Optional[str] = None) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = """SELECT d.*, dep.name as dept_name, dep.code as dept_code
               FROM drafts d JOIN departments dep ON d.dept_id=dep.id
               WHERE d.status='pending' {}
               ORDER BY CASE d.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
               WHEN 'normal' THEN 3 ELSE 4 END, d.created_at DESC"""
        if dept_id:
            async with db.execute(q.format("AND d.dept_id=?"), (dept_id,)) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(q.format("")) as cur:
                rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_all_drafts(limit: int = 100) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT d.*, dep.name as dept_name, dep.code as dept_code
            FROM drafts d JOIN departments dep ON d.dept_id=dep.id
            ORDER BY d.created_at DESC LIMIT ?
        """, (limit,)) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_draft(draft_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT d.*, dep.name as dept_name, dep.code as dept_code
            FROM drafts d JOIN departments dep ON d.dept_id=dep.id WHERE d.id=?
        """, (draft_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def review_draft(draft_id: str, action: str, notes: Optional[str] = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE drafts SET status=?, review_notes=?,
            reviewed_at=strftime('%Y-%m-%dT%H:%M:%S','now') WHERE id=?
        """, (action, notes, draft_id))
        await db.commit()
    await log_event(None, "draft_reviewed", f"Draft {draft_id} → {action}",
                    {"draft_id": draft_id, "action": action})
    return True


async def pending_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM drafts WHERE status='pending'") as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT status, COUNT(*) FROM drafts GROUP BY status") as cur:
            rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}
