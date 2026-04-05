"""core/agent_runner.py — Runs agent heartbeat cycles via AI."""
from __future__ import annotations
import uuid, json, logging
from datetime import datetime
from typing import Optional
import aiosqlite
from core.database import DB_PATH
from core.ai_router import route

logger = logging.getLogger(__name__)


async def _get_agent_context(agent_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)) as cur:
            agent = dict(await cur.fetchone() or {})
        if not agent:
            return {}

        # Load agent MD files
        async with db.execute(
            "SELECT category, filename, content FROM agent_md_files WHERE agent_id=?",
            (agent_id,)
        ) as cur:
            files = [dict(r) for r in await cur.fetchall()]

        # Load dept MD files
        async with db.execute(
            "SELECT category, filename, content FROM dept_md_files WHERE dept_id=?",
            (agent["dept_id"],)
        ) as cur:
            dept_files = [dict(r) for r in await cur.fetchall()]

        # CEO can access all dept files
        agent["md_files"]   = files
        agent["dept_files"] = dept_files
    return agent


def _build_system_prompt(agent: dict) -> str:
    parts = [
        f"# Agent Identity",
        f"You are **{agent['name']}**, {agent['title'] or agent['role']} "
        f"at the Central Think Tank's **{agent['dept_id']}** department.",
    ]
    if agent.get("personality"):
        parts.append(f"\n## Personality\n{agent['personality']}")
    if agent.get("tone"):
        parts.append(f"\n## Communication Tone\n{agent['tone']}")
    if agent.get("is_ceo"):
        parts.append("""
## CEO Powers
- You may approve or reject decisions within your department WITHOUT contacting the Founder.
- You may fire underperforming agents.
- You may delegate specific powers to senior agents.
- You MUST contact the Founder (use send_to_founder action) if you are NOT SURE about a major decision, if something is critical, or if it exceeds your mandate.
- You may respond to mail, approve strategies, create draft endeavors.
""")
    # Inject MD file context
    if agent.get("md_files"):
        parts.append("\n## Your Knowledge Files")
        for f in agent["md_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")
    if agent.get("dept_files"):
        parts.append("\n## Department Guidelines & Policy")
        for f in agent["dept_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")

    parts.append("""
## Output Format
Respond in JSON. Your response must be a JSON object with:
{
  "actions": [
    // Array of actions you want to take. Each action is an object:
    // { "type": "send_mail", "to_dept": "STR", "subject": "...", "body": "..." }
    // { "type": "send_to_founder", "subject": "...", "body": "...", "priority": "critical|high", "requires_decision": true|false }
    // { "type": "create_draft", "title": "...", "content": "...", "draft_type": "strategy" }
    // { "type": "create_draft_endeavor", "name": "...", "description": "...", "phases": [...] }
    // { "type": "approve_draft", "draft_id": "..." }
    // { "type": "request_spawn", "name": "...", "role": "...", "personality": "...", "reason": "..." }
    // { "type": "log", "message": "..." }
  ],
  "summary": "Brief summary of this heartbeat cycle"
}
Only produce actions that are genuinely needed based on the context. Do not produce actions just to seem busy.
""")
    return "\n".join(parts)


async def run_agent_heartbeat(agent_id: str) -> dict:
    agent = await _get_agent_context(agent_id)
    if not agent or agent.get("status") != "active":
        return {"ok": False, "error": "Agent inactive or not found"}

    system_prompt = _build_system_prompt(agent)

    # Build user prompt with current context
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Unread dept mail
        async with db.execute("""
            SELECT mm.subject, mm.body, mm.from_dept, mm.priority
            FROM mail_messages mm
            WHERE mm.to_dept=? AND mm.status='unread' ORDER BY mm.created_at DESC LIMIT 10
        """, (agent["dept_id"],)) as cur:
            unread_mail = [dict(r) for r in await cur.fetchall()]

        # Active projects
        async with db.execute(
            "SELECT name, description, priority FROM projects WHERE dept_id=? AND status='active'",
            (agent["dept_id"],)
        ) as cur:
            projects = [dict(r) for r in await cur.fetchall()]

        # Pending drafts for CEO
        pending_drafts = []
        if agent.get("is_ceo"):
            async with db.execute(
                "SELECT id, title, draft_type FROM drafts WHERE dept_id=? AND status='pending' LIMIT 5",
                (agent["dept_id"],)
            ) as cur:
                pending_drafts = [dict(r) for r in await cur.fetchall()]

    context_parts = [
        f"## Current Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"## Department: {agent['dept_id']}",
    ]
    if unread_mail:
        context_parts.append(f"## Unread Mail ({len(unread_mail)} messages)")
        for m in unread_mail[:3]:
            context_parts.append(f"- From {m['from_dept']}: **{m['subject']}** — {m['body'][:200]}")
    if projects:
        context_parts.append(f"## Active Projects ({len(projects)})")
        for p in projects[:5]:
            context_parts.append(f"- [{p['priority']}] {p['name']}: {p['description'][:100]}")
    if pending_drafts:
        context_parts.append(f"## Pending Drafts Awaiting CEO Approval ({len(pending_drafts)})")
        for d in pending_drafts:
            context_parts.append(f"- {d['id']}: {d['title']} ({d['draft_type']})")

    user_prompt = "\n".join(context_parts) + "\n\nRun your heartbeat cycle and decide what actions to take."

    try:
        result = await route(
            task_type="agent_heartbeat",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            dept_id=agent["dept_id"],
        )
        response_text = result.get("text", "")

        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {"actions": [], "summary": response_text[:200]}

        # Execute actions
        actions_taken = []
        for action in parsed.get("actions", []):
            try:
                taken = await _execute_agent_action(agent, action)
                if taken:
                    actions_taken.append(taken)
            except Exception as e:
                logger.warning(f"Action failed for {agent['name']}: {e}")

        # Log heartbeat
        async with aiosqlite.connect(DB_PATH) as db:
            hid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary)
                VALUES (?,?,?,?,?)
            """, (hid, agent_id, datetime.utcnow().isoformat(), "ok",
                   parsed.get("summary", "Heartbeat complete")))
            await db.execute("UPDATE agents SET last_heartbeat=? WHERE id=?",
                             (datetime.utcnow().isoformat(), agent_id))
            await db.commit()

        return {
            "ok": True,
            "agent": agent["name"],
            "summary": parsed.get("summary", ""),
            "actions_taken": actions_taken,
        }

    except Exception as e:
        logger.error(f"Heartbeat error for {agent.get('name','?')}: {e}")
        async with aiosqlite.connect(DB_PATH) as db:
            hid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary)
                VALUES (?,?,?,?,?)
            """, (hid, agent_id, datetime.utcnow().isoformat(), "error", str(e)))
            await db.commit()
        return {"ok": False, "error": str(e)}


async def _execute_agent_action(agent: dict, action: dict) -> Optional[str]:
    atype = action.get("type")
    async with aiosqlite.connect(DB_PATH) as db:

        if atype == "send_mail":
            mid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO mail_messages
                (id,from_dept,to_dept,subject,body,priority,thread_id,status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (mid, agent["dept_id"], action.get("to_dept","STR"),
                   action.get("subject",""), action.get("body",""),
                   action.get("priority","normal"), str(uuid.uuid4()), "unread"))
            await db.commit()
            return f"Sent mail to {action.get('to_dept')}"

        elif atype == "send_to_founder":
            mid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO founder_mail
                (id,from_agent_id,from_dept_id,subject,body,priority,requires_decision,context_json)
                VALUES (?,?,?,?,?,?,?,?)
            """, (mid, agent["id"], agent["dept_id"],
                   action.get("subject",""), action.get("body",""),
                   action.get("priority","high"),
                   1 if action.get("requires_decision") else 0, "{}"))
            await db.commit()
            return f"📨 Sent to Founder: {action.get('subject')}"

        elif atype == "create_draft":
            did = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status)
                VALUES (?,?,?,?,?,?,?)
            """, (did, agent["dept_id"],
                   action.get("title","Draft"), action.get("content",""),
                   action.get("draft_type","memo"),
                   action.get("priority","normal"), "pending"))
            await db.commit()
            return f"Created draft: {action.get('title')}"

        elif atype == "create_draft_endeavor":
            eid = str(uuid.uuid4())
            phases = json.dumps(action.get("phases", []))
            await db.execute("""
                INSERT INTO draft_endeavors (id,created_by,dept_id,name,description,phases_json)
                VALUES (?,?,?,?,?,?)
            """, (eid, agent["id"], agent["dept_id"],
                   action.get("name","New Endeavor"),
                   action.get("description",""), phases))
            await db.commit()
            return f"Submitted draft endeavor: {action.get('name')}"

        elif atype == "approve_draft" and agent.get("is_ceo"):
            draft_id = action.get("draft_id")
            if draft_id:
                await db.execute(
                    "UPDATE drafts SET status='approved' WHERE id=? AND dept_id=?",
                    (draft_id, agent["dept_id"])
                )
                did = str(uuid.uuid4())
                await db.execute("""
                    INSERT INTO ceo_decisions (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes)
                    VALUES (?,?,?,?,?,?,?)
                """, (did, agent["id"], agent["dept_id"], "approve_draft", draft_id,
                       "approved", action.get("reason","")))
                await db.commit()
                return f"CEO approved draft: {draft_id}"

        elif atype == "request_spawn":
            sid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO agent_spawn_requests
                (id,requesting_agent_id,dept_id,proposed_name,proposed_role,
                 proposed_personality,proposed_tone,status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (sid, agent["id"], agent["dept_id"],
                   action.get("name",""), action.get("role","analyst"),
                   action.get("personality",""), action.get("tone",""),
                   "approved" if agent.get("is_ceo") else "pending"))
            await db.commit()
            return f"Spawn request for: {action.get('name')}"

        elif atype == "log":
            return f"Log: {action.get('message','')[:100]}"

    return None
