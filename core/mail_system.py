"""
core/mail_system.py — Internal inter-department mail system.
"""
from __future__ import annotations
import aiosqlite
import json
from typing import Optional, List, Dict
from core.database import DB_PATH, new_id, log_event


async def send_mail(from_dept: str, to_dept: str, subject: str, body: str,
                    priority: str = "normal", reply_to: Optional[str] = None,
                    thread_id: Optional[str] = None, metadata: dict = None) -> str:
    import logging
    logger = logging.getLogger(__name__)
    print(metadata)
    try:
        from core.economy import deduct as _ec_deduct
        await _ec_deduct(from_dept.upper(), "mail_send", 1,
                         f"Sending mail from {from_dept} to {to_dept}", "", "")
        await _ec_deduct(to_dept.upper(), "mail_receive", -1,
                         f"Sending mail from {from_dept} to {to_dept}", "", "")
    except Exception: 
        logger.log("Failed to deduct points in send_mail.")
    mail_id = new_id()
    tid = thread_id or (reply_to and await _get_thread(reply_to)) or mail_id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO mail_messages
              (id, from_dept, to_dept, subject, body, priority, thread_id, reply_to, metadata)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (mail_id, from_dept, to_dept, subject, body,
              priority, tid, reply_to, json.dumps(metadata or {})))
        await db.commit()
    await log_event(from_dept, "mail_sent", f"{from_dept} → {to_dept}: {subject}",
                    {"mail_id": mail_id, "priority": priority})
    return mail_id


async def _get_thread(mail_id: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT thread_id FROM mail_messages WHERE id=?", (mail_id,)) as cur:
            row = await cur.fetchone()
    return row["thread_id"] if row else None


async def get_inbox(dept_id: str, status: str = "unread") -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM mail_messages WHERE to_dept=? AND status=?
            ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
            WHEN 'normal' THEN 3 ELSE 4 END, created_at DESC
        """, (dept_id, status)) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_all_mail(dept_id: str, limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM mail_messages WHERE from_dept=? OR to_dept=?
            ORDER BY created_at DESC LIMIT ?
        """, (dept_id, dept_id, limit)) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_thread(thread_id: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM mail_messages WHERE thread_id=? ORDER BY created_at ASC",
            (thread_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def mark_read(mail_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE mail_messages SET status='read',
            read_at=strftime('%Y-%m-%dT%H:%M:%S','now') WHERE id=?
        """, (mail_id,))
        await db.commit()


async def get_unread_count(dept_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM mail_messages WHERE to_dept=? AND status='unread'", (dept_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def get_global_mail(limit: int = 100) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM mail_messages ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
