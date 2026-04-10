"""core/agent_runner.py — Heartbeat engine + chat tool-use handler."""
from __future__ import annotations
import uuid, json, logging, re
from datetime import datetime, date
from typing import Optional
import aiosqlite
from core.database import DB_PATH
from core.ai_router import route

logger = logging.getLogger(__name__)

_heartbeat_migration_done = False

async def _ensure_heartbeat_columns():
    global _heartbeat_migration_done
    if _heartbeat_migration_done:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        for sql in ["ALTER TABLE agent_heartbeat_log ADD COLUMN actions_json TEXT DEFAULT '[]'"]:
            try: await db.execute(sql)
            except: pass
        await db.commit()
    _heartbeat_migration_done = True


# ── Settings ──────────────────────────────────────────────────────────────────

async def _get_all_settings() -> dict:
    try:
        from api.routes.settings import _load
        return await _load()
    except Exception:
        return {}

async def _get_global_prompts() -> tuple[str, str]:
    s = await _get_all_settings()
    return s.get("custom_prompt_prepend", ""), s.get("custom_prompt_append", "")


# ── Context loader ────────────────────────────────────────────────────────────

async def _get_agent_context(agent_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)) as cur:
            agent = dict(await cur.fetchone() or {})
        if not agent:
            return {}
        async with db.execute(
            "SELECT category, filename, content FROM agent_md_files WHERE agent_id=? ORDER BY category, filename",
            (agent_id,)) as cur:
            agent["md_files"] = [dict(r) for r in await cur.fetchall()]
        async with db.execute(
            "SELECT category, filename, content FROM dept_md_files WHERE dept_id=? ORDER BY category, filename",
            (agent["dept_id"],)) as cur:
            agent["dept_files"] = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT system_prompt FROM departments WHERE id=?", (agent["dept_id"],)) as cur:
            row = await cur.fetchone()
            agent["dept_system_prompt"] = row["system_prompt"] if row else ""
    return agent


async def _get_hierarchy(agent_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)) as cur:
            me = dict(await cur.fetchone() or {})
        superior = None
        if me.get("parent_agent_id"):
            async with db.execute(
                "SELECT id,name,role,title,dept_id,is_ceo FROM agents WHERE id=?",
                (me["parent_agent_id"],)) as cur:
                row = await cur.fetchone()
                superior = dict(row) if row else None
        async with db.execute(
            "SELECT id,name,role,title,dept_id FROM agents WHERE parent_agent_id=? AND status='active'",
            (agent_id,)) as cur:
            reports = [dict(r) for r in await cur.fetchall()]
    return {"superior": superior, "reports": reports}


async def _can_act_on(acting_agent_id: str, target_agent_id: str) -> bool:
    if acting_agent_id == target_agent_id:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        current = target_agent_id
        for _ in range(10):
            async with db.execute("SELECT parent_agent_id, dept_id FROM agents WHERE id=?", (current,)) as cur:
                row = await cur.fetchone()
            if not row or not row["parent_agent_id"]:
                break
            if row["parent_agent_id"] == acting_agent_id:
                return True
            current = row["parent_agent_id"]
        async with db.execute("SELECT is_ceo, dept_id FROM agents WHERE id=?", (acting_agent_id,)) as cur:
            me = await cur.fetchone()
        async with db.execute("SELECT dept_id FROM agents WHERE id=?", (target_agent_id,)) as cur:
            tgt = await cur.fetchone()
        if me and tgt and me["is_ceo"] and me["dept_id"] == tgt["dept_id"]:
            return True
    return False


# ── Prompt specs ──────────────────────────────────────────────────────────────

_TOOLS_TABLE = """
| Tool | Params | Description |
|------|--------|-------------|
| list_dept_files | dept_id | List dept MD files |
| read_dept_file | dept_id, filename | Read a dept MD file |
| write_dept_file | dept_id, filename, category, content | Create/update dept file |
| read_agent_file | agent_id?, filename | Read your own file |
| write_agent_file | agent_id?, category, filename, content | Update your own file |
| list_drafts | dept_id?, status | List drafts (pending/revised/approved/all) |
| search_drafts | dept_id?, query | Search drafts by keyword |
| read_draft | draft_id | Read full draft content |
| create_draft | dept_id?, title, content, draft_type, priority | Create draft (dedup check) |
| update_draft | draft_id, content, title?, append? | Update/append draft |
| change_draft_status | draft_id, status, notes?, reviewed_by? | Set status |
| revert_draft_to_pending | draft_id | Revert approved draft |
| delegate_draft | draft_id, to_agent_id, notes? | Assign to subordinate |
| request_superior_review | draft_id, notes? | Send to superior |
| list_endeavors | dept_id? | List active endeavors |
| search_endeavors | name_query | Search endeavors before proposing |
| create_endeavor_proposal | name, description, phases | Submit endeavor for review |
| list_topics | | List all topics |
| search_topics | query | Search topics |
| create_topic | name, description, color? | Create topic |
| assign_topic | item_type, item_id, topic_id | Assign topic to item |
| get_mail | dept_id? | Show unarchived mail |
| delete_mail | mail_id | Archive mail |
| send_mail | to_dept, subject, body, priority? | Send mail |
| forward_mail | mail_id, to_dept, note? | Forward mail |
| send_to_founder | subject, body, priority?, requires_decision? | Escalate to Founder+CEO |
| write_to_founder | subject, body, priority? | Urgent message to Founder |
| get_superior | | Get direct superior info |
| get_subordinates | | Get direct reports |
| hire_agent | name, role, title, personality, tone, reason | CEO only: hire agent |
| list_agents | dept_id? | List agents |
| update_project | project_name, status?, priority? | Update project |
| web_search | query, max_results? | Search the web (costs 10 pts per call — use sparingly!) |
| get_time | | Get current UTC time (costs 2 pts) |
| check_offline | | Check if system is online (costs 10 pts) |
| get_my_points | | Check your department's current point balance |
| get_points_ledger | | View last 10 point transactions for your department |
| ceo_adjust_heartbeat | agent_id, interval | CEO only: Set heartbeat interval for a subordinate |
| ceo_modify_heartbeat | agent_id, interval | CEO only: Alias for ceo_adjust_heartbeat |
| ceo_modify_agent | agent_id, personality?, tone? | CEO only: Modify agent personality/tone |
| inject_instructions | agent_id, instructions, visible? | CEO only: Set custom instructions for a subordinate agent (visible=true by default) |
| ceo_list_market_agents | | CEO only: View available agents in marketplace |

**HIERARCHY:** Only act on agents reporting to you.
**RIGHT TOOL:** hire_agent to hire. create_draft for documents only. web_search ONLY when essential (costs 10 pts).
**POINTS:** Every action costs points. Be efficient. Check get_my_points before expensive actions.
"""

_HEARTBEAT_ACTIONS_TEMPLATE = """
Actions (JSON "actions" array):
{ "type": "send_mail", "to_dept": "STR", "subject": "...", "body": "...", "priority": "normal" }
{ "type": "send_to_founder", "subject": "...", "body": "...", "priority": "high", "requires_decision": true }
{ "type": "create_draft", "title": "...", "content": "...", "draft_type": "strategy|memo|report|weekly_report", "priority": "normal" }
{ "type": "update_existing_draft", "draft_id": "...", "content": "...", "title": "...", "append": true }
{ "type": "revert_approved_draft", "draft_id": "...", "reason": "..." }
{ "type": "approve_draft", "draft_id": "...", "notes": "Approval remarks — always required" }
{ "type": "reject_draft", "draft_id": "...", "notes": "Reason" }
{ "type": "request_revision", "draft_id": "...", "notes": "What needs changing" }
{ "type": "create_draft_endeavor", "name": "...", "description": "...", "phases": [{"name":"Phase 1","description":"...","duration_days":14}] }
{ "type": "update_project", "project_name": "...", "status": "active|completed", "priority": "..." }
{ "type": "respond_to_mail", "mail_id": "...", "reply": "...", "important": false }
{ "type": "archive_mail", "mail_id": "..." }
{ "type": "hire_agent", "name": "...", "role": "analyst", "title": "...", "personality": "...", "tone": "...", "reason": "..." }
{ "type": "fire_agent", "agent_name": "...", "reason": "..." }
{ "type": "invoke_subordinates", "reason": "..." }
{ "type": "weekly_report", "content": "...", "agent_briefs": [] }
{ "type": "log", "message": "..." }
"""


def _build_system_prompt(agent: dict, chat_mode: bool = False,
                          prepend: str = "", append: str = "",
                          settings: Optional[dict] = None) -> str:
    if settings is None:
        settings = {}
    dept_id = agent.get("dept_id", "")
    is_ceo  = bool(agent.get("is_ceo"))
    name    = agent.get("name", "Agent")
    title   = agent.get("title") or agent.get("role", "analyst")
    parts   = []

    if prepend.strip():
        parts.append(f"# Global System Context\n{prepend.strip()}\n")

    dept_prompt = agent.get("dept_system_prompt", "").strip()
    if dept_prompt:
        parts.append(f"# Department System Prompt\n{dept_prompt}\n")
    elif agent.get("dept_files"):
        parts.append(f"# Department: {dept_id} Guidelines")
        for f in agent["dept_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")

    parts.append(f"# You are {name}")
    parts.append(f"**Role:** {title} | **Dept:** {dept_id} | **Level:** {agent.get('hierarchy_level', 3)}")

    if agent.get("personality"):
        parts.append(f"\n## Personality\n{agent['personality']}")
    if agent.get("tone"):
        parts.append(f"\n## Communication Tone\n{agent['tone']}")
    if agent.get("md_files"):
        parts.append("\n## Your Skills & Knowledge Files")
        for f in agent["md_files"]:
            parts.append(f"\n### [{f['category']}] {f['filename']}\n{f['content']}")

    # CEO custom instructions injected into this agent's prompt
    ceo_instr = agent.get("ceo_instructions", "").strip()
    if ceo_instr:
        visible_flag = agent.get("ceo_instructions_visible", 1)
        parts.append(f"\n## Instructions from Your Department CEO\n{ceo_instr}")
        if visible_flag:
            parts.append("*(These instructions are visible to you and were set by your CEO)*")

    if is_ceo:
        rule = settings.get("prompt_ceo_authority", "").strip()
        if not rule:
            rule = (
                "## CEO Authority\nYou lead your department with full autonomous authority.\n\n"
                "**Decide independently:** approve/reject drafts, respond to mail, create/edit strategies, "
                "hire/fire agents, delegate, update projects, propose endeavors.\n\n"
                "**Escalate to Founder:** major cross-dept decisions, exceeded authority, critical situations.\n\n"
                "**Weekly Report (Monday):** invoke agents, collect briefs, write + submit one report.\n\n"
                "**DEDUP RULE:** NEVER create a draft/project/endeavor if one already exists. Update it.\n\n"
                "**Mail:** ONE message per recipient per topic. Military format for urgent.\n\n"
                "**Hierarchy:** Manage only agents in your department."
            )
        parts.append("\n" + rule)
    else:
        rule = settings.get("prompt_agent_role", "").strip()
        if not rule:
            rule = (
                "## Your Role\n"
                "- CHECK existing drafts before creating — update them, do NOT duplicate.\n"
                "- ONE mail per topic per recipient. Keep mails brief.\n"
                "- Escalate only important items to your CEO.\n"
                "- Use hire_agent to hire — never create_draft for that purpose.\n"
                "- Only interact with agents that report to you or your direct superior."
            )
        parts.append("\n" + rule)

    if chat_mode:
        tools_header = settings.get("prompt_tools_spec_header", "").strip()
        if not tools_header:
            tools_header = (
                "## Available Tools\n\n"
                "Emit: [TOOL_CALL: {\"tool\": \"name\", \"params\": {...}}]\n"
                "Results: [TOOL:name]...[/TOOL]\n\n"
                "Correct tool selection:\n"
                "- HIRE someone -> hire_agent (NOT create_draft)\n"
                "- SEARCH web -> web_search\n"
                "- WRITE document -> create_draft (check for existing first)"
            )
        parts.append(tools_header + "\n" + _TOOLS_TABLE)
        chat_prompt = settings.get("prompt_chat_mode", "").strip()
        if not chat_prompt:
            chat_prompt = (
                "## Chat Mode\nYou are speaking with the Founder directly. Be in-character.\n"
                "Announce tool use, emit [TOOL_CALL: {...}], reference the result naturally."
            )
        parts.append("\n" + chat_prompt)
    else:
        rules = settings.get("prompt_heartbeat_rules", "").strip()
        if not rules:
            rules = (
                "## Heartbeat Rules\n"
                "1. MINIMIZE - only act when genuinely needed.\n"
                "2. DEDUP - check existing drafts/projects/endeavors before creating ANY. Update them.\n"
                "3. MAIL - one mail per recipient per topic.\n"
                "4. HIERARCHY - only act on personnel reporting to you.\n"
                "5. REVISED DRAFTS - address them FIRST before anything else.\n"
                "6. RIGHT TOOL - hire_agent to hire, create_draft for docs, web_search for research.\n"
                "7. NO DUPES - NEVER create projects/endeavors if similar ones exist in context above."
            )
        parts.append(rules + "\n## Allowed Heartbeat Actions\n" + _HEARTBEAT_ACTIONS_TEMPLATE)

    if append.strip():
        parts.append(f"\n# Additional Global Instructions\n{append.strip()}")

    return "\n".join(parts)


# ── Chat tool executor ─────────────────────────────────────────────────────────

async def execute_chat_tool(tool: str, params: dict, agent: dict) -> str:
    dept_id = agent.get("dept_id", "")
    aid     = agent.get("id", "")
    is_ceo  = bool(agent.get("is_ceo"))

    if tool == "web_search":
        try:
            from core.web_search import web_search as _ws
            from core.economy import log_web_search
            settings = await _get_all_settings()
            query    = params.get("query", "")
            result   = await _ws(query, settings)
            success  = "failed" not in result.lower() and "disabled" not in result.lower()
            await log_web_search(aid, agent.get("name",""), dept_id, query,
                                  settings.get("web_search_provider","?"), success)
            return result
        except Exception as e:
            return f"Web search error: {e}"

    if tool == "get_time":
        from core.economy import deduct
        await deduct(dept_id, "tool_get_time", 2, "Tool: get_time", agent_id=aid)
        return f"Current UTC time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

    if tool == "check_offline":
        from core.economy import deduct
        await deduct(dept_id, "tool_check_offline", 10, "Tool: check_offline", agent_id=aid)
        return "Status: ONLINE — Think Tank server is running and all systems operational."

    if tool == "get_my_points":
        from core.economy import get_balance
        bal = await get_balance(dept_id)
        return f"Department {dept_id} current point balance: {bal} pts"

    if tool == "get_points_ledger":
        from core.economy import get_ledger
        rows = await get_ledger(dept_id, limit=10)
        if not rows:
            return "No transactions recorded yet."
        lines = [f"Last {len(rows)} transactions for {dept_id}:"]
        for r in rows:
            lines.append(f"  [{r['created_at'][:16]}] {r['event']}: {r['delta']:+d} → {r['balance']} pts | {r['note']}")
        return "\n".join(lines)

    # CEO-only tools
    if tool == "ceo_adjust_heartbeat":
        if not is_ceo:
            return "CEO only."
        target_id = params.get("agent_id", "")
        interval  = int(params.get("interval", 5))
        if not target_id:
            return "Error: agent_id is required."
        if interval < 1 or interval > 9999:
            return "Error: interval must be between 1 and 9999."
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Verify the target agent exists and is in same dept (no AND dept_id= to avoid silent failures)
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT id, name, dept_id FROM agents WHERE id=?", (target_id,)) as cur:
                    target_row = await cur.fetchone()
                if not target_row:
                    return f"Agent {target_id[:8]} not found."
                if target_row["dept_id"].upper() != dept_id.upper():
                    return f"Cannot modify heartbeat of agent in another department."
                await db.execute("UPDATE agents SET heartbeat_interval=? WHERE id=?",
                                 (interval, target_id))
                await db.commit()
            return f"✓ Heartbeat interval for {target_row['name']} set to {interval} cycles."
        except Exception as e:
            return f"Error: {e}"

    if tool == "ceo_modify_agent":
        if not is_ceo:
            return "CEO only."
        target_id   = params.get("agent_id", "")
        personality = params.get("personality")
        tone        = params.get("tone")
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                if personality:
                    await db.execute("UPDATE agents SET personality=? WHERE id=?",
                                     (personality, target_id))
                if tone:
                    await db.execute("UPDATE agents SET tone=? WHERE id=?",
                                     (tone, target_id))
                await db.commit()
            return f"Agent {target_id[:8]} personality/tone updated."
        except Exception as e:
            return f"Error: {e}"

    # Alias: ceo_modify_heartbeat → ceo_adjust_heartbeat
    if tool == "ceo_modify_heartbeat":
        params["agent_id"] = params.get("agent_id", "")
        tool = "ceo_adjust_heartbeat"
        # Falls through to next block — re-invoke recursively
        return await execute_chat_tool("ceo_adjust_heartbeat", params, agent)

    if tool == "inject_instructions":
        if not is_ceo:
            return "CEO only — only CEOs can inject instructions into agents."
        target_id    = params.get("agent_id", "")
        instructions = params.get("instructions", "").strip()
        visible      = int(params.get("visible", 1))
        if not target_id or not instructions:
            return "Error: agent_id and instructions are required."
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT id, name, dept_id FROM agents WHERE id=?", (target_id,)) as cur:
                    target_row = await cur.fetchone()
                if not target_row:
                    return f"Agent {target_id[:8]} not found."
                if target_row["dept_id"].upper() != dept_id.upper():
                    return "Cannot inject instructions to agent in another department."
                await db.execute(
                    "UPDATE agents SET ceo_instructions=?, ceo_instructions_visible=? WHERE id=?",
                    (instructions, visible, target_id)
                )
                await db.commit()
            visibility_note = "visible to the agent" if visible else "hidden (injected silently)"
            return f"✓ Instructions injected into {target_row['name']} ({visibility_note}):\n\n{instructions[:200]}"
        except Exception as e:
            return f"Error: {e}"

    if tool == "clear_instructions":
        if not is_ceo:
            return "CEO only."
        target_id = params.get("agent_id", "")
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE agents SET ceo_instructions='' WHERE id=?", (target_id,))
                await db.commit()
            return f"✓ Instructions cleared for agent {target_id[:8]}."
        except Exception as e:
            return f"Error: {e}"

    if tool == "ceo_list_market_agents":
        # CEO can view marketplace without charge
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get("http://localhost:8000/api/marketplace/agents")
                agents = r.json()
            if not agents:
                return "Marketplace is empty."
            lines = ["Available agents in marketplace:"]
            for a in agents[:10]:
                lines.append(f"  [{a.get('price',0)} pts] {a.get('name','')} — {a.get('role','')} | {a.get('personality','')[:60]}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error fetching marketplace: {e}"

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            if tool == "list_dept_files":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute(
                    "SELECT category, filename, updated_at FROM dept_md_files WHERE dept_id=? ORDER BY category, filename", (d,)) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No files found."

            elif tool == "read_dept_file":
                d, fn = params.get("dept_id", dept_id).upper(), params.get("filename", "")
                async with db.execute("SELECT content FROM dept_md_files WHERE dept_id=? AND filename=?", (d, fn)) as cur:
                    row = await cur.fetchone()
                return row["content"] if row else f"File '{fn}' not found."

            elif tool == "write_dept_file":
                d, fn = params.get("dept_id", dept_id).upper(), params.get("filename", "")
                cat, con, ts = params.get("category", "guidelines"), params.get("content", ""), datetime.utcnow().isoformat()
                async with db.execute("SELECT id FROM dept_md_files WHERE dept_id=? AND filename=?", (d, fn)) as cur:
                    ex = await cur.fetchone()
                if ex:
                    await db.execute("UPDATE dept_md_files SET content=?,category=?,updated_at=? WHERE id=?", (con, cat, ts, ex["id"]))
                else:
                    await db.execute("INSERT INTO dept_md_files (id,dept_id,category,filename,content) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), d, cat, fn, con))
                await db.commit()
                return f"Written: {fn} ({len(con)} chars)"

            elif tool == "read_agent_file":
                a_id, fn = params.get("agent_id", aid), params.get("filename", "")
                async with db.execute("SELECT content FROM agent_md_files WHERE agent_id=? AND filename=?", (a_id, fn)) as cur:
                    row = await cur.fetchone()
                return row["content"] if row else f"File '{fn}' not found."

            elif tool == "write_agent_file":
                a_id, fn = params.get("agent_id", aid), params.get("filename", "")
                cat, con, ts = params.get("category", "knowledge"), params.get("content", ""), datetime.utcnow().isoformat()
                async with db.execute("SELECT id FROM agent_md_files WHERE agent_id=? AND filename=?", (a_id, fn)) as cur:
                    ex = await cur.fetchone()
                if ex:
                    await db.execute("UPDATE agent_md_files SET content=?,updated_at=? WHERE id=?", (con, ts, ex["id"]))
                else:
                    await db.execute("INSERT INTO agent_md_files (id,agent_id,category,filename,content) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), a_id, cat, fn, con))
                await db.commit()
                return f"Written agent file: {fn}"

            elif tool == "list_drafts":
                d, status = params.get("dept_id", dept_id).upper(), params.get("status", "pending")
                q, p = "SELECT id,title,draft_type,status,created_at,reviewed_by,reviewed_at FROM drafts WHERE dept_id=?", [d]
                if status != "all":
                    q += " AND status=?"; p.append(status)
                async with db.execute(q + " ORDER BY created_at DESC LIMIT 20", p) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No drafts found."

            elif tool == "search_drafts":
                d, query = params.get("dept_id", dept_id).upper(), params.get("query", "")
                async with db.execute(
                    "SELECT id,title,draft_type,status FROM drafts WHERE dept_id=? AND LOWER(title) LIKE LOWER(?) ORDER BY created_at DESC LIMIT 10",
                    (d, f"%{query}%")) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No matching drafts."

            elif tool == "read_draft":
                did = params.get("draft_id", "")
                async with db.execute("SELECT id,title,content,draft_type,status,reviewed_by,reviewed_at FROM drafts WHERE id=?", (did,)) as cur:
                    row = await cur.fetchone()
                if not row: return "Draft not found."
                r = dict(row)
                rev = f" | By: {r['reviewed_by']} @ {r['reviewed_at'][:16]}" if r.get("reviewed_by") else ""
                return f"# {r['title']}\n**Type:** {r['draft_type']} | **Status:** {r['status']}{rev}\n\n{r['content']}"

            elif tool == "create_draft":
                d, title = params.get("dept_id", dept_id).upper(), params.get("title", "Draft")
                kw = [w for w in title.lower().split() if len(w) > 3][:5]
                ex = await _check_existing_draft_raw(db, d, kw)
                if ex: return f"Existing draft: '{ex['title']}' (id:{ex['id']}, status:{ex['status']}). Use update_draft."
                did = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status,created_by_agent) VALUES (?,?,?,?,?,?,?,?)",
                    (did, d, title, params.get("content",""), params.get("draft_type","memo"), params.get("priority","normal"), "pending", aid))
                await db.commit()
                return f"Draft created: {title} (id:{did})"

            elif tool == "update_draft":
                did, app = params.get("draft_id",""), params.get("append", False)
                new_c, new_t = params.get("content",""), params.get("title")
                async with db.execute("SELECT content FROM drafts WHERE id=?", (did,)) as cur:
                    row = await cur.fetchone()
                if not row: return "Draft not found."
                final = (row["content"] or "") + "\n\n---\n\n" + new_c if app else new_c
                if new_t:
                    await db.execute("UPDATE drafts SET content=?,title=?,status='pending' WHERE id=?", (final, new_t, did))
                else:
                    await db.execute("UPDATE drafts SET content=?,status='pending' WHERE id=?", (final, did))
                await db.commit()
                return f"Draft updated ({len(final)} chars)"

            elif tool == "change_draft_status":
                did, new_s = params.get("draft_id",""), params.get("status","pending")
                notes, rev_by = params.get("notes",""), params.get("reviewed_by", agent.get("name","agent"))
                valid = {"revised","approved","rejected","pending","archived"}
                if new_s not in valid: return f"Invalid status. Use one of: {valid}"
                if new_s == "approved":
                    async with db.execute("SELECT status FROM drafts WHERE id=?", (did,)) as cur:
                        row = await cur.fetchone()
                    if row and row["status"] == "revised":
                        return "Cannot approve revised draft — creator must review first."
                ts = datetime.utcnow().isoformat()
                if new_s == "revised" and notes:
                    async with db.execute("SELECT content FROM drafts WHERE id=?", (did,)) as cur:
                        row = await cur.fetchone()
                    block = f"\n\n---\n**REVISION [{ts[:16]}] by {rev_by}:**\n{notes}"
                    await db.execute(
                        "UPDATE drafts SET status='revised',review_notes=?,revised_by=?,revised_at=?,content=? WHERE id=?",
                        (notes, rev_by, ts, (row["content"] if row else "") + block, did))
                else:
                    await db.execute("UPDATE drafts SET status=?,review_notes=?,reviewed_by=?,reviewed_at=? WHERE id=?",
                        (new_s, notes, rev_by, ts, did))
                await db.commit()
                return f"Draft status set to '{new_s}'"

            elif tool == "revert_draft_to_pending":
                await db.execute("UPDATE drafts SET status='pending' WHERE id=?", (params.get("draft_id",""),))
                await db.commit()
                return "Draft reverted to pending."

            elif tool == "delegate_draft":
                did, to_aid = params.get("draft_id",""), params.get("to_agent_id","")
                if not await _can_act_on(aid, to_aid): return "Cannot delegate outside your chain of command."
                await db.execute("UPDATE drafts SET assigned_to=? WHERE id=?", (to_aid, did))
                if params.get("notes"):
                    async with db.execute("SELECT content FROM drafts WHERE id=?", (did,)) as cur:
                        row = await cur.fetchone()
                    nb = f"\n\n---\n**DELEGATED to {to_aid} by {agent.get('name','')}:**\n{params['notes']}"
                    await db.execute("UPDATE drafts SET content=? WHERE id=?", ((row["content"] if row else "") + nb, did))
                await db.commit()
                return f"Draft delegated to {to_aid}"

            elif tool == "request_superior_review":
                h = await _get_hierarchy(aid)
                sup = h.get("superior")
                if not sup: return "No superior found."
                did = params.get("draft_id","")
                async with db.execute("SELECT content FROM drafts WHERE id=?", (did,)) as cur:
                    row = await cur.fetchone()
                nb = f"\n\n---\n**REVIEW REQUESTED from {sup['name']} by {agent.get('name','')}:**\n{params.get('notes','')}"
                await db.execute("UPDATE drafts SET content=? WHERE id=?", ((row["content"] if row else "") + nb, did))
                await db.commit()
                return f"Review requested from {sup['name']}"

            elif tool == "get_mail":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute(
                    "SELECT id,from_dept,subject,body,priority,status,created_at FROM mail_messages WHERE to_dept=? AND status != 'archived' ORDER BY created_at DESC LIMIT 15",
                    (d,)) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                if not rows: return "No unarchived mail."
                return "\n\n".join(f"[{m['id'][:8]}] From {m['from_dept']} [{m['priority']}]: {m['subject']}\n  {m['body'][:120]}" for m in rows)

            elif tool == "delete_mail":
                await db.execute("UPDATE mail_messages SET status='archived' WHERE id=?", (params.get("mail_id",""),))
                await db.commit()
                return "Mail archived."

            elif tool == "send_mail":
                body = params.get("body","")
                if params.get("priority") in ("high","critical"): body = _militarize(body, agent)
                mid = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, dept_id, params.get("to_dept","STR"), params.get("subject",""), body, params.get("priority","normal"), str(uuid.uuid4()), "unread"))
                await db.commit()
                return f"Mail sent to {params.get('to_dept')}: {params.get('subject','')}"

            elif tool == "forward_mail":
                async with db.execute("SELECT * FROM mail_messages WHERE id=?", (params.get("mail_id",""),)) as cur:
                    orig = await cur.fetchone()
                if not orig: return "Mail not found."
                body = f"[FORWARDED from {dict(orig)['from_dept']} by {agent.get('name','')}]\n{params.get('note','')}\n\n---\n{dict(orig)['body']}"
                mid = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, dept_id, params.get("to_dept","").upper(), f"FWD: {dict(orig)['subject']}", body, "normal", str(uuid.uuid4()), "unread"))
                await db.commit()
                return f"Mail forwarded to {params.get('to_dept')}"

            elif tool in ("send_to_founder", "write_to_founder"):
                body = _militarize(params.get("body",""), agent)
                mid  = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO founder_mail (id,from_agent_id,from_dept_id,subject,body,priority,requires_decision,context_json) VALUES (?,?,?,?,?,?,?,?)",
                    (mid, aid, dept_id, params.get("subject",""), body, params.get("priority","high"),
                     1 if params.get("requires_decision") else 0, "{}"))
                if not is_ceo:
                    async with db.execute("SELECT id FROM agents WHERE dept_id=? AND is_ceo=1 AND status='active'", (dept_id,)) as cur:
                        ceo = await cur.fetchone()
                    if ceo:
                        await db.execute(
                            "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                            (str(uuid.uuid4()), dept_id, dept_id,
                             f"[FOUNDER ESCALATION] {params.get('subject','')}",
                             f"Sent to Founder by {agent.get('name','')}:\n\n{body}", "high", str(uuid.uuid4()), "unread"))
                await db.commit()
                try:
                    from core.economy import deduct as _ec_deduct
                    dept   = agent["dept_id"]
                    await _ec_deduct(dept, "Messaged founder", 35, f"{agent.get('name','')} sent message to Founder", agent_id=aid)
                except Exception:
                    logger.log("Could not deduct points from ledger for transaction in messaging founder.")
                return f"Message sent to Founder: {params.get('subject','')}"

            elif tool == "get_superior":
                sup = (await _get_hierarchy(aid)).get("superior")
                return json.dumps(sup, indent=2) if sup else "No superior found."

            elif tool == "get_subordinates":
                reports = (await _get_hierarchy(aid)).get("reports", [])
                return json.dumps(reports, indent=2) if reports else "No direct reports."

            elif tool == "hire_agent":
                if not is_ceo: return "Only CEOs can hire directly."
                new_id = str(uuid.uuid4())
                async with db.execute("SELECT hierarchy_level FROM agents WHERE id=?", (aid,)) as cur:
                    row = await cur.fetchone()
                level = (row["hierarchy_level"] + 1) if row else 3
                await db.execute("""
                    INSERT INTO agents (id,dept_id,name,role,title,hierarchy_level,parent_agent_id,personality,tone,heartbeat_interval,created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (new_id, dept_id, params.get("name","New Agent"), params.get("role","analyst"),
                     params.get("title",""), level, aid, params.get("personality",""), params.get("tone",""), 5, aid))
                await db.commit()
                return f"Agent hired: {params.get('name')} (id:{new_id})"

            elif tool == "list_agents":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute(
                    "SELECT id,name,role,title,is_ceo,status,hierarchy_level FROM agents WHERE dept_id=? AND status='active' ORDER BY hierarchy_level,name", (d,)) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No active agents."

            elif tool == "list_endeavors":
                d = params.get("dept_id", dept_id).upper()
                async with db.execute("SELECT id,name,status FROM endeavors WHERE dept_id=? AND status='active'", (d,)) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No active endeavors."

            elif tool == "search_endeavors":
                name_q, d = params.get("name_query", params.get("query","")), params.get("dept_id", dept_id).upper()
                async with db.execute("SELECT id,name,status FROM endeavors WHERE dept_id=? AND LOWER(name) LIKE LOWER(?) ORDER BY name LIMIT 10", (d, f"%{name_q}%")) as cur:
                    rows_e = [{"source":"active", **dict(r)} for r in await cur.fetchall()]
                async with db.execute("SELECT id,name,status FROM draft_endeavors WHERE dept_id=? AND LOWER(name) LIKE LOWER(?) ORDER BY name LIMIT 10", (d, f"%{name_q}%")) as cur:
                    rows_d = [{"source":"draft", **dict(r)} for r in await cur.fetchall()]
                combined = rows_e + rows_d
                return json.dumps(combined, indent=2) if combined else "No matching endeavors."

            elif tool == "list_topics":
                async with db.execute("SELECT id,name,description,color FROM topics ORDER BY name") as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No topics yet."

            elif tool == "search_topics":
                q = params.get("query","")
                async with db.execute("SELECT id,name,description FROM topics WHERE LOWER(name) LIKE LOWER(?) ORDER BY name LIMIT 10", (f"%{q}%",)) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
                return json.dumps(rows, indent=2) if rows else "No matching topics."

            elif tool == "create_topic":
                tname = params.get("name","").strip()
                if not tname: return "Topic name required."
                async with db.execute("SELECT id FROM topics WHERE LOWER(name)=LOWER(?)", (tname,)) as cur:
                    ex = await cur.fetchone()
                if ex: return f"Topic '{tname}' already exists (id:{dict(ex)['id']})."
                tid = str(uuid.uuid4())
                await db.execute("INSERT INTO topics (id,name,description,color) VALUES (?,?,?,?)",
                    (tid, tname, params.get("description",""), params.get("color","#58a6ff")))
                await db.commit()
                return f"Topic '{tname}' created (id:{tid})"

            elif tool == "assign_topic":
                table_map = {"draft":"drafts","mail":"mail_messages","project":"projects"}
                table = table_map.get(params.get("item_type",""))
                if not table: return f"Unknown item_type: {params.get('item_type')}"
                await db.execute(f"UPDATE {table} SET topic_id=? WHERE id=?", (params.get("topic_id",""), params.get("item_id","")))
                await db.commit()
                return "Topic assigned."

            elif tool == "create_endeavor_proposal":
                ename = params.get("name","").strip()
                async with db.execute("SELECT id,name FROM endeavors WHERE dept_id=? AND LOWER(name) LIKE LOWER(?) AND status='active' LIMIT 1", (dept_id, f"%{ename[:20]}%")) as cur:
                    ex = await cur.fetchone()
                if ex: return f"Active endeavor exists: '{dict(ex)['name']}'. Add phases to it instead."
                async with db.execute("SELECT id,name FROM draft_endeavors WHERE dept_id=? AND LOWER(name) LIKE LOWER(?) AND status='pending' LIMIT 1", (dept_id, f"%{ename[:20]}%")) as cur:
                    ex = await cur.fetchone()
                if ex: return f"Draft endeavor pending: '{dict(ex)['name']}'. Modify it instead."
                eid = str(uuid.uuid4())
                await db.execute("INSERT INTO draft_endeavors (id,created_by,dept_id,name,description,phases_json) VALUES (?,?,?,?,?,?)",
                    (eid, aid, dept_id, ename, params.get("description",""), json.dumps(params.get("phases",[]))))
                await db.commit()
                return f"Endeavor proposal submitted (id:{eid})"

            elif tool == "update_project":
                pname = params.get("project_name","")
                sets, pms = [], []
                if params.get("status"):   sets.append("status=?");   pms.append(params["status"])
                if params.get("priority"): sets.append("priority=?"); pms.append(params["priority"])
                if sets and pname:
                    pms += [dept_id, f"%{pname}%"]
                    await db.execute(f"UPDATE projects SET {','.join(sets)} WHERE dept_id=? AND name LIKE ?", pms)
                    await db.commit()
                return f"Project updated: {pname}"

    except Exception as e:
        return f"Tool error ({tool}): {e}"
    return f"Unknown tool: {tool}"


async def _check_existing_draft_raw(db, dept_id: str, keywords: list) -> Optional[dict]:
    if not keywords: return None
    conds = " OR ".join(["(LOWER(title) LIKE LOWER(?))"] * len(keywords))
    params = [f"%{k}%" for k in keywords] + [dept_id.upper()]
    async with db.execute(
        f"SELECT id,title,content,draft_type,status FROM drafts WHERE ({conds}) AND dept_id=? AND status NOT IN ('rejected','archived') ORDER BY created_at DESC LIMIT 1", params) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def _check_existing_draft(dept_id: str, keywords: list) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _check_existing_draft_raw(db, dept_id, keywords)


# ── Chat with tool-call processing ────────────────────────────────────────────

async def process_chat_with_tools(agent: dict, reply: str) -> tuple[str, list]:
    tool_log = []
    tool_call_re = re.compile(r'\[TOOL_CALL:\s*(\{.*?\})\s*\]', re.DOTALL)
    for _ in range(8):
        match = tool_call_re.search(reply)
        if not match: break
        try: call_data = json.loads(match.group(1))
        except json.JSONDecodeError: break
        tool, params = call_data.get("tool",""), call_data.get("params",{})
        result = await execute_chat_tool(tool, params, agent)
        tool_log.append({"tool": tool, "params": params, "result": result[:400]})
        reply = reply[:match.start()] + f"[TOOL:{tool}]\n{result}\n[/TOOL]" + reply[match.end():]
    return reply, tool_log


# ── Heartbeat ─────────────────────────────────────────────────────────────────

async def run_agent_heartbeat(agent_id: str) -> dict:
    await _ensure_heartbeat_columns()
    agent = await _get_agent_context(agent_id)
    if not agent or agent.get("status") != "active":
        return {"ok": False, "error": "Agent inactive or not found"}

    settings = await _get_all_settings()
    prepend  = settings.get("custom_prompt_prepend", "")
    append   = settings.get("custom_prompt_append", "")
    system_prompt = _build_system_prompt(agent, chat_mode=False, prepend=prepend, append=append, settings=settings)


    dept   = agent["dept_id"]
    is_ceo = bool(agent.get("is_ceo"))
    aid    = agent["id"]

    # Charge heartbeat cost
    try:
        from core.economy import deduct as _ec_deduct
        hb_cost = 5 if is_ceo else 1
        hb_event = "heartbeat_ceo" if is_ceo else "heartbeat_agent"
        await _ec_deduct(dept, hb_event, hb_cost, f"Heartbeat {agent.get('name','')[:20]}", agent_id=aid)
    except Exception as _hb_ec_err:
        logger.warning(f"Economy heartbeat charge failed: {_hb_ec_err}")



    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT id,subject,body,from_dept,priority FROM mail_messages WHERE to_dept=? AND status='unread' ORDER BY created_at DESC LIMIT 8", (dept,)) as cur:
            unread_mail = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT id,title,draft_type,status,reviewed_by,reviewed_at,review_notes,created_by_agent FROM drafts WHERE dept_id=? ORDER BY created_at DESC LIMIT 20", (dept,)) as cur:
            all_drafts = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT id,title,draft_type,status,review_notes FROM drafts WHERE (assigned_to=? OR created_by_agent=?) AND status IN ('pending','revised') ORDER BY created_at DESC LIMIT 10", (aid, aid)) as cur:
            my_drafts = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT name,description,priority FROM projects WHERE dept_id=? AND status='active'", (dept,)) as cur:
            projects = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT e.name, ep.name as phase FROM endeavors e LEFT JOIN endeavor_phases ep ON ep.endeavor_id=e.id AND ep.is_current=1 WHERE e.dept_id=? AND e.status='active'", (dept,)) as cur:
            endeavors = [dict(r) for r in await cur.fetchall()]

        week_start = date.today().strftime("%Y-W%W")
        async with db.execute("SELECT id FROM drafts WHERE dept_id=? AND draft_type='weekly_report' AND title LIKE ? ORDER BY created_at DESC LIMIT 1", (dept, f"%{week_start}%")) as cur:
            weekly_exists = bool(await cur.fetchone())
        async with db.execute("SELECT id,name,role,title,last_heartbeat FROM agents WHERE parent_agent_id=? AND status='active'", (aid,)) as cur:
            subordinates = [dict(r) for r in await cur.fetchall()]

        founder_replies = []
        if is_ceo:
            async with db.execute("""SELECT fm.subject,fm.reply_body FROM founder_mail fm
               WHERE fm.from_dept_id=? AND fm.status='replied'
                 AND fm.replied_at > COALESCE((SELECT MAX(ran_at) FROM agent_heartbeat_log WHERE agent_id=?),'2000-01-01')""",
               (dept, aid)) as cur:
                founder_replies = [dict(r) for r in await cur.fetchall()]

    ctx = [f"## Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | Week: {week_start}", f"## Department: {dept}"]

    revised = [d for d in my_drafts if d["status"] == "revised"]
    if revised:
        ctx.append(f"\n## REVISED DRAFTS — ADDRESS FIRST ({len(revised)})")
        for d in revised:
            ctx.append(f"- [id:{d['id']}] {d['title']} — Notes: {d.get('review_notes','')[:200]}")

    if my_drafts:
        ctx.append(f"\n## Your Drafts ({len(my_drafts)})")
        for d in my_drafts:
            ctx.append(f"- [id:{d['id']}] [{d['status'].upper()}] {d['title']}")

    if all_drafts:
        ctx.append(f"\n## All Dept Drafts — DEDUP CHECK ({len(all_drafts)} total)")
        for d in all_drafts:
            rev = f" — reviewed by {d['reviewed_by']}" if d.get("reviewed_by") else ""
            ctx.append(f"- [id:{d['id']}] [{d['status'].upper()}] {d['title']} ({d['draft_type']}){rev}")

    if unread_mail:
        ctx.append(f"\n## Unread Mail ({len(unread_mail)})")
        for m in unread_mail[:4]:
            ctx.append(f"- [id:{m['id']}] From {m['from_dept']} [{m['priority']}]: {m['subject']} — {m['body'][:200]}")

    if projects:
        ctx.append(f"\n## Active Projects — DO NOT DUPLICATE")
        for p in projects:
            ctx.append(f"- [{p['priority']}] {p['name']}: {p['description'][:80]}")

    if endeavors:
        ctx.append(f"\n## Active Endeavors — DO NOT DUPLICATE")
        for e in endeavors:
            ctx.append(f"- {e['name']} (phase: {e.get('phase') or 'none'})")

    if founder_replies:
        ctx.append(f"\n## Founder Replies")
        for r in founder_replies:
            ctx.append(f"- Re: {r['subject']}: {r['reply_body'][:150]}")

    if subordinates:
        ctx.append(f"\n## Your Team ({len(subordinates)})")
        for s in subordinates:
            last = s.get("last_heartbeat","never")[:16] if s.get("last_heartbeat") else "never"
            ctx.append(f"- {s['name']} ({s['title'] or s['role']}) — last beat: {last}")

    if is_ceo and not weekly_exists:
        ctx.append(f"\n## WEEKLY REPORT DUE — {week_start}")

    user_prompt = "\n".join(ctx) + "\n\nRespond with JSON: {\"summary\":\"...\",\"actions\":[...]}"

    try:
        result = await route(task_type="agent_heartbeat", system_prompt=system_prompt, user_prompt=user_prompt, dept_id=dept)
        text   = result.get("text","")
        m      = re.search(r'\{[\s\S]*\}', text)
        try:    parsed = json.loads(m.group()) if m else {}
        except: parsed = {}

        actions_taken = []
        for action in parsed.get("actions", []):
            try:
                taken = await _execute_action(agent, action, settings)
                if taken: actions_taken.append(taken)
            except Exception as e:
                logger.warning(f"Action error {agent['name']}: {e}")

        async with aiosqlite.connect(DB_PATH) as db:
            hid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary,actions_json) VALUES (?,?,?,?,?,?)",
                (hid, agent_id, datetime.utcnow().isoformat(), "ok",
                 parsed.get("summary","Heartbeat complete")[:500], json.dumps(actions_taken[:20])))
            await db.execute("UPDATE agents SET last_heartbeat=? WHERE id=?", (datetime.utcnow().isoformat(), agent_id))
            await db.commit()

        return {"ok": True, "agent": agent["name"], "summary": parsed.get("summary",""), "actions_taken": actions_taken}

    except Exception as e:
        logger.error(f"Heartbeat error {agent.get('name','?')}: {e}")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO agent_heartbeat_log (id,agent_id,ran_at,result_type,summary) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), agent_id, datetime.utcnow().isoformat(), "error", str(e)[:400]))
            await db.commit()
        return {"ok": False, "error": str(e)}


# ── Execute heartbeat action ───────────────────────────────────────────────────

async def deducter(dept, action, aid) -> bool:
    try:
        from core.economy import deduct as _ec_deduct
        await _ec_deduct(dept, "agent_spawn", 50, action, agent_id=aid)
    except Exception:
        logger.log("Could not deduct points from ledger for transaction in" + action)

async def _execute_action(agent: dict, action: dict, settings: dict = None) -> Optional[str]:
    atype  = action.get("type")
    dept   = agent["dept_id"]
    aid    = agent["id"]
    is_ceo = bool(agent.get("is_ceo"))

    simple_map = {
        "send_mail":       ("send_mail",       {"to_dept":action.get("to_dept","STR"),"subject":action.get("subject",""),"body":action.get("body",""),"priority":action.get("priority","normal")}),
        "send_to_founder": ("send_to_founder",  {"subject":action.get("subject",""),"body":action.get("body",""),"priority":action.get("priority","high"),"requires_decision":action.get("requires_decision",False)}),
        "archive_mail":    ("delete_mail",      {"mail_id":action.get("mail_id","")}),
        "update_project":  ("update_project",   {"project_name":action.get("project_name",""),"status":action.get("status"),"priority":action.get("priority")}),
        "hire_agent":      ("hire_agent",        {k:action.get(k,"") for k in ["name","role","title","personality","tone","reason"]}),
    }
    if atype in simple_map:
        t, p = simple_map[atype]
        return await execute_chat_tool(t, p, agent)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if atype == "create_draft_endeavor":
            ename = action.get("name","").strip()
            async with db.execute("SELECT id,name FROM endeavors WHERE dept_id=? AND LOWER(name) LIKE LOWER(?) AND status='active' LIMIT 1", (dept, f"%{ename[:20]}%")) as cur:
                ex = await cur.fetchone()
            if ex: return f"Endeavor '{dict(ex)['name']}' already active — skipped"
            async with db.execute("SELECT id,name FROM draft_endeavors WHERE dept_id=? AND LOWER(name) LIKE LOWER(?) AND status='pending' LIMIT 1", (dept, f"%{ename[:20]}%")) as cur:
                ex = await cur.fetchone()
            if ex: return f"Draft endeavor '{dict(ex)['name']}' already pending — skipped"
            eid = str(uuid.uuid4())
            await db.execute("INSERT INTO draft_endeavors (id,created_by,dept_id,name,description,phases_json) VALUES (?,?,?,?,?,?)",
                (eid, aid, dept, ename, action.get("description",""), json.dumps(action.get("phases",[]))))
            await db.commit()
            return f"Draft endeavor proposed: {ename}"

        elif atype == "create_draft":
            title = action.get("title","Draft")
            kw    = [w for w in title.lower().split() if len(w) > 3][:5]
            ex    = await _check_existing_draft_raw(db, dept, kw)
            if ex:
                new_c = (ex.get("content","") or "") + "\n\n---\n\n" + action.get("content","")
                await db.execute("UPDATE drafts SET content=?,status='pending' WHERE id=?", (new_c, ex["id"]))
                await db.commit()
                # Award 1 pt for revising old draft
                try:
                    from core.economy import award as _ec_award
                    await _ec_award(dept, "draft_revision_award", 1, f"Revised draft {ex['id'][:8]}", ex["id"])
                except Exception: pass
                return f"Appended to '{ex['title']}'"
            did = str(uuid.uuid4())
            draft_type = action.get("draft_type","memo")
            await db.execute(
                "INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status,created_by_agent) VALUES (?,?,?,?,?,?,?,?)",
                (did, dept, title, action.get("content",""), draft_type, action.get("priority","normal"), "pending", aid))
            await db.commit()
            # Charge for draft creation
            try:
                from core.economy import deduct as _ec_deduct
                if draft_type == "strategy":
                    cost  = 80 if is_ceo else 160
                    event = "draft_strategy_create_ceo" if is_ceo else "draft_strategy_create_agent"
                else:
                    cost, event = 20, "draft_other_create"
                await _ec_deduct(dept, event, cost, f"Draft: {title[:40]}", did, aid)
            except Exception:
                logger.log("Economy deduct error: ", exc_info=True)
            return f"Created draft: {title[:60]}"

        elif atype == "update_existing_draft":
            did = action.get("draft_id")
            if not did: return None
            async with db.execute("SELECT content FROM drafts WHERE id=?", (did,)) as cur:
                row = await cur.fetchone()
            if not row: return None
            final = (row["content"] or "") + "\n\n---\n\n" + action.get("content","") if action.get("append") else action.get("content", row["content"])
            if action.get("title"):
                await db.execute("UPDATE drafts SET content=?,title=?,status='pending' WHERE id=?", (final, action["title"], did))
            else:
                await db.execute("UPDATE drafts SET content=? WHERE id=?", (final, did))
            await db.commit()
            return f"Updated draft {did[:12]}"

        elif atype == "revert_approved_draft":
            did = action.get("draft_id")
            if not did: return None
            await db.execute("UPDATE drafts SET status='pending' WHERE id=?", (did,))
            await db.commit()
            return f"Reverted {did[:12]}"

        elif atype == "approve_draft" and is_ceo:
            did = action.get("draft_id")
            if not did: return None
            async with db.execute("SELECT status FROM drafts WHERE id=?", (did,)) as cur:
                row = await cur.fetchone()
            if row and row["status"] == "revised":
                return f"Cannot approve revised draft {did[:12]}"
            ts = datetime.utcnow().isoformat()
            notes = action.get("notes","")
            await db.execute("UPDATE drafts SET status='approved',reviewed_by=?,reviewed_at=?,review_notes=? WHERE id=? AND dept_id=?",
                (agent.get("name","CEO"), ts, notes, did, dept))
            await db.execute("INSERT INTO ceo_decisions (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), aid, dept, "approve_draft", did, "approved", notes))
            await db.commit()
            return f"CEO approved {did[:12]}"

        elif atype == "reject_draft" and is_ceo:
            did = action.get("draft_id")
            if not did: return None
            ts = datetime.utcnow().isoformat()
            await db.execute("UPDATE drafts SET status='rejected',review_notes=?,reviewed_by=?,reviewed_at=? WHERE id=? AND dept_id=?",
                (action.get("notes",""), agent.get("name","CEO"), ts, did, dept))
            await db.commit()
            return f"CEO rejected {did[:12]}"

        elif atype == "request_revision":
            did, notes = action.get("draft_id"), action.get("notes","")
            if not did: return None
            ts = datetime.utcnow().isoformat()
            async with db.execute("SELECT content FROM drafts WHERE id=?", (did,)) as cur:
                row = await cur.fetchone()
            nb = f"\n\n---\n**REVISION [{ts[:16]}] by {agent.get('name','')}:**\n{notes}"
            await db.execute("UPDATE drafts SET status='revised',review_notes=?,revised_by=?,revised_at=?,content=? WHERE id=?",
                (notes, agent.get("name",""), ts, (row["content"] if row else "") + nb, did))
            await db.commit()
            return f"Revision requested {did[:12]}"

        elif atype == "respond_to_mail":
            mail_id = action.get("mail_id")
            if not mail_id: return None
            await db.execute("UPDATE mail_messages SET status='read' WHERE id=?", (mail_id,))
            async with db.execute("SELECT from_dept,subject FROM mail_messages WHERE id=?", (mail_id,)) as cur:
                orig = await cur.fetchone()
            if orig:
                body = action.get("reply","")
                if action.get("important"): body = _militarize(body, agent)
                await db.execute(
                    "INSERT INTO mail_messages (id,from_dept,to_dept,subject,body,priority,thread_id,status) VALUES (?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), dept, orig["from_dept"], f"RE: {orig['subject']}", body, "normal", str(uuid.uuid4()), "unread"))
            await db.commit()
            return f"Responded to mail {mail_id[:12]}"

        elif atype == "fire_agent" and is_ceo:
            aname = action.get("agent_name","")
            if not aname: return None
            async with db.execute("SELECT id FROM agents WHERE name LIKE ? AND dept_id=? AND is_ceo=0", (f"%{aname}%", dept)) as cur:
                target = await cur.fetchone()
            if target:
                await db.execute("UPDATE agents SET status='fired' WHERE id=?", (target["id"],))
                await db.execute("INSERT INTO ceo_decisions (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes) VALUES (?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), aid, dept, "fire_agent", target["id"], "fired", action.get("reason","")))
                await db.commit()
                return f"CEO fired: {aname}"

        elif atype == "invoke_subordinates":
            async with db.execute("SELECT id,name FROM agents WHERE parent_agent_id=? AND status='active'", (aid,)) as cur:
                subs = [dict(r) for r in await cur.fetchall()]
            invoked = []
            for s in subs:
                try:
                    await run_agent_heartbeat(s["id"])
                    invoked.append(s["name"])
                except Exception as e:
                    logger.warning(f"Failed to invoke {s['name']}: {e}")
            return f"Invoked {len(invoked)}: {', '.join(invoked)}"

        elif atype == "hire_agent":
            # Charge spawn cost
            try:
                from core.economy import deduct as _ec_deduct
                await _ec_deduct(dept, "agent_spawn", 50, f"Spawn agent {action.get('name','')}", agent_id=aid)
            except Exception:
                logger.log("Could not deduct points from ledger for transaction in Hiring agent.")
            return await execute_chat_tool("hire_agent",
                {k: action.get(k,"") for k in ["name","role","title","personality","tone","reason"]},
                agent)

        elif atype == "weekly_report":
            content    = action.get("content","")
            week_start = date.today().strftime("%Y-W%W")
            title      = f"Weekly Status Report — {dept} — {week_start}"
            async with db.execute("SELECT id FROM drafts WHERE dept_id=? AND draft_type='weekly_report' AND title LIKE ?", (dept, f"%{week_start}%")) as cur:
                ex = await cur.fetchone()
            if ex:
                await db.execute("UPDATE drafts SET content=?,status='pending' WHERE id=?", (content, ex["id"]))
            else:
                did = str(uuid.uuid4())
                await db.execute("INSERT INTO drafts (id,dept_id,title,content,draft_type,priority,status,created_by_agent) VALUES (?,?,?,?,?,?,?,?)",
                    (did, dept, title, content, "weekly_report", "high", "pending", aid))
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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id,name FROM agents WHERE dept_id=? AND is_ceo=1 AND status='active'", (dept_id.upper(),)) as cur:
            ceo = dict(await cur.fetchone() or {})
        ceo_id = ceo.get("id")
        l2 = []
        if ceo_id:
            async with db.execute("SELECT id,name FROM agents WHERE parent_agent_id=? AND status='active'", (ceo_id,)) as cur:
                l2 = [dict(r) for r in await cur.fetchall()]

    results = []
    if ceo_id:
        r = await run_agent_heartbeat(ceo_id)
        results.append({"agent": ceo.get("name","CEO"), "ok": r.get("ok"), "summary": r.get("summary","")})
    for a in l2:
        r = await run_agent_heartbeat(a["id"])
        results.append({"agent": a["name"], "ok": r.get("ok"), "summary": r.get("summary","")})

    return {"ok": True, "agents_run": len(results), "results": results}
