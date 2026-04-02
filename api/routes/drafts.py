"""api/routes/drafts.py"""
from fastapi import APIRouter, Body
from typing import Optional
from core.draft_vault import (
    get_all_drafts, get_pending_drafts, get_draft,
    review_draft, save_draft, stats, pending_count
)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("")
async def all_drafts(limit: int = 100):
    return await get_all_drafts(limit)


@router.get("/pending")
async def pending(dept_id: Optional[str] = None):
    return await get_pending_drafts(dept_id)


@router.get("/stats")
async def draft_stats():
    s = await stats()
    s["pending_count"] = await pending_count()
    return s


@router.get("/{draft_id}")
async def get_one(draft_id: str):
    d = await get_draft(draft_id)
    return d if d else {"error": "Not found"}


@router.post("/{draft_id}/review")
async def review(
    draft_id: str,
    action: str = Body(...),
    notes: Optional[str] = Body(None),
):
    await review_draft(draft_id, action, notes)
    return {"ok": True, "action": action}


@router.post("")
async def create_draft(
    dept_id: str = Body(...),
    draft_type: str = Body(...),
    title: str = Body(...),
    content: str = Body(...),
    priority: str = Body("normal"),
):
    draft_id = await save_draft(dept_id, draft_type, title, content, priority)
    return {"draft_id": draft_id}
