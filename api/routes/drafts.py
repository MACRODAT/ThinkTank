"""api/routes/drafts.py"""
from fastapi import APIRouter, Body
from typing import Optional
from core.draft_vault import (
    get_all_drafts, get_pending_drafts, get_draft,
    review_draft, save_draft, stats, pending_count,
)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("")
async def all_drafts(limit: int = 100):
    return await get_all_drafts(limit)


# Fixed routes MUST come before /{draft_id} wildcard
@router.get("/pending")
async def pending(dept_id: Optional[str] = None):
    return await get_pending_drafts(dept_id.upper() if dept_id else None)


@router.get("/stats")
async def draft_stats():
    s = await stats()
    s["pending_count"] = await pending_count()
    return s


@router.post("")
async def create_draft(
    dept_id: str = Body(...),
    draft_type: str = Body(...),
    title: str = Body(...),
    content: str = Body(...),
    priority: str = Body("normal"),
):
    draft_id = await save_draft(dept_id.upper(), draft_type, title, content, priority)
    return {"draft_id": draft_id}


@router.get("/{draft_id}")
async def get_one(draft_id: str):
    d = await get_draft(draft_id)
    if not d:
        return {"error": "Not found"}
    return d


@router.post("/{draft_id}/review")
async def review(
    draft_id: str,
    action: str = Body(...),
    notes: Optional[str] = Body(None),
):
    valid = {"approved", "rejected", "revised"}
    if action not in valid:
        return {"error": f"action must be one of {valid}"}
    await review_draft(draft_id, action, notes)
    return {"ok": True, "action": action}


@router.post("/{draft_id}/update")
async def update_draft_content(
    draft_id: str,
    title: str = Body(...),
    content: str = Body(...),
    draft_type: str = Body(...),
    priority: str = Body("normal"),
):
    """Update title, content, type and priority of an existing draft."""
    import aiosqlite
    from core.database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE drafts
               SET title=?, content=?, draft_type=?, priority=?,
                   reviewed_at=strftime('%Y-%m-%dT%H:%M:%S','now')
               WHERE id=?""",
            (title, content, draft_type, priority, draft_id)
        )
        await db.commit()
    return {"ok": True, "draft_id": draft_id}
