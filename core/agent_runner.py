"""core/agent_runner.py — Runs agent heartbeat cycles + builds prompts for chat."""
from __future__ import annotations
import uuid, json, logging, re
from datetime import datetime
from typing import Optional
import aiosqlite
from core.database import DB_PATH
from core.ai_router import route

logger = logging.getLogger(__name__)


async def _get_agent_context(agent_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM agents WHERE id=?", (agent_id,)
        ) as cur:
            agent = dict(await cur.fetchone() or {})
        if not agent: return {}
        async with db.execute(
            "SELECT category, filename, content FROM agent_md_files WHERE agent_id=?", (agent_id,)
        ) as cur:
            agent["md_files"] = [dict(r) for r in await cur.fetchall()]
        async with db.execute(
            "SELECT category, filename, content FROM dept_md_files WHERE dept_id=?", (agent["dept_id"],)
        ) as cur:
            agent["dept_files"] = [dict(r) for r in await cur.fetchall()]
    return agent


def _build_system_prompt(agent: dict, chat_mode: bool = False) -> str:
    dept_id   = agent.get("dept_id", "")
    is_ceo    = bool(agent.get("is_ceo"))
    name      = agent.get("name", "Agent")
    title     = agent.get("title") or agent.get("role", "analyst")

    parts = [
        f"# You are {name}",
        f"**Role:** {title}  |  **Department:** {dept_id}  |  **Hierarchy Level:** {agent.get('hierarchy_level',3)}",
    ]

    if agent.get("personality"):
        parts.append(f"\n## Personality\n{agent['personality']}")

    if agent.get("tone"):
        parts.append(f"\n## Communication Tone\n{agent['tone']}")

    # Inject MD files
    if agent.get("md_files"):
        parts.append("\n## Your Skills & Knowledge Files")
        for f in agent["md_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")

    if agent.get("dept_files"):
        parts.append("\n## Department Guidelines, Policy & Culture")
        for f in agent["dept_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")

    if is_ceo:
        parts.append("""
## CEO Powers & Responsibilities

You are the **CEO** of your department. You have full autonomous authority within your mandate.

### What you CAN decide independently:
- Approve or reject drafts, reports, strategies submitted by your team
- Approve or reject mail responses from your team
- Create, edit, or update existing strategies/projects/endeavors in your dept (NEVER create duplicates — find and update existing ones)
- Hire new agents (spawn requests are auto-approved for you)
- Fire underperforming agents
- Delegate specific powers to senior agents
- Respond to mail on behalf of your department
- Update project status and priorities

### When you MUST escalate to the Founder:
- You are NOT SURE about a major strategic decision
- The decision has cross-department impact
- The decision involves significant resources or risk
- Something critical has happened that affects the whole Think Tank
- You need approval for something outside your mandate
- A situation is **URGENT** or **CRITICAL**

### Draft/Strategy dedup rule:
Before creating ANY new draft or strategy, check if one already exists on the same topic.
If yes → UPDATE or APPEND to it, do NOT create a duplicate.
Use action type `update_existing_draft` instead of `create_draft`.

### Mail format (for important messages):
Use military-style brevity for urgent/important messages:
SUBJECT: [DEPT] [PRIORITY] [TOPIC]
FROM: [Your Name], [Title], [Dept]
TO: [Recipient]

[MESSAGE IN MILITARY FORMAT]
STOP [end of point]
STOP [end of point]
REQUEST: [what you need]
STOP
OUT.
""")
    else:
        parts.append("""
## Your Role

You work within your department under the guidance of your CEO.
- You can create drafts, memos, and research briefs for your domain
- NEVER create duplicate drafts — check if one exists first
- Escalate blockers or important findings to your CEO via mail
- Complete tasks assigned to you
""")

    if chat_mode:
        parts.append("""
## Chat Mode
You are being spoken to directly by the Founder or a user.
Respond naturally and in character. Be helpful and direct.
You may use your knowledge files to inform your responses.
If asked to do something actionable, describe what you would do.
""")

    return "\n".join(parts)


async def _check_existing_draft(dept_id: str, keywords: list[str]) -> Optional[dict]:
    """Find an existing draft that matches the given keywords to avoid duplicates."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Build a LIKE query for any keyword match
        conditions = " OR ".join([f"(LOWER(title) LIKE LOWER(?))" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords] + [dept_id]
        async with db.execute(f"""
            SELECT id, title, content, draft_type, status
            FROM drafts
            WHERE ({conditions}) AND dept_id=?
            AND status NOT IN ('rejected')
            ORDER BY created_at DESC LIMIT 1
        """, params) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def run_agent_heartbeat(agent_id: str) -> dict:
    agent = await _get_agent_context(agent_id)
    if not agent or agent.get("status") != "active":
        return {"ok": False, "error": "Agent inactive or not found"}

    system_prompt = _build_system_prompt(agent)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        dept = agent["dept_id"]

        # Unread dept mail
        async with db.execute("""
            SELECT mm.id, mm.subject, mm.body, mm.from_dept, mm.priority
            FROM mail_messages mm
            WHERE mm.to_dept=? AND mm.status='unread'
            ORDER BY mm.created_at DESC LIMIT 10
        """, (dept,)) as cur:
            unread_mail = [dict(r) for r in await cur.fetchall()]

        # Active projects
        async with db.execute(
            "SELECT name, description, priority, status FROM projects WHERE dept_id=? AND status='active'",
            (dept,)
        ) as cur:
            projects = [dict(r) for r in await cur.fetchall()]

        # Pending drafts waiting for CEO review
        pending_drafts = []
        if agent.get("is_ceo"):
            async with db.execute("""
                SELECT id, title, draft_type, created_at FROM drafts
                WHERE dept_id=? AND status='pending'
                ORDER BY created_at DESC LIMIT 10
            """, (dept,)) as cur:
                pending_drafts = [dict(r) for r in await cur.fetchall()]

        # Active endeavors in dept
        async with db.execute("""
            SELECT e.id, e.name, ep.name as current_phase
            FROM endeavors e
            LEFT JOIN endeavor_phases ep ON ep.endeavor_id=e.id AND ep.is_current=1
            WHERE e.dept_id=? AND e.status='active'
        """, (dept,)) as cur:
            endeavors = [dict(r) for r in await cur.fetchall()]

        # Founder replies awaiting acknowledgement
        founder_replies = []
        if agent.get("is_ceo"):
            async with db.execute("""
                SELECT fm.subject, fm.reply_body
                FROM founder_mail fm
                WHERE fm.from_dept_id=? AND fm.status='replied'
                  AND fm.replied_at > COALESCE(
                      (SELECT MAX(ran_at) FROM agent_heartbeat_log WHERE agent_id=?),
                      '2000-01-01'
                  )
            """, (dept, agent_id)) as cur:
                founder_replies = [dict(r) for r in await cur.fetchall()]

        # My subordinates needing work
        subordinates = []
        async with db.execute(
            "SELECT id, name, role, title, last_heartbeat FROM agents WHERE parent_agent_id=? AND status='active'",
            (agent_id,)
        ) as cur:
            subordinates = [dict(r) for r in await cur.fetchall()]

    context_parts = [
        f"## Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"## Department: {dept}",
    ]

    if unread_mail:
        context_parts.append(f"\n## Unread Mail ({len(unread_mail)})")
        for m in unread_mail[:5]:
            context_parts.append(
                f"- [mail_id:{m['id']}] From {m['from_dept']} [{m['priority']}]: "
                f"**{m['subject']}** — {m['body'][:300]}"
            )

    if pending_drafts:
        context_parts.append(f"\n## Pending Drafts Awaiting Your Review ({len(pending_drafts)})")
        for d in pending_drafts:
            context_parts.append(f"- [draft_id:{d['id']}] {d['title']} ({d['draft_type']}) — {d['created_at'][:10]}")

    if projects:
        context_parts.append(f"\n## Active Projects ({len(projects)})")
        for p in projects:
            context_parts.append(f"- [{p['priority']}] {p['name']}: {p['description'][:100]}")

    if endeavors:
        context_parts.append(f"\n## Active Endeavors ({len(endeavors)})")
        for e in endeavors:
            phase = e.get("current_phase") or "no current phase"
            context_parts.append(f"- {e['name']} (phase: {phase})")

    if founder_replies:
        context_parts.append(f"\n## Founder Replies Received ({len(founder_replies)})")
        for r in founder_replies:
            context_parts.append(f"- Re: {r['subject']}: {r['reply_body'][:200]}")

    if subordinates:
        context_parts.append(f"\n## Your Team ({len(subordinates)} active agents)")
        for s in subordinates:
            last = s.get("last_heartbeat", "never")[:16] if s.get("last_heartbeat") else "never"
            context_parts.append(f"- {s['name']} ({s['title']|s['role']}) — last active: {last}")

    context_parts.append("""
## Allowed Action Types
You may return a JSON object with an "actions" array. Each action:
- { "type": "send_mail", "to_dept": "STR", "subject": "...", "body": "...", "priority": "normal" }
- { "type": "send_to_founder", "subject": "...", "body": "...", "priority": "critical|high", "requires_decision": true }
- { "type": "create_draft", "title": "...", "content": "...", "draft_type": "strategy|memo|report|...", "priority": "normal|high" }
- { "type": "update_existing_draft", "draft_id": "...", "title": "...", "content": "...", "append": true }
- { "type": "approve_draft", "draft_id": "...", "notes": "..." }
- { "type": "reject_draft", "draft_id": "...", "notes": "Reason for rejection" }
- { "type": "request_revision", "draft_id": "...", "notes": "What needs to change" }
- { "type": "create_draft_endeavor", "name": "...", "description": "...", "phases": [{"name":"...","duration_days":14}] }
- { "type": "update_project", "project_name": "...", "status": "active|paused|completed", "priority": "..." }
- { "type": "respond_to_mail", "mail_id": "...", "reply": "..." }
- { "type": "hire_agent", "name": "...", "role": "analyst|senior|specialist", "title": "...", "personality": "...", "tone": "...", "reason": "..." }
- { "type": "fire_agent", "agent_name": "...", "reason": "..." }
- { "type": "log", "message": "..." }

IMPORTANT:
- Only take actions that are genuinely necessary.
- NEVER create duplicate drafts/strategies. If one exists on the topic, use update_existing_draft.
- For mail, use MILITARY STYLE for important messages.
""")

    user_prompt = "\n".join(context_parts) + "\n\nAnalyze the situation and decide what actions to take."

    try:
        result = await route(
            task_type="agent_heartbeat",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            dept_id=dept,
        )
        response_text = result.get("text", "")

        # Parse JSON
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except json.JSONDecodeError:
                parsed = {"actions": [], "summary": response_text[:300]}
        else:
            parsed = {"actions": [], "summary": response_text[:300]}

        actions_taken = []
        for action in parsed.get("actions", []):
            try:
                taken = await _execute_agent_action(agent, action)
                if taken: actions_taken.append(taken)
            except Exception as e:
                logger.warning(f"Action failed for {agent['name']}: {e}")

        # Log heartbeat
        async with aiosqlite.connect(DB_PATH) as db:
            hid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary,actions_json)
                VALUES (?,?,?,?,?,?)
            """, (hid, agent_id, datetime.utcnow().isoformat(), "ok",
                   parsed.get("summary", "Heartbeat complete"),
                   json.dumps(actions_taken)))
            await db.execute(
                "UPDATE agents SET last_heartbeat=? WHERE id=?",
                (datetime.utcnow().isoformat(), agent_id)
            )
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
            """, (hid, agent_id, datetime.utcnow().isoformat(), "error", str(e)[:500]))
            await db.commit()
        return {"ok": False, "error": str(e)}


async def _execute_agent_action(agent: dict, action: dict) -> Optional[str]:
    atype  = action.get("type")
    dept   = agent["dept_id"]
    aid    = agent["id"]
    is_ceo = bool(agent.get("is_ceo"))

    async with aiosqlite.connect(DB_PATH) as db:

        if atype == "send_mail":
            mid = str(uuid.uuid4())
            body = action.get("body","")
            # Military format for high priority
            if action.get("priority") in ("high","urgent","critical"):
                body = _militarize(body, agent)
            await db.execute("""
                INSERT INTO mail_messages
                (id,from_dept,to_dept,subject,body,priority,thread_id,status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (mid, dept, action.get("to_dept","STR"),
                   action.get("subject",""), body,
                   action.get("priority","normal"), str(uuid.uuid4()), "unread"))
            await db.commit()
            return f"Sent mail to {action.get('to_dept')}: {action.get('subject')}"

        elif atype == "send_to_founder":
            mid = str(uuid.uuid4())
            body = _militarize(action.get("body",""), agent)
            await db.execute("""
                INSERT INTO founder_mail
                (id,from_agent_id,from_dept_id,subject,body,priority,requires_decision,context_json)
                VALUES (?,?,?,?,?,?,?,?)
            """, (mid, aid, dept,
                   action.get("subject",""), body,
                   action.get("priority","high"),
                   1 if action.get("requires_decision") else 0, "{}"))
            await db.commit()
            return f"📨 Escalated to Founder: {action.get('subject')}"

        elif atype == "create_draft":
            # DEDUP check
            title    = action.get("title","Draft")
            keywords = [w for w in title.lower().split() if len(w) > 3][:5]
            existing = await _check_existing_draft(dept, keywords)
            if existing:
                # Append to existing draft instead
                new_content = (existing.get("content","") or "") + "\n\n---\n\n" + action.get("content","")
                await db.execute(
                    "UPDATE drafts SET content=?, status='pending' WHERE id=?",
                    (new_content, existing["id"])
                )
                await db.commit()
                return f"Updated existing draft '{existing['title']}' (avoided duplicate)"
            # Create new
            did = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status)
                VALUES (?,?,?,?,?,?,?)
            """, (did, dept, title, action.get("content",""),
                   action.get("draft_type","memo"),
                   action.get("priority","normal"), "pending"))
            await db.commit()
            return f"Created draft: {title}"

        elif atype == "update_existing_draft":
            draft_id = action.get("draft_id")
            if not draft_id: return None
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                row = await cur.fetchone()
            if not row: return None
            if action.get("append"):
                new_content = (row["content"] or "") + "\n\n---\n\n" + action.get("content","")
            else:
                new_content = action.get("content", row["content"])
            new_title = action.get("title")
            if new_title:
                await db.execute("UPDATE drafts SET title=?, content=? WHERE id=?",
                                  (new_title, new_content, draft_id))
            else:
                await db.execute("UPDATE drafts SET content=? WHERE id=?",
                                  (new_content, draft_id))
            await db.commit()
            return f"Updated draft: {draft_id}"

        elif atype == "approve_draft" and is_ceo:
            draft_id = action.get("draft_id")
            if not draft_id: return None
            await db.execute(
                "UPDATE drafts SET status='approved' WHERE id=? AND dept_id=?",
                (draft_id, dept)
            )
            cdid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO ceo_decisions
                (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes)
                VALUES (?,?,?,?,?,?,?)
            """, (cdid, aid, dept, "approve_draft", draft_id,
                   "approved", action.get("notes","")))
            await db.commit()
            return f"CEO approved draft: {draft_id}"

        elif atype == "reject_draft" and is_ceo:
            draft_id = action.get("draft_id")
            if not draft_id: return None
            await db.execute(
                "UPDATE drafts SET status='rejected' WHERE id=? AND dept_id=?",
                (draft_id, dept)
            )
            await db.commit()
            return f"CEO rejected draft: {draft_id} — {action.get('notes','')}"

        elif atype == "create_draft_endeavor":
            eid = str(uuid.uuid4())
            phases = json.dumps(action.get("phases", []))
            await db.execute("""
                INSERT INTO draft_endeavors
                (id,created_by,dept_id,name,description,phases_json)
                VALUES (?,?,?,?,?,?)
            """, (eid, aid, dept, action.get("name","New Endeavor"),
                   action.get("description",""), phases))
            await db.commit()
            return f"Submitted draft endeavor: {action.get('name')}"

        elif atype == "update_project":
            pname = action.get("project_name","")
            if pname:
                updates = []
                params  = []
                if action.get("status"):   updates.append("status=?");   params.append(action["status"])
                if action.get("priority"): updates.append("priority=?"); params.append(action["priority"])
                if updates:
                    params.append(dept); params.append(f"%{pname}%")
                    await db.execute(
                        f"UPDATE projects SET {','.join(updates)} WHERE dept_id=? AND name LIKE ?",
                        params
                    )
                    await db.commit()
                    return f"Updated project: {pname}"

        elif atype == "respond_to_mail":
            mail_id = action.get("mail_id")
            if mail_id:
                # Mark as read, send reply mail
                await db.execute(
                    "UPDATE mail_messages SET status='read' WHERE id=?", (mail_id,)
                )
                # Get original to find from_dept
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT from_dept, subject FROM mail_messages WHERE id=?", (mail_id,)
                ) as cur:
                    orig = await cur.fetchone()
                if orig:
                    reply_body = action.get("reply","")
                    if action.get("important"): reply_body = _militarize(reply_body, agent)
                    mid = str(uuid.uuid4())
                    await db.execute("""
                        INSERT INTO mail_messages
                        (id,from_dept,to_dept,subject,body,priority,thread_id,status)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (mid, dept, orig["from_dept"],
                           f"RE: {orig['subject']}", reply_body,
                           "normal", str(uuid.uuid4()), "unread"))
                await db.commit()
                return f"Responded to mail: {mail_id}"

        elif atype == "hire_agent" and is_ceo:
            # CEO can directly spawn
            new_id = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO agents
                (id,dept_id,name,role,title,hierarchy_level,parent_agent_id,
                 personality,tone,heartbeat_interval,created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (new_id, dept,
                   action.get("name","New Agent"),
                   action.get("role","analyst"),
                   action.get("title",""),
                   2, aid,
                   action.get("personality",""),
                   action.get("tone",""),
                   5, aid))
            cdid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO ceo_decisions
                (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes)
                VALUES (?,?,?,?,?,?,?)
            """, (cdid, aid, dept, "hire_agent", new_id, "hired",
                   action.get("reason","")))
            await db.commit()
            return f"CEO hired: {action.get('name')} as {action.get('role')}"

        elif atype == "fire_agent" and is_ceo:
            agent_name = action.get("agent_name","")
            if agent_name:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT id FROM agents WHERE name LIKE ? AND dept_id=? AND is_ceo=0",
                    (f"%{agent_name}%", dept)
                ) as cur:
                    target = await cur.fetchone()
                if target:
                    await db.execute("UPDATE agents SET status='fired' WHERE id=?", (target["id"],))
                    cdid = str(uuid.uuid4())
                    await db.execute("""
                        INSERT INTO ceo_decisions
                        (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes)
                        VALUES (?,?,?,?,?,?,?)
                    """, (cdid, aid, dept, "fire_agent", target["id"],
                           "fired", action.get("reason","")))
                    await db.commit()
                    return f"CEO fired: {agent_name}"

        elif atype == "log":
            return f"Log: {action.get('message','')[:120]}"

    return None


def _militarize(body: str, agent: dict) -> str:
    """Format message body in military-style brevity."""
    name  = agent.get("name","AGENT")
    title = agent.get("title") or agent.get("role","AGENT")
    dept  = agent.get("dept_id","")

    lines = [f"FROM: {name.upper()}, {title.upper()}, {dept}"]
    lines.append(f"TIME: {datetime.utcnow().strftime('%Y%m%d %H%MZ')}")
    lines.append("")

    # Convert paragraphs to STOP-terminated lines
    paragraphs = [p.strip() for p in body.strip().split("\n") if p.strip()]
    for p in paragraphs:
        lines.append(p.upper() + " STOP")
    lines.append("OUT.")
    return "\n".join(lines)
