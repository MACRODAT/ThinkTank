"""
core/mail_system.py — Internal inter-department mail system.
Supports ref_mail_prev for reply-chain tracking.
"""
from __future__ import annotations
import aiosqlite
import json
import logging
from typing import Optional, List, Dict
from core.database import DB_PATH, new_id, log_event

logger = logging.getLogger(__name__)

_mail_migrated = False

async def _ensure_mail_columns():
    global _mail_migrated
    if _mail_migrated:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        for sql in [
            "ALTER TABLE mail_messages ADD COLUMN ref_mail_prev TEXT DEFAULT ''",
            "ALTER TABLE mail_messages ADD COLUMN archived INTEGER DEFAULT 0",
            "ALTER TABLE mail_messages ADD COLUMN sender_agent_id TEXT DEFAULT ''",
        ]:
            try:
                await db.execute(sql)
            except Exception:
                pass
        await db.commit()
    _mail_migrated = True


async def send_mail(
    from_dept: str, to_dept: str, subject: str, body: str,
    priority: str = "normal", reply_to: Optional[str] = None,
    thread_id: Optional[str] = None, metadata: dict = None,
    ref_mail_prev: Optional[str] = None,
    sender_agent_id: str = "",
) -> str:
    await _ensure_mail_columns()
    try:
        from core.economy import deduct as _ec_deduct
        await _ec_deduct(from_dept.upper(), "mail_send", 1,
                         f"Mail {from_dept}→{to_dept}", "", "")
        await _ec_deduct(to_dept.upper(), "mail_receive", -1,
                         f"Mail received from {from_dept}", "", "")
    except Exception as e:
        logger.warning(f"Economy charge failed in send_mail: {e}")

    mail_id = new_id()
    tid = thread_id or (reply_to and await _get_thread(reply_to)) or mail_id
    ref_prev = ref_mail_prev or reply_to or ""

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO mail_messages
              (id, from_dept, to_dept, subject, body, priority,
               thread_id, reply_to, ref_mail_prev, sender_agent_id, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (mail_id, from_dept.upper(), to_dept.upper(), subject, body,
              priority, tid, reply_to or "", ref_prev, sender_agent_id,
              json.dumps(metadata or {})))
        await db.commit()

    await log_event(from_dept, "mail_sent",
                    f"{from_dept}→{to_dept}: {subject}",
                    {"mail_id": mail_id, "priority": priority})
    return mail_id


async def _get_thread(mail_id: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT thread_id FROM mail_messages WHERE id=?", (mail_id,)) as cur:
            row = await cur.fetchone()
    return row["thread_id"] if row else None


async def get_inbox(dept_id: str, status: str = "unread") -> List[Dict]:
    await _ensure_mail_columns()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM mail_messages
            WHERE to_dept=? AND status=? AND (archived IS NULL OR archived=0)
            ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
            WHEN 'normal' THEN 3 ELSE 4 END, created_at DESC
        """, (dept_id, status)) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_all_mail(dept_id: str, limit: int = 50) -> List[Dict]:
    await _ensure_mail_columns()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM mail_messages
            WHERE (from_dept=? OR to_dept=?) AND (archived IS NULL OR archived=0)
            ORDER BY created_at DESC LIMIT ?
        """, (dept_id, dept_id, limit)) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_thread(thread_id: str) -> List[Dict]:
    await _ensure_mail_columns()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM mail_messages WHERE thread_id=? ORDER BY created_at ASC",
            (thread_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_mail_by_id(mail_id: str) -> Optional[Dict]:
    await _ensure_mail_columns()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM mail_messages WHERE id=?", (mail_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def get_reply_chain(mail_id: str, max_depth: int = 20) -> List[Dict]:
    """Walk ref_mail_prev chain to reconstruct full conversation history."""
    await _ensure_mail_columns()
    chain = []
    seen  = set()
    current = mail_id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        for _ in range(max_depth):
            if not current or current in seen:
                break
            seen.add(current)
            async with db.execute("SELECT * FROM mail_messages WHERE id=?", (current,)) as cur:
                row = await cur.fetchone()
            if not row:
                break
            chain.append(dict(row))
            ref = (row["ref_mail_prev"] or "").strip()
            if not ref or ref == current:
                break
            current = ref
    chain.reverse()
    return chain


async def mark_read(mail_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE mail_messages
            SET status='read', read_at=strftime('%Y-%m-%dT%H:%M:%S','now')
            WHERE id=?
        """, (mail_id,))
        await db.commit()


async def archive_mail(mail_id: str):
    await _ensure_mail_columns()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE mail_messages SET archived=1 WHERE id=?", (mail_id,))
        await db.commit()


async def get_unread_count(dept_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM mail_messages WHERE to_dept=? AND status='unread' AND (archived IS NULL OR archived=0)",
            (dept_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def get_global_mail(limit: int = 100) -> List[Dict]:
    await _ensure_mail_columns()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM mail_messages WHERE (archived IS NULL OR archived=0) ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
