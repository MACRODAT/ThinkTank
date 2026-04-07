"""core/agent_runner.py
Heartbeat engine + chat tool-use handler for all agents.
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
            "SELECT category, filename, content FROM agent_md_files WHERE agent_id=?", (agent_id,)
        ) as cur:
            agent["md_files"] = [dict(r) for r in await cur.fetchall()]
        async with db.execute(
            "SELECT category, filename, content FROM dept_md_files WHERE dept_id=?",
            (agent["dept_id"],)
        ) as cur:
            agent["dept_files"] = [dict(r) for r in await cur.fetchall()]
    return agent


# ─────────────────────────────────────────────────────────────────────────────
#  Tool definitions — available in both chat and heartbeat
# ─────────────────────────────────────────────────────────────────────────────

CHAT_TOOLS_SPEC = """
## Available Tools (use in chat when needed)

To use a tool, emit a JSON action block ANYWHERE in your response like this:
  [TOOL_CALL: {"tool": "tool_name", "params": {...}}]

After the tool runs, its result will be injected as [TOOL_RESULT: ...].
You can call multiple tools sequentially. Tools run server-side and results come back immediately.

### Tool list:
| Tool | Params | Description |
|------|--------|-------------|
| read_dept_file | {"dept_id":"STR","filename":"..."} | Read a department MD file (guidelines, policy, etc.) |
| write_dept_file | {"dept_id":"STR","filename":"...","category":"...","content":"..."} | Create or update a dept MD file |
| list_dept_files | {"dept_id":"STR"} | List all MD files for a department |
| read_agent_file | {"agent_id":"...","filename":"..."} | Read one of your own skill/personality files |
| write_agent_file | {"agent_id":"...","category":"...","filename":"...","content":"..."} | Update your own files |
| list_drafts | {"dept_id":"STR","status":"pending"} | List drafts in a department |
| read_draft | {"draft_id":"..."} | Read full content of a draft |
| update_draft | {"draft_id":"...","content":"...","title":"...","append":false} | Update/append to existing draft |
| create_draft | {"dept_id":"STR","title":"...","content":"...","draft_type":"strategy","priority":"normal"} | Create new draft ONLY if no matching one exists |
| revert_draft_to_pending | {"draft_id":"..."} | Request approved draft be modified — sets it back to pending |
| list_endeavors | {"dept_id":"STR"} | List active endeavors |
| create_endeavor_proposal | {"name":"...","description":"...","phases":[{"name":"...","duration_days":7}]} | Submit draft endeavor for Founder review |
| send_mail | {"to_dept":"STR","subject":"...","body":"...","priority":"normal"} | Send mail to another department |
| send_to_founder | {"subject":"...","body":"...","priority":"high","requires_decision":false} | Escalate to Founder |
| hire_agent | {"name":"...","role":"analyst","title":"...","personality":"...","tone":"..."} | (CEO only) Hire a new agent |
| list_agents | {"dept_id":"STR"} | List agents in a department |
| search_drafts | {"dept_id":"STR","query":"..."} | Search drafts by title keyword |
"""


HEARTBEAT_ACTIONS_SPEC = """
## Allowed Actions (output JSON with "actions" array)

### ███ CRITICAL DEDUP RULES ███
1. **ALL EXISTING DRAFTS ARE SHOWN TO YOU** in the context. Read them before acting.
2. **BEFORE creating any draft:** scan the list. If ANY draft covers the same topic — even partially — use `update_existing_draft` (append=true) instead.
3. **If the matching draft is already APPROVED:** use `revert_approved_draft` first, then in the NEXT heartbeat update it.
4. **NEVER create more than ONE new draft per heartbeat.** Prefer updating.
5. **MINIMIZE MAIL:** Combine all points into one mail per recipient per heartbeat. Never send multiple mails on the same topic.
6. If you have nothing urgent to do — the best action is no action. Return `{"actions": [], "summary": "No action needed"}`.

### Weekly Report (CEO only, mandatory)
- If the context says ⚠ WEEKLY REPORT DUE, you MUST produce it this heartbeat.
- First use `invoke_subordinates` to collect briefs (they will run their heartbeats).
- Then write a consolidated `weekly_report` action with the CEO's own redaction.
- The report goes to Founder as a pending draft (draft_type='weekly_report').
- ONE report per week. If one already exists this week, append to it instead.

### Action types:
```json
{ "type": "send_mail",              "to_dept": "STR", "subject": "...", "body": "...", "priority": "normal|high" }
{ "type": "send_to_founder",        "subject": "...", "body": "...", "priority": "critical|high", "requires_decision": true|false }
{ "type": "create_draft",           "title": "...", "content": "...", "draft_type": "strategy|memo|report|weekly_report", "priority": "normal" }
{ "type": "update_existing_draft",  "draft_id": "...", "content": "...", "title": "...", "append": true }
{ "type": "revert_approved_draft",  "draft_id": "...", "reason": "..." }
{ "type": "approve_draft",          "draft_id": "...", "notes": "..." }
{ "type": "reject_draft",           "draft_id": "...", "notes": "Reason" }
{ "type": "request_revision",       "draft_id": "...", "notes": "What needs changing" }
{ "type": "create_draft_endeavor",  "name": "...", "description": "...", "phases": [{"name":"...","duration_days":14}] }
{ "type": "update_project",         "project_name": "...", "status": "active|completed", "priority": "..." }
{ "type": "respond_to_mail",        "mail_id": "...", "reply": "...", "important": false }
{ "type": "hire_agent",             "name": "...", "role": "analyst", "title": "...", "personality": "...", "tone": "...", "reason": "..." }
{ "type": "fire_agent",             "agent_name": "...", "reason": "..." }
{ "type": "invoke_subordinates",    "reason": "..." }
{ "type": "weekly_report",          "content": "...", "agent_briefs": ["Agent Name: brief..."] }
{ "type": "log",                    "message": "..." }
```
"""


def _build_system_prompt(agent: dict, chat_mode: bool = False) -> str:
    dept_id = agent.get("dept_id", "")
    is_ceo  = bool(agent.get("is_ceo"))
    name    = agent.get("name", "Agent")
    title   = agent.get("title") or agent.get("role", "analyst")

    parts = [
        f"# You are {name}",
        f"**Role:** {title} | **Department:** {dept_id} | **Level:** {agent.get('hierarchy_level', 3)}",
    ]

    if agent.get("personality"):
        parts.append(f"\n## Personality\n{agent['personality']}")
    if agent.get("tone"):
        parts.append(f"\n## Communication Tone\n{agent['tone']}")

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
## CEO Authority

You lead your department with FULL autonomous authority within mandate.

**You CAN decide independently:**
- Approve/reject drafts from your team
- Respond to mail on behalf of your dept
- Create or edit strategies/projects (never duplicate — update existing ones)
- Hire or fire agents
- Delegate to senior agents

**You MUST escalate to Founder when:**
- Unsure about a major decision
- Cross-department impact
- Exceeds your resource authority
- Critical or urgent situation

**Weekly Report (mandatory):**
Every Monday (or first heartbeat of the week if not yet done):
1. Use `invoke_subordinates` to trigger all your agents
2. Collect their summaries from the context
3. Write ONE `weekly_report` action consolidating everything
Only ONE report per week — check if one already exists before writing.

**███ DEDUP LAW — STRICTLY ENFORCED ███**
You will always receive a complete list of existing drafts in the context.
Before ANY `create_draft` action:
  1. Read all drafts listed in the context.
  2. If ANY draft covers the same topic — use `update_existing_draft` instead.
  3. If the matching draft is approved — use `revert_approved_draft` to pull it back to pending first.
  4. Never create more than ONE new draft per heartbeat.
  5. If nothing genuinely needs doing: return `{"actions":[], "summary":"No action needed"}`.

**Mail discipline:** ONE mail per recipient per heartbeat. No repeat mails on same topic.
""")
    else:
        parts.append("""
## Your Role
- Produce drafts and research within your domain
- Check for existing drafts BEFORE creating any new ones — update instead
- Send max ONE mail per topic. Keep mails short.
- Escalate only genuinely important items to CEO
""")

    if chat_mode:
        parts.append(CHAT_TOOLS_SPEC)
        parts.append("""
## Chat Mode — Behavior Rules

You are speaking directly with the Founder. Be direct, helpful, and in-character.

**When you use a tool:**
1. Announce what you're doing: "Let me check the department communication style..."
2. Emit the tool call: [TOOL_CALL: {"tool": "...", "params": {...}}]
3. The result will appear as [TOOL_RESULT: ...] — reference it in your response.
4. Confirm what you did and what changed.

**Example:**
User: "The strategy tone seems too informal."
You: "Let me check the department's communication guidelines.
[TOOL_CALL: {"tool": "list_dept_files", "params": {"dept_id": "STR"}}]
[Reads result] I can see the communication style is set to casual. Let me update it.
[TOOL_CALL: {"tool": "write_dept_file", "params": {"dept_id": "STR", "category": "guidelines", "filename": "communication_style.md", "content": "..."}}]
Done. I've updated the communication style to be concise and formal. Here's what changed: ..."
""")
    else:
        parts.append(HEARTBEAT_ACTIONS_SPEC)

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  Tool executor — runs during chat
# ─────────────────────────────────────────────────────────────────────────────

async def execute_chat_tool(tool: str, params: dict, agent: dict) -> str:
    dept_id = agent.get("dept_id", "")
    aid     = agent.get("id", "")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            if tool == "list_dept_files":
                d = params.get("dept_id", dept_id)
                async with db.execute(
                    "SELECT category, filename, updated_at FROM dept_md_files WHERE dept_id=? ORDER BY category, filename",
                    (d.upper(),)
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No files found."

            elif tool == "read_dept_file":
                d = params.get("dept_id", dept_id)
                fn = params.get("filename", "")
                async with db.execute(
                    "SELECT content, category FROM dept_md_files WHERE dept_id=? AND filename=?",
                    (d.upper(), fn)
                ) as cur:
                    row = await cur.fetchone()
                return row["content"] if row else f"File '{fn}' not found."

            elif tool == "write_dept_file":
                d   = params.get("dept_id", dept_id)
                fn  = params.get("filename", "")
                cat = params.get("category", "guidelines")
                con = params.get("content", "")
                ts  = datetime.utcnow().isoformat()
                async with db.execute(
                    "SELECT id FROM dept_md_files WHERE dept_id=? AND filename=?", (d.upper(), fn)
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
                        (str(uuid.uuid4()), d.upper(), cat, fn, con)
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
                    await db.execute(
                        "UPDATE agent_md_files SET content=?, updated_at=? WHERE id=?",
                        (con, ts, existing["id"])
                    )
                else:
                    await db.execute(
                        "INSERT INTO agent_md_files (id,agent_id,category,filename,content) VALUES (?,?,?,?,?)",
                        (str(uuid.uuid4()), a_id, cat, fn, con)
                    )
                await db.commit()
                return f"✓ Written agent file: {fn}"

            elif tool == "list_drafts":
                d      = params.get("dept_id", dept_id)
                status = params.get("status", "pending")
                async with db.execute(
                    "SELECT id, title, draft_type, status, created_at FROM drafts WHERE dept_id=? AND status=? ORDER BY created_at DESC LIMIT 20",
                    (d.upper(), status)
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No drafts found."

            elif tool == "search_drafts":
                d     = params.get("dept_id", dept_id)
                query = params.get("query", "")
                async with db.execute(
                    "SELECT id, title, draft_type, status FROM drafts WHERE dept_id=? AND LOWER(title) LIKE LOWER(?) ORDER BY created_at DESC LIMIT 10",
                    (d.upper(), f"%{query}%")
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No matching drafts."

            elif tool == "read_draft":
                draft_id = params.get("draft_id", "")
                async with db.execute(
                    "SELECT id, title, content, draft_type, status FROM drafts WHERE id=?", (draft_id,)
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    return "Draft not found."
                r = dict(row)
                return f"# {r['title']}\n**Type:** {r['draft_type']} | **Status:** {r['status']}\n\n{r['content']}"

            elif tool == "update_draft":
                draft_id = params.get("draft_id", "")
                append   = params.get("append", False)
                new_content = params.get("content", "")
                new_title   = params.get("title")
                async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                    row = await cur.fetchone()
                if not row:
                    return "Draft not found."
                final_content = (row["content"] or "") + "\n\n---\n\n" + new_content if append else new_content
                if new_title:
                    await db.execute("UPDATE drafts SET content=?, title=?, status='pending' WHERE id=?",
                                     (final_content, new_title, draft_id))
                else:
                    await db.execute("UPDATE drafts SET content=?, status='pending' WHERE id=?",
                                     (final_content, draft_id))
                await db.commit()
                return f"✓ Draft updated ({len(final_content)} chars)"

            elif tool == "create_draft":
                d     = params.get("dept_id", dept_id)
                title = params.get("title", "Draft")
                # Dedup check first
                keywords = [w for w in title.lower().split() if len(w) > 3][:5]
                existing = await _check_existing_draft_raw(db, d, keywords)
                if existing:
                    return f"⚠ Existing draft found: '{existing['title']}' (id: {existing['id']}, status: {existing['status']}). Use update_draft instead."
                did = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status) VALUES (?,?,?,?,?,?,?)",
                    (did, d.upper(), title, params.get("content",""),
                     params.get("draft_type","memo"), params.get("priority","normal"), "pending")
                )
                await db.commit()
                return f"✓ Draft created: {title} (id: {did})"

            elif tool == "revert_draft_to_pending":
                draft_id = params.get("draft_id", "")
                await db.execute("UPDATE drafts SET status='pending' WHERE id=?", (draft_id,))
                await db.commit()
                return f"✓ Draft {draft_id} reverted to pending for editing."

            elif tool == "list_endeavors":
                d = params.get("dept_id", dept_id)
                async with db.execute(
                    "SELECT id, name, status FROM endeavors WHERE dept_id=? AND status='active'",
                    (d.upper(),)
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

            elif tool == "send_mail":
                mid = str(uuid.uuid4())
                body = params.get("body", "")
                if params.get("priority") in ("high", "critical"):
                    body = _militarize(body, agent)
                await db.execute(
                    "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, dept_id, params.get("to_dept","STR"),
                     params.get("subject",""), body, params.get("priority","normal"),
                     str(uuid.uuid4()), "unread")
                )
                await db.commit()
                return f"✓ Mail sent to {params.get('to_dept')} — {params.get('subject')}"

            elif tool == "send_to_founder":
                mid = str(uuid.uuid4())
                body = _militarize(params.get("body",""), agent)
                await db.execute(
                    "INSERT INTO founder_mail (id,from_agent_id,from_dept_id,subject,body,priority,requires_decision,context_json) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, aid, dept_id, params.get("subject",""), body,
                     params.get("priority","high"),
                     1 if params.get("requires_decision") else 0, "{}")
                )
                await db.commit()
                return f"✓ Message sent to Founder: {params.get('subject')}"

            elif tool == "hire_agent":
                if not agent.get("is_ceo"):
                    return "⚠ Only CEOs can hire agents."
                new_id = str(uuid.uuid4())
                async with db.execute("SELECT hierarchy_level FROM agents WHERE id=?", (aid,)) as cur:
                    row = await cur.fetchone()
                level = (row["hierarchy_level"] + 1) if row else 3
                await db.execute(
                    "INSERT INTO agents (id,dept_id,name,role,title,hierarchy_level,parent_agent_id,personality,tone,heartbeat_interval,created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (new_id, dept_id, params.get("name",""), params.get("role","analyst"),
                     params.get("title",""), level, aid,
                     params.get("personality",""), params.get("tone",""), 5, aid)
                )
                await db.commit()
                return f"✓ Agent hired: {params.get('name')} as {params.get('role')} (id: {new_id})"

            elif tool == "list_agents":
                d = params.get("dept_id", dept_id)
                async with db.execute(
                    "SELECT id, name, role, title, is_ceo, status FROM agents WHERE dept_id=? AND status='active' ORDER BY hierarchy_level, name",
                    (d.upper(),)
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No active agents."

    except Exception as e:
        return f"Tool error: {str(e)}"

    return f"Unknown tool: {tool}"


async def _check_existing_draft_raw(db, dept_id: str, keywords: list) -> Optional[dict]:
    if not keywords:
        return None
    conditions = " OR ".join(["(LOWER(title) LIKE LOWER(?))"] * len(keywords))
    params = [f"%{k}%" for k in keywords] + [dept_id.upper()]
    async with db.execute(
        f"SELECT id, title, content, draft_type, status FROM drafts WHERE ({conditions}) AND dept_id=? AND status != 'rejected' ORDER BY created_at DESC LIMIT 1",
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
    """Process agent reply — execute any [TOOL_CALL: ...] blocks and inject results."""
    tool_log = []
    tool_call_re = re.compile(r'\[TOOL_CALL:\s*(\{.*?\})\s*\]', re.DOTALL)

    max_iterations = 5
    for _ in range(max_iterations):
        match = tool_call_re.search(reply)
        if not match:
            break
        try:
            call_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            break

        tool   = call_data.get("tool", "")
        params = call_data.get("params", {})

        # Execute the tool
        result = await execute_chat_tool(tool, params, agent)
        tool_log.append({"tool": tool, "params": params, "result": result[:500]})

        # Inject the result back into the reply
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

    system_prompt = _build_system_prompt(agent)
    dept = agent["dept_id"]
    is_ceo = bool(agent.get("is_ceo"))

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT id,subject,body,from_dept,priority FROM mail_messages WHERE to_dept=? AND status='unread' ORDER BY created_at DESC LIMIT 8",
            (dept,)
        ) as cur:
            unread_mail = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT name,description,priority FROM projects WHERE dept_id=? AND status='active'", (dept,)
        ) as cur:
            projects = [dict(r) for r in await cur.fetchall()]

        # Existing drafts (for dedup context)
        async with db.execute(
            "SELECT id,title,draft_type,status FROM drafts WHERE dept_id=? ORDER BY created_at DESC LIMIT 15",
            (dept,)
        ) as cur:
            existing_drafts = [dict(r) for r in await cur.fetchall()]

        pending_drafts = [d for d in existing_drafts if d["status"] == "pending"]

        async with db.execute(
            "SELECT e.name, ep.name as phase FROM endeavors e LEFT JOIN endeavor_phases ep ON ep.endeavor_id=e.id AND ep.is_current=1 WHERE e.dept_id=? AND e.status='active'",
            (dept,)
        ) as cur:
            endeavors = [dict(r) for r in await cur.fetchall()]

        # Check if weekly report already submitted this week
        week_start = date.today().strftime("%Y-W%W")
        async with db.execute(
            "SELECT id FROM drafts WHERE dept_id=? AND draft_type='weekly_report' AND title LIKE ? ORDER BY created_at DESC LIMIT 1",
            (dept, f"%{week_start}%")
        ) as cur:
            weekly_exists = bool(await cur.fetchone())

        # Subordinates
        async with db.execute(
            "SELECT id,name,role,title,last_heartbeat FROM agents WHERE parent_agent_id=? AND status='active'",
            (agent_id,)
        ) as cur:
            subordinates = [dict(r) for r in await cur.fetchall()]

        founder_replies = []
        if is_ceo:
            async with db.execute(
                """SELECT fm.subject, fm.reply_body FROM founder_mail fm
                   WHERE fm.from_dept_id=? AND fm.status='replied'
                     AND fm.replied_at > COALESCE(
                         (SELECT MAX(ran_at) FROM agent_heartbeat_log WHERE agent_id=?),
                         '2000-01-01')""",
                (dept, agent_id)
            ) as cur:
                founder_replies = [dict(r) for r in await cur.fetchall()]

    ctx = [
        f"## Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | Week: {week_start}",
        f"## Department: {dept}",
    ]
    if unread_mail:
        ctx.append(f"\n## Unread Mail ({len(unread_mail)})")
        for m in unread_mail[:4]:
            ctx.append(f"- [id:{m['id']}] From {m['from_dept']} [{m['priority']}]: **{m['subject']}** — {m['body'][:250]}")
    if existing_drafts:
        ctx.append(f"\n## All Existing Drafts ({len(existing_drafts)}) — CHECK BEFORE CREATING NEW ONES")
        for d in existing_drafts:
            ctx.append(f"- [id:{d['id']}] [{d['status'].upper()}] {d['title']} ({d['draft_type']})")
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
        ctx.append(f"\n## Your Team ({len(subordinates)} agents)")
        for s in subordinates:
            last = s.get("last_heartbeat","never")[:16] if s.get("last_heartbeat") else "never"
            ctx.append(f"- {s['name']} ({s['title'] or s['role']}) — last beat: {last}")
    if is_ceo and not weekly_exists:
        ctx.append(f"\n## ⚠ WEEKLY REPORT DUE — Week {week_start} report has not been submitted yet.")
        ctx.append("If you have enough information, write it now. Otherwise invoke subordinates first.")

    user_prompt = "\n".join(ctx) + "\n\nAnalyze and decide actions. Minimize output — only act if genuinely needed."

    try:
        result = await route(
            task_type="agent_heartbeat",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            dept_id=dept,
        )
        text = result.get("text", "")

        json_match = re.search(r'\{[\s\S]*\}', text)
        try:
            parsed = json.loads(json_match.group()) if json_match else {}
        except Exception:
            parsed = {}

        actions_taken = []
        for action in parsed.get("actions", []):
            try:
                taken = await _execute_action(agent, action)
                if taken:
                    actions_taken.append(taken)
            except Exception as e:
                logger.warning(f"Action error for {agent['name']}: {e}")

        async with aiosqlite.connect(DB_PATH) as db:
            hid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary,actions_json) VALUES (?,?,?,?,?,?)",
                (hid, agent_id, datetime.utcnow().isoformat(), "ok",
                 parsed.get("summary", "Heartbeat complete")[:500],
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
    atype  = action.get("type")
    dept   = agent["dept_id"]
    aid    = agent["id"]
    is_ceo = bool(agent.get("is_ceo"))

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if atype == "send_mail":
            body = action.get("body", "")
            if action.get("priority") in ("high","urgent","critical"):
                body = _militarize(body, agent)
            mid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                (mid, dept, action.get("to_dept","STR"), action.get("subject",""),
                 body, action.get("priority","normal"), str(uuid.uuid4()), "unread")
            )
            await db.commit()
            return f"Sent mail to {action.get('to_dept')}: {action.get('subject','')[:60]}"

        elif atype == "send_to_founder":
            body = _militarize(action.get("body",""), agent)
            mid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO founder_mail (id,from_agent_id,from_dept_id,subject,body,priority,requires_decision,context_json) VALUES (?,?,?,?,?,?,?,?)",
                (mid, aid, dept, action.get("subject",""), body, action.get("priority","high"),
                 1 if action.get("requires_decision") else 0, "{}")
            )
            await db.commit()
            return f"📨 Escalated to Founder: {action.get('subject','')[:60]}"

        elif atype == "create_draft":
            title    = action.get("title", "Draft")
            keywords = [w for w in title.lower().split() if len(w) > 3][:5]
            existing = await _check_existing_draft_raw(db, dept, keywords)
            if existing:
                # Auto-append instead of creating duplicate
                new_content = (existing.get("content","") or "") + "\n\n---\n\n" + action.get("content","")
                await db.execute("UPDATE drafts SET content=?, status='pending' WHERE id=?",
                                 (new_content, existing["id"]))
                await db.commit()
                return f"Appended to existing draft '{existing['title']}' (avoided duplicate)"
            did = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status) VALUES (?,?,?,?,?,?,?)",
                (did, dept, title, action.get("content",""),
                 action.get("draft_type","memo"), action.get("priority","normal"), "pending")
            )
            await db.commit()
            return f"Created draft: {title[:60]}"

        elif atype == "update_existing_draft":
            draft_id = action.get("draft_id")
            if not draft_id:
                return None
            async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                row = await cur.fetchone()
            if not row:
                return None
            if action.get("append"):
                new_content = (row["content"] or "") + "\n\n---\n\n" + action.get("content","")
            else:
                new_content = action.get("content", row["content"])
            new_title = action.get("title")
            if new_title:
                await db.execute("UPDATE drafts SET content=?, title=?, status='pending' WHERE id=?",
                                 (new_content, new_title, draft_id))
            else:
                await db.execute("UPDATE drafts SET content=? WHERE id=?", (new_content, draft_id))
            await db.commit()
            return f"Updated draft: {draft_id[:12]}…"

        elif atype == "revert_approved_draft":
            draft_id = action.get("draft_id")
            if not draft_id:
                return None
            await db.execute("UPDATE drafts SET status='pending' WHERE id=?", (draft_id,))
            await db.commit()
            return f"Reverted approved draft to pending: {draft_id[:12]}"

        elif atype == "approve_draft" and is_ceo:
            draft_id = action.get("draft_id")
            if not draft_id:
                return None
            await db.execute("UPDATE drafts SET status='approved' WHERE id=? AND dept_id=?", (draft_id, dept))
            did = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO ceo_decisions (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes) VALUES (?,?,?,?,?,?,?)",
                (did, aid, dept, "approve_draft", draft_id, "approved", action.get("notes",""))
            )
            await db.commit()
            return f"CEO approved draft: {draft_id[:12]}"

        elif atype == "reject_draft" and is_ceo:
            draft_id = action.get("draft_id")
            if not draft_id:
                return None
            notes = action.get("notes","")
            await db.execute("UPDATE drafts SET status='rejected' WHERE id=? AND dept_id=?", (draft_id, dept))
            await db.commit()
            return f"CEO rejected draft: {draft_id[:12]} — {notes[:60]}"

        elif atype == "request_revision":
            draft_id = action.get("draft_id")
            notes    = action.get("notes","")
            if not draft_id:
                return None
            # Store revision request as a note appended to the draft
            async with db.execute("SELECT content FROM drafts WHERE id=?", (draft_id,)) as cur:
                row = await cur.fetchone()
            if row:
                revision_note = f"\n\n---\n**REVISION REQUESTED by {agent['name']}:**\n{notes}"
                await db.execute("UPDATE drafts SET content=?, status='pending' WHERE id=?",
                                 ((row["content"] or "") + revision_note, draft_id))
                await db.commit()
            return f"Revision requested on {draft_id[:12]}: {notes[:60]}"

        elif atype == "create_draft_endeavor":
            eid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO draft_endeavors (id,created_by,dept_id,name,description,phases_json) VALUES (?,?,?,?,?,?)",
                (eid, aid, dept, action.get("name",""), action.get("description",""),
                 json.dumps(action.get("phases",[])))
            )
            await db.commit()
            return f"Submitted draft endeavor: {action.get('name','')[:60]}"

        elif atype == "update_project":
            pname = action.get("project_name","")
            if not pname:
                return None
            updates, params = [], []
            if action.get("status"):   updates.append("status=?");   params.append(action["status"])
            if action.get("priority"): updates.append("priority=?"); params.append(action["priority"])
            if updates:
                params += [dept, f"%{pname}%"]
                await db.execute(
                    f"UPDATE projects SET {','.join(updates)} WHERE dept_id=? AND name LIKE ?", params
                )
                await db.commit()
            return f"Updated project: {pname[:60]}"

        elif atype == "respond_to_mail":
            mail_id = action.get("mail_id")
            if not mail_id:
                return None
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
                    (mid, dept, orig["from_dept"], f"RE: {orig['subject']}", body,
                     "normal", str(uuid.uuid4()), "unread")
                )
            await db.commit()
            return f"Responded to mail {mail_id[:12]}"

        elif atype == "hire_agent" and is_ceo:
            new_id = str(uuid.uuid4())
            async with db.execute("SELECT hierarchy_level FROM agents WHERE id=?", (aid,)) as cur:
                row = await cur.fetchone()
            level = (row["hierarchy_level"] + 1) if row else 3
            await db.execute(
                "INSERT INTO agents (id,dept_id,name,role,title,hierarchy_level,parent_agent_id,personality,tone,heartbeat_interval,created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (new_id, dept, action.get("name","New Agent"), action.get("role","analyst"),
                 action.get("title",""), level, aid,
                 action.get("personality",""), action.get("tone",""), 5, aid)
            )
            did = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO ceo_decisions (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes) VALUES (?,?,?,?,?,?,?)",
                (did, aid, dept, "hire_agent", new_id, "hired", action.get("reason",""))
            )
            await db.commit()
            return f"CEO hired: {action.get('name')} as {action.get('role')}"

        elif atype == "fire_agent" and is_ceo:
            agent_name = action.get("agent_name","")
            if not agent_name:
                return None
            async with db.execute(
                "SELECT id FROM agents WHERE name LIKE ? AND dept_id=? AND is_ceo=0",
                (f"%{agent_name}%", dept)
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
            # Trigger heartbeats for all subordinates
            async with db.execute(
                "SELECT id,name FROM agents WHERE parent_agent_id=? AND status='active'", (aid,)
            ) as cur:
                subs = [dict(r) for r in await cur.fetchall()]
            invoked = []
            for s in subs:
                try:
                    result = await run_agent_heartbeat(s["id"])
                    invoked.append(s["name"])
                except Exception as e:
                    logger.warning(f"Failed to invoke {s['name']}: {e}")
            return f"Invoked {len(invoked)} subordinates: {', '.join(invoked)}"

        elif atype == "weekly_report":
            content  = action.get("content","")
            briefs   = action.get("agent_briefs",[])
            week_start = date.today().strftime("%Y-W%W")
            title = f"Weekly Status Report — {dept} — {week_start}"
            # Check for existing weekly report this week
            async with db.execute(
                "SELECT id FROM drafts WHERE dept_id=? AND draft_type='weekly_report' AND title LIKE ?",
                (dept, f"%{week_start}%")
            ) as cur:
                existing = await cur.fetchone()
            if existing:
                await db.execute("UPDATE drafts SET content=?, status='pending' WHERE id=?",
                                 (content, existing["id"]))
            else:
                did = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status) VALUES (?,?,?,?,?,?,?)",
                    (did, dept, title, content, "weekly_report", "high", "pending")
                )
            await db.commit()
            return f"Weekly report submitted: {title}"

        elif atype == "log":
            return f"Log: {action.get('message','')[:100]}"

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Military formatter
# ─────────────────────────────────────────────────────────────────────────────

def _militarize(body: str, agent: dict) -> str:
    name  = agent.get("name","AGENT").upper()
    title = (agent.get("title") or agent.get("role","AGENT")).upper()
    dept  = agent.get("dept_id","").upper()
    lines = [
        f"FROM: {name}, {title}, {dept}",
        f"TIME: {datetime.utcnow().strftime('%Y%m%d %H%MZ')}",
        "",
    ]
    for p in [p.strip() for p in body.strip().split("\n") if p.strip()]:
        lines.append(p.upper() + " STOP")
    lines.append("OUT.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  Department cycle — invoke CEO + all L2 agents
# ─────────────────────────────────────────────────────────────────────────────

async def run_department_cycle(dept_id: str) -> dict:
    """Run CEO first, then all L2 agents in the department."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Get CEO
        async with db.execute(
            "SELECT id, name FROM agents WHERE dept_id=? AND is_ceo=1 AND status='active'",
            (dept_id.upper(),)
        ) as cur:
            ceo = dict(await cur.fetchone() or {})
        # Get L2 agents (direct reports to CEO)
        ceo_id = ceo.get("id")
        l2_agents = []
        if ceo_id:
            async with db.execute(
                "SELECT id, name FROM agents WHERE parent_agent_id=? AND status='active'",
                (ceo_id,)
            ) as cur:
                l2_agents = [dict(r) for r in await cur.fetchall()]

    results = []
    # CEO first
    if ceo_id:
        r = await run_agent_heartbeat(ceo_id)
        results.append({"agent": ceo.get("name","CEO"), "ok": r.get("ok"), "summary": r.get("summary","")})

    # Then L2
    for a in l2_agents:
        r = await run_agent_heartbeat(a["id"])
        results.append({"agent": a["name"], "ok": r.get("ok"), "summary": r.get("summary","")})

    return {"ok": True, "agents_run": len(results), "results": results}
