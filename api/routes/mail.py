"""api/routes/mail.py"""
from fastapi import APIRouter, Body
from typing import Optional
from core.mail_system import (
    get_inbox, get_all_mail, get_thread, get_global_mail,
    mark_read, send_mail
)

router = APIRouter(prefix="/api/mail", tags=["mail"])


@router.get("")
async def all_mail(limit: int = 100):
    return await get_global_mail(limit)


@router.get("/{dept_id}/inbox")
async def inbox(dept_id: str, status: str = "unread"):
    return await get_inbox(dept_id, status)


@router.get("/{dept_id}/all")
async def dept_mail(dept_id: str, limit: int = 50):
    return await get_all_mail(dept_id, limit)


@router.get("/thread/{thread_id}")
async def thread(thread_id: str):
    return await get_thread(thread_id)


@router.post("/{mail_id}/read")
async def read(mail_id: str):
    await mark_read(mail_id)
    return {"ok": True}


@router.post("/send")
async def compose(
    from_dept: str = Body(...),
    to_dept: str = Body(...),
    subject: str = Body(...),
    body: str = Body(...),
    priority: str = Body("normal"),
    reply_to: Optional[str] = Body(None),
):
    mail_id = await send_mail(from_dept, to_dept, subject, body, priority, reply_to)
    return {"mail_id": mail_id}
