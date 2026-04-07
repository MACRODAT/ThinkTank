"""core/agent_runner.py
Heartbeat engine + chat tool-use handler.
Prompt order:
  1. global prepend
  2. dept system prompt
  3. agent personality/tone
  4. agent MD files
  5. pending drafts destined for agent
  6. dept mail
  7. global append
"""
from __future__ import annotations
import uuid, json, logging, re
from datetime import datetime, date
from typing import Optional
import aiosqlite
from core.database import DB_PATH
from core.ai_router import route

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Settings helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_global_prompts() -> tuple[str, str]:
    """Return (prepend, append) from app_settings."""
    try:
        from api.routes.settings import _load
        s = await _load()
        return s.get("custom_prompt_prepend", ""), s.get("custom_prompt_append", "")
    except Exception:
        return "", ""


# ─────────────────────────────────────────────────────────────────────────────
#  Context loader
# ─────────────────────────────────────────────────────────────────────────────

async def _get_agent_context(agent_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)) as cur:
            agent = dict(await cur.fetchone() or {})
        if not agent:
            return {}
        async with db.execute(
            "SELECT category, filename, content FROM agent_md_files WHERE agent_id=? ORDER BY category, filename",
            (agent_id,)
        ) as cur:
            agent["md_files"] = [dict(r) for r in await cur.fetchall()]
        async with db.execute(
            "SELECT category, filename, content FROM dept_md_files WHERE dept_id=? ORDER BY category, filename",
            (agent["dept_id"],)
        ) as cur:
            agent["dept_files"] = [dict(r) for r in await cur.fetchall()]
        # dept system prompt
        async with db.execute(
            "SELECT system_prompt FROM dept_prompts WHERE dept_id=?", (agent["dept_id"],)
        ) as cur:
            row = await cur.fetchone()
            agent["dept_system_prompt"] = row["system_prompt"] if row else ""
    return agent


async def _get_hierarchy(agent_id: str) -> dict:
    """Return direct superior and direct reports."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM agents WHERE id=?", (agent_id,)
        ) as cur:
            me = dict(await cur.fetchone() or {})
        superior = None
        if me.get("parent_agent_id"):
            async with db.execute(
                "SELECT id,name,role,title,dept_id,is_ceo FROM agents WHERE id=?",
                (me["parent_agent_id"],)
            ) as cur:
                row = await cur.fetchone()
                superior = dict(row) if row else None
        async with db.execute(
            "SELECT id,name,role,title,dept_id FROM agents WHERE parent_agent_id=? AND status='active'",
            (agent_id,)
        ) as cur:
            reports = [dict(r) for r in await cur.fetchall()]
    return {"superior": superior, "reports": reports}


async def _can_act_on(acting_agent_id: str, target_agent_id: str) -> bool:
    """True if acting agent is in the target's chain of command (superior or same dept CEO)."""
    if acting_agent_id == target_agent_id:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Walk up the chain from target
        current = target_agent_id
        for _ in range(10):
            async with db.execute("SELECT parent_agent_id, dept_id FROM agents WHERE id=?", (current,)) as cur:
                row = await cur.fetchone()
            if not row or not row["parent_agent_id"]:
                break
            if row["parent_agent_id"] == acting_agent_id:
                return True
            current = row["parent_agent_id"]
        # Allow if acting agent is CEO of same dept
        async with db.execute(
            "SELECT a.is_ceo, a.dept_id FROM agents a WHERE a.id=?", (acting_agent_id,)
        ) as cur:
            me = await cur.fetchone()
        async with db.execute("SELECT dept_id FROM agents WHERE id=?", (target_agent_id,)) as cur:
            tgt = await cur.fetchone()
        if me and tgt and me["is_ceo"] and me["dept_id"] == tgt["dept_id"]:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
#  Tool specification
# ─────────────────────────────────────────────────────────────────────────────

CHAT_TOOLS_SPEC = """
## Available Tools

Emit tool calls anywhere in your response:
  [TOOL_CALL: {"tool": "tool_name", "params": {...}}]

Results come back as [TOOL:name]...[/TOOL].

| Tool | Key Params | What it does |
|------|-----------|-------------|
| list_dept_files | dept_id | List all MD files for a department |
| read_dept_file | dept_id, filename | Read a dept MD file |
| write_dept_file | dept_id, filename, category, content | Create/update a dept file |
| read_agent_file | agent_id?, filename | Read one of your skill/personality files |
| write_agent_file | agent_id?, category, filename, content | Update your own files |
| list_drafts | dept_id?, status | List drafts (status: pending/revised/approved/all) |
| search_drafts | dept_id?, query | Search drafts by title keyword |
| read_draft | draft_id | Read full content of a draft |
| create_draft | dept_id?, title, content, draft_type, priority | Create new draft (dedup check built-in) |
| update_draft | draft_id, content, title?, append? | Update/append to existing draft |
| change_draft_status | draft_id, status, notes?, reviewed_by? | Set draft status: revised/approved/rejected/pending/archived |
| revert_draft_to_pending | draft_id | Pull an approved draft back to pending for editing |
| delegate_draft | draft_id, to_agent_id, notes? | Assign a draft to a reporting agent |
| request_superior_review | draft_id, notes? | Send a draft up to your direct superior for review |
| list_endeavors | dept_id? | List active endeavors |
| create_endeavor_proposal | name, description, phases | Submit draft endeavor for Founder review |
| get_mail | dept_id? | Show unarchived mail sent to your department |
| delete_mail | mail_id | Archive a mail (hide unless explicitly requested) |
| send_mail | to_dept, subject, body, priority? | Send mail to another department |
| forward_mail | mail_id, to_dept, note? | Forward an existing mail to another department |
| send_to_founder | subject, body, priority?, requires_decision? | Escalate directly to Founder AND your CEO |
| write_to_founder | subject, body, priority? | Urgent message directly to Founder and CEO |
| get_superior | | Get your direct superior agent info |
| get_subordinates | | Get agents reporting directly to you |
| hire_agent | name, role, title, personality, tone, reason | (CEO only) Directly hire a new agent |
| list_agents | dept_id? | List agents in a department |
| update_project | project_name, status?, priority? | Update a project's status or priority |

**HIERARCHY RULE:** You may only take actions on agents that report to you (directly or transitively). You cannot send mail or create work for agents outside your chain of command.
"""

HEARTBEAT_ACTIONS_SPEC = """
## Allowed Heartbeat Actions (JSON with "actions" array)

RULES:
1. MINIMIZE — only act when genuinely needed.
2. STRICT DEDUP — search before creating ANY draft. Update existing ones.
3. MAIL DISCIPLINE — one mail per recipient per topic.
4. HIERARCHY — only act on personnel reporting to you.
5. REVISED DRAFTS — if you see drafts with REVISION REQUEST notes, address them FIRST.

Actions:
{ "type": "send_mail", "to_dept": "STR", "subject": "...", "body": "...", "priority": "normal" }
{ "type": "send_to_founder", "subject": "...", "body": "...", "priority": "high", "requires_decision": true }
{ "type": "create_draft", "title": "...", "content": "...", "draft_type": "strategy|memo|report|weekly_report", "priority": "normal" }
{ "type": "update_existing_draft", "draft_id": "...", "content": "...", "title": "...", "append": true }
{ "type": "revert_approved_draft", "draft_id": "...", "reason": "..." }
{ "type": "approve_draft", "draft_id": "...", "notes": "..." }
{ "type": "reject_draft", "draft_id": "...", "notes": "Reason" }
{ "type": "request_revision", "draft_id": "...", "notes": "What needs changing" }
{ "type": "create_draft_endeavor", "name": "...", "description": "...", "phases": [...] }
{ "type": "update_project", "project_name": "...", "status": "active|completed", "priority": "..." }
{ "type": "respond_to_mail", "mail_id": "...", "reply": "...", "important": false }
{ "type": "archive_mail", "mail_id": "..." }
{ "type": "hire_agent", "name": "...", "role": "analyst", "title": "...", "personality": "...", "tone": "...", "reason": "..." }
{ "type": "fire_agent", "agent_name": "...", "reason": "..." }
{ "type": "invoke_subordinates", "reason": "..." }
{ "type": "weekly_report", "content": "...", "agent_briefs": [...] }
{ "type": "log", "message": "..." }
"""


def _build_system_prompt(agent: dict, chat_mode: bool = False,
                          prepend: str = "", append: str = "") -> str:
    dept_id = agent.get("dept_id", "")
    is_ceo  = bool(agent.get("is_ceo"))
    name    = agent.get("name", "Agent")
    title   = agent.get("title") or agent.get("role", "analyst")

    parts = []

    # 1. Global prepend
    if prepend.strip():
        parts.append(f"# Global System Context\n{prepend.strip()}\n")

    # 2. Dept system prompt
    dept_prompt = agent.get("dept_system_prompt", "").strip()
    if dept_prompt:
        parts.append(f"# Department System Prompt\n{dept_prompt}\n")
    elif agent.get("dept_files"):
        parts.append(f"# Department: {dept_id} — Guidelines & Policy")
        for f in agent["dept_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")

    # 3. Agent identity + personality + tone
    parts.append(f"# You are {name}")
    parts.append(f"**Role:** {title} | **Department:** {dept_id} | **Level:** {agent.get('hierarchy_level', 3)}")

    if agent.get("personality"):
        parts.append(f"\n## Personality\n{agent['personality']}")
    if agent.get("tone"):
        parts.append(f"\n## Communication Tone\n{agent['tone']}")

    # 4. Agent MD files
    if agent.get("md_files"):
        parts.append("\n## Your Skills & Knowledge Files")
        for f in agent["md_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")

    # 5. CEO / role rules
    if is_ceo:
        parts.append("""
## CEO Authority

You lead your department. Full autonomous authority within mandate.

**Independent decisions:** approve/reject drafts, respond to mail, create/edit strategies,
hire/fire agents, delegate to senior agents, update projects.

**Escalate to Founder when:** unsure about major decision, cross-dept impact,
resource authority exceeded, critical/urgent situation.

**Weekly Report (Monday):** invoke all agents → collect briefs → write and submit one weekly report.

**Strict dedup:** Search BEFORE any draft action. Approved draft on same topic → revert to pending, then edit.

**Mail discipline:** ONE mail per recipient per topic. Use military format for urgent matters.

**Hierarchy:** You may only directly manage agents in your department.
""")
    else:
        parts.append("""
## Your Role
- Produce drafts within your domain. CHECK for existing drafts first.
- Max ONE mail per topic. Keep mails short.
- Escalate only genuinely important items to your CEO.
- Only interact with agents that report to you or your direct superior.
""")

    # 6. Tools spec
    if chat_mode:
        parts.append(CHAT_TOOLS_SPEC)
        parts.append("""
## Chat Mode

You are speaking with the Founder. Be direct and in-character.
When using tools: announce what you're doing, emit [TOOL_CALL: {...}], reference the result.
""")
    else:
        parts.append(HEARTBEAT_ACTIONS_SPEC)

    # 7. Global append
    if append.strip():
        parts.append(f"\n# Additional Global Instructions\n{append.strip()}")

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  Chat tool executor
# ─────────────────────────────────────────────────────────────────────────────

async def execute_chat_tool(tool: str, params: dict, agent: dict) -> str:
    dept_id = agent.get("dept_id", "")
    aid     = agent.get("id", "")
    is_ceo  = bool(agent.get("is_ceo"))

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            if tool == "list_dept_files":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute(
                    "SELECT category, filename, updated_at FROM dept_md_files WHERE dept_id=? ORDER BY category, filename",
                    (d,)
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No files found."

            elif tool == "read_dept_file":
                d  = params.get("dept_id", dept_id).upper()
                fn = params.get("filename", "")
                async with db.execute(
                    "SELECT content, category FROM dept_md_files WHERE dept_id=? AND filename=?", (d, fn)
                ) as cur:
                    row = await cur.fetchone()
                return row["content"] if row else f"File '{fn}' not found."

            elif tool == "write_dept_file":
                d   = params.get("dept_id", dept_id).upper()
                fn  = params.get("filename", "")
                cat = params.get("category", "guidelines")
                con = params.get("content", "")
                ts  = datetime.utcnow().isoformat()
                async with db.execute(
                    "SELECT id FROM dept_md_files WHERE dept_id=? AND filename=?", (d, fn)
                ) as cur:
                    existing = await cur.fetchone()
                if existing:
                    await db.execute(
                        "UPDATE dept_md_files SET content=?, category=?, updated_at=? WHERE id=?",
                        (con, cat, ts, existing["id"])
                    )
                else:
                    await db.execute(
                        "INSERT INTO dept_md_files (id,dept_id,category,filename,content) VALUES (?,?,?,?,?)",
                        (str(uuid.uuid4()), d, cat, fn, con)
                    )
                await db.commit()
                return f"✓ Written: {fn} ({len(con)} chars)"

            elif tool == "read_agent_file":
                a_id = params.get("agent_id", aid)
                fn   = params.get("filename", "")
                async with db.execute(
                    "SELECT content FROM agent_md_files WHERE agent_id=? AND filename=?", (a_id, fn)
                ) as cur:
                    row = await cur.fetchone()
                return row["content"] if row else f"File '{fn}' not found."

            elif tool == "write_agent_file":
                a_id = params.get("agent_id", aid)
                fn   = params.get("filename", "")
                cat  = params.get("category", "knowledge")
                con  = params.get("content", "")
                ts   = datetime.utcnow().isoformat()
                async with db.execute(
                    "SELECT id FROM agent_md_files WHERE agent_id=? AND filename=?", (a_id, fn)
                ) as cur:
                    existing = await cur.fetchone()
                if existing:
                    await db.execute("UPDATE agent_md_files SET content=?, updated_at=? WHERE id=?",
                                     (con, ts, existing["id"]))
                else:
                    await db.execute(
                        "INSERT INTO agent_md_files (id,agent_id,category,filename,content) VALUES (?,?,?,?,?)",
                        (str(uuid.uuid4()), a_id, cat, fn, con)
                    )
                await db.commit()
                return f"✓ Written agent file: {fn}"

            elif tool == "list_drafts":
                d      = params.get("dept_id", dept_id).upper()
                status = params.get("status", "pending")
                if status == "all":
                    async with db.execute(
                        "SELECT id,title,draft_type,status,created_at,reviewed_by,reviewed_at FROM drafts WHERE dept_id=? ORDER BY created_at DESC LIMIT 20",
                        (d,)
                    ) as cur:
                        rows = [dict(r) for r in await cur.fetchall()]
                else:
                    async with db.execute(
                        "SELECT id,title,draft_type,status,created_at,reviewed_by,reviewed_at FROM drafts WHERE dept_id=? AND status=? ORDER BY created_at DESC LIMIT 20",
                        (d, status)
                    ) as cur:
                        rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No drafts found."

            elif tool == "search_drafts":
                d     = params.get("dept_id", dept_id).upper()
                query = params.get("query", "")
                async with db.execute(
                    "SELECT id,title,draft_type,status,reviewed_by,reviewed_at FROM drafts WHERE dept_id=? AND LOWER(title) LIKE LOWER(?) ORDER BY created_at DESC LIMIT 10",
                    (d, f"%{query}%")
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No matching drafts."

            elif tool == "read_draft":
                draft_id = params.get("draft_id", "")
                async with db.execute(
                    "SELECT id,title,content,draft_type,status,reviewed_by,reviewed_at FROM drafts WHERE id=?",
                    (draft_id,)
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    return "Draft not found."
                r = dict(row)
                rev_info = f" | Reviewed by: {r['reviewed_by']} at {r['reviewed_at'][:16]}" if r.get("reviewed_by") else ""
                return f"# {r['title']}\n**Type:** {r['draft_type']} | **Status:** {r['status']}{rev_info}\n\n{r['content']}"

            elif tool == "create_draft":
                d     = params.get("dept_id", dept_id).upper()
                title = params.get("title", "Draft")
                keywords = [w for w in title.lower().split() if len(w) > 3][:5]
                existing = await _check_existing_draft_raw(db, d, keywords)
                if existing:
                    return f"⚠ Existing draft found: '{existing['title']}' (id: {existing['id']}, status: {existing['status']}). Use update_draft instead."
                did = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status,created_by_agent) VALUES (?,?,?,?,?,?,?,?)",
                    (did, d, title, params.get("content",""),
                     params.get("draft_type","memo"), params.get("priority","normal"), "pending", aid)
                )
                await db.commit()
                return f"✓ Draft created: {title} (id: {did})"

            elif tool == "update_draft":
                draft_id    = params.get("draft_id","")
                append      = params.get("append", False)
                new_content = params.get("content","")
                new_title   = params.get("title")
                async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                    row = await cur.fetchone()
                if not row:
                    return "Draft not found."
                final = (row["content"] or "") + "\n\n---\n\n" + new_content if append else new_content
                if new_title:
                    await db.execute("UPDATE drafts SET content=?, title=?, status='pending' WHERE id=?",
                                     (final, new_title, draft_id))
                else:
                    await db.execute("UPDATE drafts SET content=?, status='pending' WHERE id=?",
                                     (final, draft_id))
                await db.commit()
                return f"✓ Draft updated ({len(final)} chars)"

            elif tool == "change_draft_status":
                draft_id    = params.get("draft_id","")
                new_status  = params.get("status","pending")
                notes       = params.get("notes","")
                rev_by      = params.get("reviewed_by", agent.get("name","agent"))
                valid       = {"revised","approved","rejected","pending","archived"}
                if new_status not in valid:
                    return f"Invalid status. Use one of: {valid}"
                # Block approving a revised draft
                if new_status == "approved":
                    async with db.execute("SELECT status FROM drafts WHERE id=?", (draft_id,)) as cur:
                        row = await cur.fetchone()
                    if row and row["status"] == "revised":
                        return "⚠ Cannot approve a 'revised' draft — creator must review the changes first."
                ts = datetime.utcnow().isoformat()
                if new_status == "revised" and notes:
                    async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                        row = await cur.fetchone()
                    note_block = f"\n\n---\n**📝 REVISION REQUEST [{ts[:16]}] by {rev_by}:**\n{notes}"
                    await db.execute(
                        "UPDATE drafts SET status='revised', review_notes=?, revised_by=?, revised_at=?, content=? WHERE id=?",
                        (notes, rev_by, ts, (row["content"] if row else "") + note_block, draft_id)
                    )
                else:
                    await db.execute(
                        "UPDATE drafts SET status=?, review_notes=?, reviewed_by=?, reviewed_at=? WHERE id=?",
                        (new_status, notes, rev_by, ts, draft_id)
                    )
                await db.commit()
                return f"✓ Draft status changed to '{new_status}'"

            elif tool == "revert_draft_to_pending":
                draft_id = params.get("draft_id","")
                await db.execute("UPDATE drafts SET status='pending' WHERE id=?", (draft_id,))
                await db.commit()
                return f"✓ Draft {draft_id} reverted to pending."

            elif tool == "delegate_draft":
                draft_id    = params.get("draft_id","")
                to_agent_id = params.get("to_agent_id","")
                notes       = params.get("notes","")
                # Check hierarchy
                if not await _can_act_on(aid, to_agent_id):
                    return "⚠ Cannot delegate to an agent outside your chain of command."
                await db.execute("UPDATE drafts SET assigned_to=? WHERE id=?", (to_agent_id, draft_id))
                if notes:
                    async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                        row = await cur.fetchone()
                    note_block = f"\n\n---\n**📋 DELEGATED to {to_agent_id} by {agent.get('name','')}:**\n{notes}"
                    await db.execute("UPDATE drafts SET content=? WHERE id=?",
                                     ((row["content"] if row else "") + note_block, draft_id))
                await db.commit()
                return f"✓ Draft delegated to agent {to_agent_id}"

            elif tool == "request_superior_review":
                draft_id = params.get("draft_id","")
                notes    = params.get("notes","")
                h        = await _get_hierarchy(aid)
                superior = h.get("superior")
                if not superior:
                    return "No superior found — are you the CEO?"
                async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                    row = await cur.fetchone()
                note_block = f"\n\n---\n**🔼 REVIEW REQUESTED from {superior['name']} by {agent.get('name','')}:**\n{notes}"
                await db.execute("UPDATE drafts SET content=? WHERE id=?",
                                 ((row["content"] if row else "") + note_block, draft_id))
                await db.commit()
                return f"✓ Review requested from {superior['name']}"

            elif tool == "get_mail":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute("""
                    SELECT id,from_dept,to_dept,subject,body,priority,status,created_at
                    FROM mail_messages WHERE to_dept=? AND status != 'archived'
                    ORDER BY created_at DESC LIMIT 15
                """, (d,)) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                if not rows:
                    return "No unarchived mail."
                out = []
                for m in rows:
                    out.append(f"[{m['id'][:8]}] From {m['from_dept']} [{m['priority']}] {m['status']}: {m['subject']}\n  {m['body'][:120]}")
                return "\n\n".join(out)

            elif tool == "delete_mail":
                mail_id = params.get("mail_id","")
                await db.execute("UPDATE mail_messages SET status='archived' WHERE id=?", (mail_id,))
                await db.commit()
                return f"✓ Mail {mail_id} archived."

            elif tool == "send_mail":
                body = params.get("body","")
                if params.get("priority") in ("high","critical"):
                    body = _militarize(body, agent)
                mid = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, dept_id, params.get("to_dept","STR"),
                     params.get("subject",""), body, params.get("priority","normal"),
                     str(uuid.uuid4()), "unread")
                )
                await db.commit()
                return f"✓ Mail sent to {params.get('to_dept')}: {params.get('subject','')}"

            elif tool == "forward_mail":
                mail_id  = params.get("mail_id","")
                to_dept  = params.get("to_dept","")
                note     = params.get("note","")
                async with db.execute("SELECT * FROM mail_messages WHERE id=?", (mail_id,)) as cur:
                    orig = await cur.fetchone()
                if not orig:
                    return "Mail not found."
                body = f"[FORWARDED from {dict(orig)['from_dept']} by {agent.get('name','')}]\n{note}\n\n---\n{dict(orig)['body']}"
                mid = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, dept_id, to_dept.upper(),
                     f"FWD: {dict(orig)['subject']}", body, "normal", str(uuid.uuid4()), "unread")
                )
                await db.commit()
                return f"✓ Mail forwarded to {to_dept}"

            elif tool in ("send_to_founder", "write_to_founder"):
                body = _militarize(params.get("body",""), agent)
                mid  = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO founder_mail (id,from_agent_id,from_dept_id,subject,body,priority,requires_decision,context_json) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, aid, dept_id, params.get("subject",""), body,
                     params.get("priority","high"),
                     1 if params.get("requires_decision") else 0, "{}")
                )
                # Also send mail to CEO if not the CEO
                if not is_ceo:
                    async with db.execute(
                        "SELECT id,name FROM agents WHERE dept_id=? AND is_ceo=1 AND status='active'",
                        (dept_id,)
                    ) as cur:
                        ceo = await cur.fetchone()
                    if ceo:
                        await db.execute(
                            "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                            (str(uuid.uuid4()), dept_id, dept_id,
                             f"[FOUNDER ESCALATION] {params.get('subject','')}",
                             f"Sent to Founder by {agent.get('name','')}:\n\n{body}",
                             "high", str(uuid.uuid4()), "unread")
                        )
                await db.commit()
                return f"✓ Message sent to Founder: {params.get('subject','')}"

            elif tool == "get_superior":
                h = await _get_hierarchy(aid)
                sup = h.get("superior")
                if not sup:
                    return "No superior (you may be at the top of the hierarchy)."
                return json.dumps(sup, indent=2)

            elif tool == "get_subordinates":
                h = await _get_hierarchy(aid)
                reports = h.get("reports", [])
                return json.dumps(reports, indent=2) if reports else "No direct reports."

            elif tool == "hire_agent":
                if not is_ceo:
                    return "⚠ Only CEOs can hire agents directly."
                new_id_val = str(uuid.uuid4())
                async with db.execute("SELECT hierarchy_level FROM agents WHERE id=?", (aid,)) as cur:
                    row = await cur.fetchone()
                level = (row["hierarchy_level"] + 1) if row else 3
                await db.execute("""
                    INSERT INTO agents (id,dept_id,name,role,title,hierarchy_level,
                    parent_agent_id,personality,tone,heartbeat_interval,created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (new_id_val, dept_id, params.get("name","New Agent"),
                      params.get("role","analyst"), params.get("title",""),
                      level, aid, params.get("personality",""),
                      params.get("tone",""), 5, aid))
                await db.commit()
                return f"✓ Agent hired: {params.get('name')} as {params.get('role')} (id: {new_id_val})"

            elif tool == "list_agents":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute(
                    "SELECT id,name,role,title,is_ceo,status,hierarchy_level FROM agents WHERE dept_id=? AND status='active' ORDER BY hierarchy_level,name",
                    (d,)
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No active agents."

            elif tool == "list_endeavors":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute(
                    "SELECT id,name,status FROM endeavors WHERE dept_id=? AND status='active'", (d,)
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No active endeavors."

            elif tool == "create_endeavor_proposal":
                eid = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO draft_endeavors (id,created_by,dept_id,name,description,phases_json) VALUES (?,?,?,?,?,?)",
                    (eid, aid, dept_id, params.get("name",""), params.get("description",""),
                     json.dumps(params.get("phases",[])))
                )
                await db.commit()
                return f"✓ Endeavor proposal submitted (id: {eid})"

            elif tool == "update_project":
                pname = params.get("project_name","")
                updates, pms = [], []
                if params.get("status"):   updates.append("status=?");   pms.append(params["status"])
                if params.get("priority"): updates.append("priority=?"); pms.append(params["priority"])
                if updates and pname:
                    pms += [dept_id, f"%{pname}%"]
                    await db.execute(
                        f"UPDATE projects SET {','.join(updates)} WHERE dept_id=? AND name LIKE ?", pms
                    )
                    await db.commit()
                return f"✓ Project updated: {pname}"

    except Exception as e:
        return f"Tool error ({tool}): {str(e)}"

    return f"Unknown tool: {tool}"


async def _check_existing_draft_raw(db, dept_id: str, keywords: list) -> Optional[dict]:
    if not keywords:
        return None
    conditions = " OR ".join(["(LOWER(title) LIKE LOWER(?))"] * len(keywords))
    params = [f"%{k}%" for k in keywords] + [dept_id.upper()]
    async with db.execute(
        f"SELECT id,title,content,draft_type,status FROM drafts WHERE ({conditions}) AND dept_id=? AND status NOT IN ('rejected','archived') ORDER BY created_at DESC LIMIT 1",
        params
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def _check_existing_draft(dept_id: str, keywords: list) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _check_existing_draft_raw(db, dept_id, keywords)


# ─────────────────────────────────────────────────────────────────────────────
#  Chat with tool-call processing
# ─────────────────────────────────────────────────────────────────────────────

async def process_chat_with_tools(agent: dict, reply: str) -> tuple[str, list]:
    tool_log = []
    tool_call_re = re.compile(r'\[TOOL_CALL:\s*(\{.*?\})\s*\]', re.DOTALL)

    for _ in range(8):
        match = tool_call_re.search(reply)
        if not match:
            break
        try:
            call_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            break

        tool   = call_data.get("tool","")
        params = call_data.get("params",{})
        result = await execute_chat_tool(tool, params, agent)
        tool_log.append({"tool": tool, "params": params, "result": result[:400]})

        result_block = f"[TOOL:{tool}]\n{result}\n[/TOOL]"
        reply = reply[:match.start()] + result_block + reply[match.end():]

    return reply, tool_log


# ─────────────────────────────────────────────────────────────────────────────
#  Heartbeat
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent_heartbeat(agent_id: str) -> dict:
    agent = await _get_agent_context(agent_id)
    if not agent or agent.get("status") != "active":
        return {"ok": False, "error": "Agent inactive or not found"}

    prepend, append = await _get_global_prompts()
    system_prompt   = _build_system_prompt(agent, chat_mode=False, prepend=prepend, append=append)
    dept  = agent["dept_id"]
    is_ceo = bool(agent.get("is_ceo"))
    aid   = agent["id"]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Unread mail for dept
        async with db.execute(
            "SELECT id,subject,body,from_dept,priority FROM mail_messages WHERE to_dept=? AND status='unread' ORDER BY created_at DESC LIMIT 8",
            (dept,)
        ) as cur:
            unread_mail = [dict(r) for r in await cur.fetchall()]

        # All drafts (for dedup + CEO review)
        async with db.execute(
            "SELECT id,title,draft_type,status,reviewed_by,reviewed_at,review_notes,created_by_agent FROM drafts WHERE dept_id=? ORDER BY created_at DESC LIMIT 20",
            (dept,)
        ) as cur:
            all_drafts = [dict(r) for r in await cur.fetchall()]

        # Drafts specifically assigned to or created by this agent
        async with db.execute(
            "SELECT id,title,draft_type,status,review_notes FROM drafts WHERE (assigned_to=? OR created_by_agent=?) AND status IN ('pending','revised') ORDER BY created_at DESC LIMIT 10",
            (aid, aid)
        ) as cur:
            my_drafts = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT name,description,priority FROM projects WHERE dept_id=? AND status='active'", (dept,)
        ) as cur:
            projects = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT e.name, ep.name as phase FROM endeavors e LEFT JOIN endeavor_phases ep ON ep.endeavor_id=e.id AND ep.is_current=1 WHERE e.dept_id=? AND e.status='active'",
            (dept,)
        ) as cur:
            endeavors = [dict(r) for r in await cur.fetchall()]

        # Weekly report check
        week_start = date.today().strftime("%Y-W%W")
        async with db.execute(
            "SELECT id FROM drafts WHERE dept_id=? AND draft_type='weekly_report' AND title LIKE ? ORDER BY created_at DESC LIMIT 1",
            (dept, f"%{week_start}%")
        ) as cur:
            weekly_exists = bool(await cur.fetchone())

        # Subordinates
        async with db.execute(
            "SELECT id,name,role,title,last_heartbeat FROM agents WHERE parent_agent_id=? AND status='active'",
            (aid,)
        ) as cur:
            subordinates = [dict(r) for r in await cur.fetchall()]

        # Founder replies (CEO only)
        founder_replies = []
        if is_ceo:
            async with db.execute(
                """SELECT fm.subject,fm.reply_body FROM founder_mail fm
                   WHERE fm.from_dept_id=? AND fm.status='replied'
                     AND fm.replied_at > COALESCE(
                         (SELECT MAX(ran_at) FROM agent_heartbeat_log WHERE agent_id=?),
                         '2000-01-01')""",
                (dept, aid)
            ) as cur:
                founder_replies = [dict(r) for r in await cur.fetchall()]

    ctx = [
        f"## Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | Week: {week_start}",
        f"## Department: {dept}",
    ]

    # REVISED DRAFTS — highest priority context
    revised_drafts = [d for d in my_drafts if d["status"] == "revised"]
    if revised_drafts:
        ctx.append(f"\n## ⚠ REVISED DRAFTS NEEDING YOUR ATTENTION ({len(revised_drafts)})")
        ctx.append("These drafts have revision notes. Address them FIRST in your cycle.")
        for d in revised_drafts:
            ctx.append(f"- [id:{d['id']}] {d['title']} — Notes: {d.get('review_notes','')[:200]}")

    if my_drafts:
        ctx.append(f"\n## Your Drafts (assigned to you or created by you, {len(my_drafts)})")
        for d in my_drafts:
            ctx.append(f"- [id:{d['id']}] [{d['status'].upper()}] {d['title']}")

    if all_drafts:
        ctx.append(f"\n## All Dept Drafts (dedup check — {len(all_drafts)} total)")
        for d in all_drafts:
            rev_info = f" — reviewed by {d['reviewed_by']}" if d.get("reviewed_by") else ""
            ctx.append(f"- [id:{d['id']}] [{d['status'].upper()}] {d['title']} ({d['draft_type']}){rev_info}")

    if unread_mail:
        ctx.append(f"\n## Unread Mail ({len(unread_mail)})")
        for m in unread_mail[:4]:
            ctx.append(f"- [id:{m['id']}] From {m['from_dept']} [{m['priority']}]: **{m['subject']}** — {m['body'][:200]}")

    if projects:
        ctx.append(f"\n## Active Projects")
        for p in projects:
            ctx.append(f"- [{p['priority']}] {p['name']}: {p['description'][:80]}")

    if endeavors:
        ctx.append(f"\n## Active Endeavors")
        for e in endeavors:
            ctx.append(f"- {e['name']} (phase: {e.get('phase') or 'none'})")

    if founder_replies:
        ctx.append(f"\n## Founder Replies")
        for r in founder_replies:
            ctx.append(f"- Re: {r['subject']}: {r['reply_body'][:150]}")

    if subordinates:
        ctx.append(f"\n## Your Team ({len(subordinates)} direct reports)")
        for s in subordinates:
            last = s.get("last_heartbeat","never")[:16] if s.get("last_heartbeat") else "never"
            ctx.append(f"- {s['name']} ({s['title'] or s['role']}) — last beat: {last}")

    if is_ceo and not weekly_exists:
        ctx.append(f"\n## ⚠ WEEKLY REPORT DUE — Week {week_start} not yet submitted.")

    user_prompt = "\n".join(ctx) + "\n\nAnalyze and decide actions. Minimize output."

    try:
        result = await route(
            task_type="agent_heartbeat",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            dept_id=dept,
        )
        text = result.get("text","")

        json_match = re.search(r'\{[\s\S]*\}', text)
        try:    parsed = json.loads(json_match.group()) if json_match else {}
        except: parsed = {}

        actions_taken = []
        for action in parsed.get("actions", []):
            try:
                taken = await _execute_action(agent, action)
                if taken: actions_taken.append(taken)
            except Exception as e:
                logger.warning(f"Action error {agent['name']}: {e}")

        async with aiosqlite.connect(DB_PATH) as db:
            hid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary,actions_json) VALUES (?,?,?,?,?,?)",
                (hid, agent_id, datetime.utcnow().isoformat(), "ok",
                 parsed.get("summary","Heartbeat complete")[:500],
                 json.dumps(actions_taken[:20]))
            )
            await db.execute("UPDATE agents SET last_heartbeat=? WHERE id=?",
                             (datetime.utcnow().isoformat(), agent_id))
            await db.commit()

        return {"ok": True, "agent": agent["name"], "summary": parsed.get("summary",""),
                "actions_taken": actions_taken}

    except Exception as e:
        logger.error(f"Heartbeat error {agent.get('name','?')}: {e}")
        async with aiosqlite.connect(DB_PATH) as db:
            hid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary) VALUES (?,?,?,?,?)",
                (hid, agent_id, datetime.utcnow().isoformat(), "error", str(e)[:400])
            )
            await db.commit()
        return {"ok": False, "error": str(e)}


async def _execute_action(agent: dict, action: dict) -> Optional[str]:
    """Execute a heartbeat action. Proxies to execute_chat_tool for shared tools."""
    atype  = action.get("type")
    dept   = agent["dept_id"]
    aid    = agent["id"]
    is_ceo = bool(agent.get("is_ceo"))

    # Many actions are identical to chat tools — proxy them
    tool_map = {
        "send_mail":              ("send_mail", {"to_dept": action.get("to_dept","STR"), "subject": action.get("subject",""), "body": action.get("body",""), "priority": action.get("priority","normal")}),
        "send_to_founder":        ("send_to_founder", {"subject": action.get("subject",""), "body": action.get("body",""), "priority": action.get("priority","high"), "requires_decision": action.get("requires_decision",False)}),
        "archive_mail":           ("delete_mail", {"mail_id": action.get("mail_id","")}),
        "create_draft_endeavor":  ("create_endeavor_proposal", {"name": action.get("name",""), "description": action.get("description",""), "phases": action.get("phases",[])}),
        "update_project":         ("update_project", {"project_name": action.get("project_name",""), "status": action.get("status"), "priority": action.get("priority")}),
        "invoke_subordinates":    None,  # handled below
        "weekly_report":          None,
        "hire_agent":             ("hire_agent", {k: action.get(k,"") for k in ["name","role","title","personality","tone","reason"]}),
    }

    if atype in tool_map and tool_map[atype] is not None:
        t, p = tool_map[atype]
        return await execute_chat_tool(t, p, agent)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if atype == "create_draft":
            title    = action.get("title","Draft")
            keywords = [w for w in title.lower().split() if len(w) > 3][:5]
            existing = await _check_existing_draft_raw(db, dept, keywords)
            if existing:
                new_content = (existing.get("content","") or "") + "\n\n---\n\n" + action.get("content","")
                await db.execute("UPDATE drafts SET content=?, status='pending' WHERE id=?",
                                 (new_content, existing["id"]))
                await db.commit()
                return f"Appended to existing '{existing['title']}'"
            did = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status,created_by_agent) VALUES (?,?,?,?,?,?,?,?)",
                (did, dept, title, action.get("content",""),
                 action.get("draft_type","memo"), action.get("priority","normal"), "pending", aid)
            )
            await db.commit()
            return f"Created draft: {title[:60]}"

        elif atype == "update_existing_draft":
            draft_id = action.get("draft_id")
            if not draft_id: return None
            async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                row = await cur.fetchone()
            if not row: return None
            final = (row["content"] or "") + "\n\n---\n\n" + action.get("content","") if action.get("append") else action.get("content", row["content"])
            new_title = action.get("title")
            if new_title:
                await db.execute("UPDATE drafts SET content=?,title=?,status='pending' WHERE id=?", (final, new_title, draft_id))
            else:
                await db.execute("UPDATE drafts SET content=? WHERE id=?", (final, draft_id))
            await db.commit()
            return f"Updated draft {draft_id[:12]}"

        elif atype == "revert_approved_draft":
            draft_id = action.get("draft_id")
            if not draft_id: return None
            await db.execute("UPDATE drafts SET status='pending' WHERE id=?", (draft_id,))
            await db.commit()
            return f"Reverted draft {draft_id[:12]} to pending"

        elif atype == "approve_draft" and is_ceo:
            draft_id = action.get("draft_id")
            if not draft_id: return None
            async with db.execute("SELECT status FROM drafts WHERE id=?", (draft_id,)) as cur:
                row = await cur.fetchone()
            if row and row["status"] == "revised":
                return f"Cannot approve revised draft {draft_id[:12]} — must be re-reviewed first"
            ts = datetime.utcnow().isoformat()
            await db.execute(
                "UPDATE drafts SET status='approved',reviewed_by=?,reviewed_at=? WHERE id=? AND dept_id=?",
                (agent.get("name","CEO"), ts, draft_id, dept)
            )
            did = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO ceo_decisions (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes) VALUES (?,?,?,?,?,?,?)",
                (did, aid, dept, "approve_draft", draft_id, "approved", action.get("notes",""))
            )
            await db.commit()
            return f"CEO approved draft {draft_id[:12]}"

        elif atype == "reject_draft" and is_ceo:
            draft_id = action.get("draft_id")
            if not draft_id: return None
            ts = datetime.utcnow().isoformat()
            await db.execute(
                "UPDATE drafts SET status='rejected',review_notes=?,reviewed_by=?,reviewed_at=? WHERE id=? AND dept_id=?",
                (action.get("notes",""), agent.get("name","CEO"), ts, draft_id, dept)
            )
            await db.commit()
            return f"CEO rejected draft {draft_id[:12]}"

        elif atype == "request_revision":
            draft_id = action.get("draft_id")
            notes    = action.get("notes","")
            if not draft_id: return None
            ts = datetime.utcnow().isoformat()
            async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                row = await cur.fetchone()
            note_block = f"\n\n---\n**📝 REVISION REQUEST [{ts[:16]}] by {agent.get('name','')}:**\n{notes}"
            await db.execute(
                "UPDATE drafts SET status='revised',review_notes=?,revised_by=?,revised_at=?,content=? WHERE id=?",
                (notes, agent.get("name",""), ts, (row["content"] if row else "") + note_block, draft_id)
            )
            await db.commit()
            return f"Revision requested on {draft_id[:12]}"

        elif atype == "respond_to_mail":
            mail_id = action.get("mail_id")
            if not mail_id: return None
            await db.execute("UPDATE mail_messages SET status='read' WHERE id=?", (mail_id,))
            async with db.execute("SELECT from_dept,subject FROM mail_messages WHERE id=?", (mail_id,)) as cur:
                orig = await cur.fetchone()
            if orig:
                body = action.get("reply","")
                if action.get("important"):
                    body = _militarize(body, agent)
                mid = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, dept, orig["from_dept"], f"RE: {orig['subject']}",
                     body, "normal", str(uuid.uuid4()), "unread")
                )
            await db.commit()
            return f"Responded to mail {mail_id[:12]}"

        elif atype == "fire_agent" and is_ceo:
            agent_name = action.get("agent_name","")
            if not agent_name: return None
            async with db.execute(
                "SELECT id FROM agents WHERE name LIKE ? AND dept_id=? AND is_ceo=0", (f"%{agent_name}%", dept)
            ) as cur:
                target = await cur.fetchone()
            if target:
                await db.execute("UPDATE agents SET status='fired' WHERE id=?", (target["id"],))
                did = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO ceo_decisions (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes) VALUES (?,?,?,?,?,?,?)",
                    (did, aid, dept, "fire_agent", target["id"], "fired", action.get("reason",""))
                )
                await db.commit()
                return f"CEO fired: {agent_name}"

        elif atype == "invoke_subordinates":
            async with db.execute(
                "SELECT id,name FROM agents WHERE parent_agent_id=? AND status='active'", (aid,)
            ) as cur:
                subs = [dict(r) for r in await cur.fetchall()]
            invoked = []
            for s in subs:
                try:
                    await run_agent_heartbeat(s["id"])
                    invoked.append(s["name"])
                except Exception as e:
                    logger.warning(f"Failed to invoke {s['name']}: {e}")
            return f"Invoked {len(invoked)} subordinates: {', '.join(invoked)}"

        elif atype == "weekly_report":
            content    = action.get("content","")
            week_start = date.today().strftime("%Y-W%W")
            title      = f"Weekly Status Report — {dept} — {week_start}"
            async with db.execute(
                "SELECT id FROM drafts WHERE dept_id=? AND draft_type='weekly_report' AND title LIKE ?",
                (dept, f"%{week_start}%")
            ) as cur:
                existing = await cur.fetchone()
            if existing:
                await db.execute("UPDATE drafts SET content=?,status='pending' WHERE id=?",
                                 (content, existing["id"]))
            else:
                did = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status,created_by_agent) VALUES (?,?,?,?,?,?,?,?)",
                    (did, dept, title, content, "weekly_report", "high", "pending", aid)
                )
            await db.commit()
            return f"Weekly report submitted: {title}"

        elif atype == "log":
            return f"Log: {action.get('message','')[:100]}"

    return None


def _militarize(body: str, agent: dict) -> str:
    name  = agent.get("name","AGENT").upper()
    title = (agent.get("title") or agent.get("role","AGENT")).upper()
    dept  = agent.get("dept_id","").upper()
    lines = [f"FROM: {name}, {title}, {dept}", f"TIME: {datetime.utcnow().strftime('%Y%m%d %H%MZ')}", ""]
    for p in [p.strip() for p in body.strip().split("\n") if p.strip()]:
        lines.append(p.upper() + " STOP")
    lines.append("OUT.")
    return "\n".join(lines)


async def run_department_cycle(dept_id: str) -> dict:
    """Run CEO first, then all direct reports (L2)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id,name FROM agents WHERE dept_id=? AND is_ceo=1 AND status='active'",
            (dept_id.upper(),)
        ) as cur:
            ceo = dict(await cur.fetchone() or {})
        ceo_id = ceo.get("id")
        l2 = []
        if ceo_id:
            async with db.execute(
                "SELECT id,name FROM agents WHERE parent_agent_id=? AND status='active'", (ceo_id,)
            ) as cur:
                l2 = [dict(r) for r in await cur.fetchall()]

    results = []
    if ceo_id:
        r = await run_agent_heartbeat(ceo_id)
        results.append({"agent": ceo.get("name","CEO"), "ok": r.get("ok"), "summary": r.get("summary","")})
    for a in l2:
        r = await run_agent_heartbeat(a["id"])
        results.append({"agent": a["name"], "ok": r.get("ok"), "summary": r.get("summary","")})

    return {"ok": True, "agents_run": len(results), "results": results}
