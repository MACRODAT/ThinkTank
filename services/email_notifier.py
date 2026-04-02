"""
services/email_notifier.py — Sends draft digest to real inbox via SMTP.
"""
from __future__ import annotations
import aiosmtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from core.config import config
from core.draft_vault import get_pending_drafts

logger = logging.getLogger(__name__)

DEPT_COLORS = {
    "HF": "#4CAF50", "FIN": "#2196F3",
    "RES": "#9C27B0", "ING": "#FF9800", "STR": "#F44336",
}
PRIORITY_BADGE = {
    "urgent": "🔴", "high": "🟠", "normal": "🟡", "low": "🟢",
}


async def send_draft_digest():
    cfg = config.email
    if not getattr(cfg, "enabled", True):
        return
    drafts = await get_pending_drafts()
    if not drafts:
        logger.info("No pending drafts — skipping digest.")
        return
    html = _build_html(drafts)
    await _send(
        subject=f"📋 Think Tank — {len(drafts)} Draft(s) Awaiting Review | "
                f"{datetime.now().strftime('%Y-%m-%d')}",
        html=html,
    )
    logger.info(f"Digest sent: {len(drafts)} pending drafts.")


def _build_html(drafts: list) -> str:
    port = getattr(config.server, "port", 8000)
    rows = ""
    for d in drafts:
        color = DEPT_COLORS.get(d["dept_id"], "#607D8B")
        badge = PRIORITY_BADGE.get(d["priority"], "⚪")
        rows += (
            f'<tr style="border-bottom:1px solid #21262d;">'
            f'<td style="padding:10px 8px;">'
            f'<span style="background:{color};color:white;padding:3px 8px;'
            f'border-radius:4px;font-size:12px;font-weight:bold;">{d["dept_id"]}</span></td>'
            f'<td style="padding:10px 8px;color:#8b949e;font-size:12px;">'
            f'{d["draft_type"].upper()}</td>'
            f'<td style="padding:10px 8px;color:#e6edf3;">{d["title"]}</td>'
            f'<td style="padding:10px 8px;text-align:center;">{badge}</td>'
            f'<td style="padding:10px 8px;color:#8b949e;font-size:12px;">'
            f'{d["created_at"][:10]}</td></tr>'
        )
    return f"""<html><body style="font-family:Arial,sans-serif;background:#0d1117;
color:#e6edf3;padding:20px;">
<div style="max-width:700px;margin:0 auto;background:#161b22;border-radius:12px;
border:1px solid #21262d;overflow:hidden;">
  <div style="padding:24px;border-bottom:1px solid #21262d;">
    <h1 style="margin:0;color:#e6edf3;">🏛️ Central Think Tank</h1>
    <p style="color:#8b949e;margin:4px 0 0;">Draft Digest — {datetime.now().strftime('%A, %B %d %Y')}</p>
  </div>
  <div style="padding:24px;">
    <p style="color:#8b949e;"><strong style="color:#e6edf3;">{len(drafts)}</strong> draft(s) pending review.</p>
    <table style="width:100%;border-collapse:collapse;">
      <thead><tr style="color:#8b949e;font-size:11px;text-transform:uppercase;">
        <th style="padding:8px;text-align:left;">Dept</th>
        <th style="padding:8px;text-align:left;">Type</th>
        <th style="padding:8px;text-align:left;">Title</th>
        <th style="padding:8px;">Priority</th>
        <th style="padding:8px;text-align:left;">Date</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div style="margin-top:24px;text-align:center;">
      <a href="http://localhost:{port}" style="background:#238636;color:white;
      padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:bold;">
        Open Dashboard →</a>
    </div>
  </div>
</div></body></html>"""


async def _send(subject: str, html: str):
    cfg = config.email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.username
    msg["To"] = cfg.recipient
    msg.attach(MIMEText(html, "html"))
    try:
        await aiosmtplib.send(
            msg, hostname=cfg.smtp_host, port=cfg.smtp_port,
            username=cfg.username, password=cfg.password, start_tls=True,
        )
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise
