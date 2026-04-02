"""
departments/base.py — Base class for all Think Tank department agents.
"""
from __future__ import annotations
import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict
from core.database import DB_PATH, log_event, get_context
from core.ai_router import route
from core.mail_system import get_inbox, mark_read, send_mail
from core.draft_vault import save_draft

logger = logging.getLogger(__name__)


class DepartmentAgent:
    dept_id: str = ""
    dept_name: str = ""

    async def run_cycle(self):
        logger.info(f"[{self.dept_id}] Starting cycle...")
        await log_event(self.dept_id, "cycle_start", f"{self.dept_name} cycle started")
        try:
            await self._process_inbox()
            await self._work_on_projects()
            await self._generate_status_memo()
            await self._update_last_run()
        except Exception as e:
            logger.error(f"[{self.dept_id}] Cycle error: {e}", exc_info=True)
            await log_event(self.dept_id, "cycle_error", str(e))
        logger.info(f"[{self.dept_id}] Cycle complete.")

    async def _process_inbox(self):
        messages = await get_inbox(self.dept_id, status="unread")
        if not messages:
            return
        context = await get_context(self.dept_id)
        ctx_str = self._format_context(context)
        for msg in messages:
            await mark_read(msg["id"])
            prompt = f"""You received internal mail from {msg['from_dept']}.
FROM: {msg['from_dept']}
SUBJECT: {msg['subject']}
BODY:
{msg['body']}

Respond with JSON:
{{
  "requires_response": true/false,
  "response_body": "...",
  "action_needed": "none | create_draft",
  "draft_title": "...",
  "draft_type": "memo | strategy | report | recommendation",
  "draft_content": "..."
}}"""
            result = await route("response", self._system_prompt(), prompt, context=ctx_str)
            try:
                text = result["text"].strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                data = json.loads(text)
            except Exception:
                data = {"requires_response": False}
            if data.get("requires_response") and data.get("response_body"):
                await send_mail(self.dept_id, msg["from_dept"],
                                f"Re: {msg['subject']}", data["response_body"],
                                reply_to=msg["id"], thread_id=msg.get("thread_id"))
            if data.get("action_needed") == "create_draft" and data.get("draft_title"):
                await save_draft(self.dept_id, data.get("draft_type", "memo"),
                                 data["draft_title"], data.get("draft_content", ""),
                                 metadata={"triggered_by_mail": msg["id"]})

    async def _work_on_projects(self):
        projects = await self._get_active_projects()
        if not projects:
            return
        context = await get_context(self.dept_id)
        ctx_str = self._format_context(context)
        project = projects[0]
        logger.info(f"[{self.dept_id}] Working on: {project['name']}")
        prompt = f"""Work on this active project:
PROJECT: {project['name']}
DESCRIPTION: {project['description']}
PRIORITY: {project['priority']}

Generate a substantive, detailed deliverable for this project cycle.
Include specific findings, strategies, recommendations, or analyses.
This output will be stored as a draft for review."""
        desc_lower = (project["name"] + " " + (project["description"] or "")).lower()
        if any(w in desc_lower for w in ["strategy", "plan", "roadmap"]):
            task_type = "strategy"
        elif any(w in desc_lower for w in ["report", "analysis"]):
            task_type = "comprehensive_report"
        elif any(w in desc_lower for w in ["research", "intelligence"]):
            task_type = "research_brief"
        else:
            task_type = "full_analysis"
        result = await route(task_type, self._system_prompt(), prompt, context=ctx_str)
        await save_draft(
            dept_id=self.dept_id, draft_type=task_type,
            title=f"[{project['name']}] — {datetime.now().strftime('%Y-%m-%d')}",
            content=result["text"], priority=project.get("priority", "normal"),
            related_project=project["id"], metadata={"backend": result["backend"]}
        )
        await self._check_coordination_needs(project, result["text"])

    async def _check_coordination_needs(self, project: Dict, work_output: str):
        prompt = f"""Based on this {self.dept_name} work output, determine if coordination
with other departments is needed.
Work excerpt: {work_output[:1200]}
Available depts: HF, FIN, RES, ING, STR

If coordination needed:
{{"needs_coordination": true, "mails": [{{"to_dept": "X", "subject": "...", "body": "...", "priority": "normal"}}]}}
If not: {{"needs_coordination": false}}"""
        result = await route("memo", self._system_prompt(), prompt)
        try:
            text = result["text"].strip()
            if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
            data = json.loads(text)
            if data.get("needs_coordination"):
                for mail in data.get("mails", []):
                    if mail.get("to_dept") and mail["to_dept"] != self.dept_id:
                        await send_mail(self.dept_id, mail["to_dept"],
                                        mail["subject"], mail["body"],
                                        priority=mail.get("priority", "normal"))
        except Exception:
            pass

    async def _generate_status_memo(self):
        projects = await self._get_active_projects()
        prompt = f"""Generate a concise weekly status memo for {self.dept_name}.
Active projects: {', '.join(p['name'] for p in projects) if projects else 'None'}
Date: {datetime.now().strftime('%Y-%m-%d')}
Cover: current focus, progress highlights, upcoming priorities, inter-dept needs.
Keep it professional and concise (1-2 paragraphs)."""
        result = await route("memo", self._system_prompt(), prompt)
        await save_draft(self.dept_id, "memo",
                         f"Weekly Status — {self.dept_name} — {datetime.now().strftime('%Y-%m-%d')}",
                         result["text"], priority="low",
                         metadata={"backend": result["backend"], "auto_generated": True})

    async def _get_active_projects(self) -> List[Dict]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM projects WHERE dept_id=? AND status='active'
                ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
                WHEN 'normal' THEN 3 ELSE 4 END
            """, (self.dept_id,)) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def _update_last_run(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE departments SET last_run=strftime('%Y-%m-%dT%H:%M:%S','now') WHERE id=?",
                (self.dept_id,))
            await db.commit()

    def _system_prompt(self) -> str:
        raise NotImplementedError

    @staticmethod
    def _format_context(ctx: Dict[str, str]) -> str:
        if not ctx:
            return "No prior context."
        return "\n".join(f"• {k}: {v}" for k, v in ctx.items())
