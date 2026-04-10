"""
core/draft_vault.py — Stores and manages AI-generated drafts.
"""
from __future__ import annotations
import aiosqlite
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from core.database import DB_PATH, new_id, log_event


async def _log_draft_history(draft_id: str, actor: str, action: str,
                              notes: str = "", snapshot: str = ""):
    """Append one history entry for a draft."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO draft_history (id,draft_id,actor,action,notes,snapshot) VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), draft_id, actor, action, notes or "", snapshot or "")
            )
            await db.commit()
    except Exception:
        pass   # Never crash the caller over history logging


async def _run_draft_migrations():
    """Add missing columns to drafts table for existing databases."""
    async with aiosqlite.connect(DB_PATH) as db:
        migrations = [
            "ALTER TABLE drafts ADD COLUMN reviewed_by  TEXT DEFAULT ''",
            "ALTER TABLE drafts ADD COLUMN revised_by   TEXT DEFAULT ''",
            "ALTER TABLE drafts ADD COLUMN revised_at   TEXT DEFAULT ''",
            "ALTER TABLE drafts ADD COLUMN assigned_to  TEXT DEFAULT ''",
            "ALTER TABLE drafts ADD COLUMN created_by_agent TEXT DEFAULT ''",
        ]
        for sql in migrations:
            try:
                await db.execute(sql)
            except Exception:
                pass  # column already exists
        await db.commit()


async def save_draft(dept_id: str, draft_type: str, title: str, content: str,
                     priority: str = "normal", related_project: Optional[str] = None,
                     metadata: dict = None, created_by_agent: str = "") -> str:
    await _run_draft_migrations()
    draft_id = new_id()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO drafts
              (id, dept_id, draft_type, title, content, priority,
               related_project, metadata, created_by_agent)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (draft_id, dept_id, draft_type, title, content,
              priority, related_project, json.dumps(metadata or {}),
              created_by_agent))
        await db.commit()
    await log_event(dept_id, "draft_created", f"[{draft_type.upper()}] {title}",
                    {"draft_id": draft_id, "priority": priority})
    await _log_draft_history(draft_id, created_by_agent or "system", "created",
                              f"Draft created: {title}")
    return draft_id


async def update_draft(draft_id: str, title: Optional[str] = None,
                       content: Optional[str] = None,
                       priority: Optional[str] = None,
                       append: bool = False) -> bool:
    """Update an existing draft. If append=True, content is appended rather than replaced."""
    await _run_draft_migrations()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return False

        new_content = content
        if content and append:
            new_content = (row["content"] or "") + "\n\n---\n\n" + content

        sets, params = [], []
        if title is not None:     sets.append("title=?");   params.append(title)
        if new_content is not None: sets.append("content=?"); params.append(new_content)
        if priority is not None:  sets.append("priority=?"); params.append(priority)

        if sets:
            params.append(draft_id)
            await db.execute(f"UPDATE drafts SET {','.join(sets)} WHERE id=?", params)
            await db.commit()
    change_desc = []
    if title is not None:   change_desc.append(f"title→'{title}'")
    if content is not None: change_desc.append(f"content updated ({'append' if append else 'replace'})")
    if priority is not None:change_desc.append(f"priority→{priority}")
    if change_desc:
        await _log_draft_history(draft_id, "system", "edited", ", ".join(change_desc))
        # Award 1 pt for editing an existing draft
        try:
            from core.economy import award as _ec_award, _load_points_config
            async with aiosqlite.connect(DB_PATH) as db2:
                db2.row_factory = aiosqlite.Row
                async with db2.execute("SELECT dept_id FROM drafts WHERE id=?", (draft_id,)) as cur:
                    r2 = await cur.fetchone()
            if r2:
                cfg = await _load_points_config()
                await _ec_award(r2["dept_id"], "draft_revision_award",
                                int(cfg.get("draft_revision_award", 1)),
                                f"Draft edit {draft_id[:8]}")
        except Exception:
            pass
    return True


async def get_pending_drafts(dept_id: Optional[str] = None) -> List[Dict]:
    await _run_draft_migrations()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = """SELECT d.*, dep.name as dept_name, dep.code as dept_code
               FROM drafts d JOIN departments dep ON d.dept_id=dep.id
               WHERE d.status IN ('pending','revised') {}
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
    await _run_draft_migrations()
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
    await _run_draft_migrations()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT d.*, dep.name as dept_name, dep.code as dept_code
            FROM drafts d JOIN departments dep ON d.dept_id=dep.id WHERE d.id=?
        """, (draft_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def _get_draft_info(draft_id: str) -> Optional[dict]:
    """Lightweight fetch for economy hooks."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT dept_id, draft_type, status, created_by_agent FROM drafts WHERE id=?",
            (draft_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def review_draft(draft_id: str, action: str,
                       notes: Optional[str] = None,
                       reviewed_by: str = "founder") -> bool:
    """
    action: 'approved' | 'rejected' | 'revised' | 'pending' | 'archived'
    'revised' = notes added, must be re-reviewed by creator before approval.
    A draft with status 'revised' CANNOT be set to 'approved' directly.
    """
    await _run_draft_migrations()
    ts = datetime.utcnow().isoformat()

    # Block approving a 'revised' draft without going back to pending first
    if action == "approved":
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT status FROM drafts WHERE id=?", (draft_id,)) as cur:
                row = await cur.fetchone()
            if row and row["status"] == "revised":
                return False  # must be reviewed by creator first

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if action == "revised":
            # When noting revisions: stamp revised_by + revised_at, keep review_notes
            if notes:
                async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                    row = await cur.fetchone()
                note_block = f"\n\n---\n**📝 REVISION REQUEST [{ts[:16]}] by {reviewed_by}:**\n{notes}"
                new_content = ((row["content"] or "") if row else "") + note_block
                await db.execute(
                    "UPDATE drafts SET status='revised', review_notes=?, revised_by=?, revised_at=?, content=? WHERE id=?",
                    (notes, reviewed_by, ts, new_content, draft_id)
                )
            else:
                await db.execute(
                    "UPDATE drafts SET status='revised', revised_by=?, revised_at=? WHERE id=?",
                    (reviewed_by, ts, draft_id)
                )
        else:
            await db.execute("""
                UPDATE drafts SET status=?, review_notes=?, reviewed_by=?,
                reviewed_at=strftime('%Y-%m-%dT%H:%M:%S','now') WHERE id=?
            """, (action, notes, reviewed_by, draft_id))
        await db.commit()

    await log_event(None, "draft_reviewed", f"Draft {draft_id} → {action}",
                    {"draft_id": draft_id, "action": action, "by": reviewed_by})
    # Always log the status change with actor + notes
    await _log_draft_history(draft_id, reviewed_by, action, notes or "")

    # Economy charges
    try:
        from core.economy import deduct as _ec_deduct, award as _ec_award, _load_points_config
        info = await _get_draft_info(draft_id)
        if info:
            dept      = info["dept_id"]
            dtype     = info["draft_type"]
            cfg       = await _load_points_config()
            is_strat  = (dtype == "strategy")

            if action == "approved":
                pts   = int(cfg.get("draft_strategy_approved", 180)) if is_strat else int(cfg.get("draft_other_approved", 40))
                event = "draft_strategy_approved" if is_strat else "draft_other_approved"
                await _ec_award(dept, event, pts, f"Draft approved {draft_id[:8]}")

            elif action == "rejected":
                if not is_strat and reviewed_by == "founder":
                    await _ec_deduct(dept, "draft_other_rejected_founder",
                                     int(cfg.get("draft_other_rejected_founder", 80)),
                                     f"Founder rejected draft {draft_id[:8]}")
                elif is_strat:
                    await _ec_deduct(dept, "draft_strategy_rejected",
                                     int(cfg.get("draft_strategy_rejected", 20)),
                                     f"Strategy scrapped {draft_id[:8]}")

            elif action == "revised" and is_strat:
                await _ec_deduct(dept, "draft_strategy_revised",
                                 int(cfg.get("draft_strategy_revised", 2)),
                                 f"Strategy revised {draft_id[:8]}")
    except Exception:
        pass  # Never crash review over economy errors

    return True


async def pending_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM drafts WHERE status IN ('pending','revised')"
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT status, COUNT(*) FROM drafts GROUP BY status") as cur:
            rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}
