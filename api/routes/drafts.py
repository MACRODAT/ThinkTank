"""api/routes/drafts.py — Draft CRUD including missing update endpoint."""
from fastapi import APIRouter, Body
from typing import Optional
from core.draft_vault import (
    get_all_drafts, get_pending_drafts, get_draft,
    review_draft, save_draft, update_draft, stats, pending_count,
)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("")
async def all_drafts(limit: int = 100):
    return await get_all_drafts(limit)


# ── Static routes MUST come before /{draft_id} wildcard ──────────────────────

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
    dept_id:          str           = Body(...),
    draft_type:       str           = Body(...),
    title:            str           = Body(...),
    content:          str           = Body(...),
    priority:         str           = Body("normal"),
    created_by_agent: str           = Body(""),
):
    draft_id = await save_draft(
        dept_id.upper(), draft_type, title, content, priority,
        created_by_agent=created_by_agent
    )
    return {"draft_id": draft_id}


# ── Draft-specific routes (still before /{draft_id}) ─────────────────────────

@router.get("/{draft_id}")
async def get_one(draft_id: str):
    d = await get_draft(draft_id)
    if not d:
        return {"error": "Not found"}
    return d


@router.post("/{draft_id}/update")
async def update_one(
    draft_id: str,
    title:    Optional[str] = Body(None),
    content:  Optional[str] = Body(None),
    priority: Optional[str] = Body(None),
    append:   bool          = Body(False),
):
    """Update draft title, content or priority. Set append=true to append content."""
    ok = await update_draft(draft_id, title=title, content=content,
                            priority=priority, append=append)
    if not ok:
        return {"error": "Draft not found"}
    return {"ok": True}


@router.post("/{draft_id}/review")
async def review(
    draft_id:    str,
    action:      str           = Body(...),
    notes:       Optional[str] = Body(None),
    reviewed_by: str           = Body("founder"),
):
    """
    action: approved | rejected | revised | pending | archived
    'revised' stamps revision notes and blocks approval until creator re-reviews.
    """
    valid = {"approved", "rejected", "revised", "pending", "archived"}
    if action not in valid:
        return {"error": f"action must be one of {valid}"}
    ok = await review_draft(draft_id, action, notes, reviewed_by)
    if not ok and action == "approved":
        return {"error": "Cannot approve a draft in 'revised' status — creator must review changes first."}
    return {"ok": True, "action": action}
