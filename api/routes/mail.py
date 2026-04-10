"""api/routes/mail.py"""
from fastapi import APIRouter, Body
from typing import Optional
from core.mail_system import (
    get_inbox, get_all_mail, get_thread, get_global_mail,
    mark_read, send_mail, get_mail_by_id, get_reply_chain, archive_mail,
)

router = APIRouter(prefix="/api/mail", tags=["mail"])


@router.get("")
async def all_mail(limit: int = 100):
    return await get_global_mail(limit)


# Fixed sub-paths MUST come before /{dept_id} wildcard
@router.get("/thread/{thread_id}")
async def get_thread_messages(thread_id: str):
    return await get_thread(thread_id)


@router.get("/message/{mail_id}")
async def get_single_mail(mail_id: str):
    return await get_mail_by_id(mail_id)


@router.get("/chain/{mail_id}")
async def get_mail_chain(mail_id: str):
    """Return full ref_mail_prev reply chain for a given mail, oldest first."""
    return await get_reply_chain(mail_id)


@router.post("/send")
async def compose(
    from_dept:       str           = Body(...),
    to_dept:         str           = Body(...),
    subject:         str           = Body(...),
    body:            str           = Body(...),
    priority:        str           = Body("normal"),
    reply_to:        Optional[str] = Body(None),
    ref_mail_prev:   Optional[str] = Body(None),
    sender_agent_id: str           = Body(""),
):
    mail_id = await send_mail(
        from_dept.upper(), to_dept.upper(),
        subject, body, priority, reply_to,
        ref_mail_prev=ref_mail_prev,
        sender_agent_id=sender_agent_id,
    )
    return {"mail_id": mail_id}


@router.get("/{dept_id}/inbox")
async def inbox(dept_id: str, status: str = "unread"):
    return await get_inbox(dept_id.upper(), status)


@router.get("/{dept_id}/all")
async def dept_mail(dept_id: str, limit: int = 50):
    return await get_all_mail(dept_id.upper(), limit)


@router.post("/{mail_id}/read")
async def mark_as_read(mail_id: str):
    await mark_read(mail_id)
    return {"ok": True}


@router.post("/{mail_id}/archive")
async def archive(mail_id: str):
    await archive_mail(mail_id)
    return {"ok": True}
