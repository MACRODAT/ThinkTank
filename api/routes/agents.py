"""api/routes/agents.py — Full agent management + chat API."""
from __future__ import annotations
import uuid, json
from datetime import datetime
from typing import Optional
from pathlib import Path
import aiosqlite
from fastapi import APIRouter, Body
from core.database import DB_PATH

router = APIRouter(tags=["agents"])

BASE_FILES = Path(__file__).parent.parent.parent / "data" / "dept_files"
BASE_FILES.mkdir(parents=True, exist_ok=True)

def _row(r): return dict(r) if r else None
def _rows(rs): return [dict(r) for r in rs]


# ══════════════════════════════════════════════════════════════
#  HEARTBEAT STATUS — must be BEFORE /{aid} routes
# ══════════════════════════════════════════════════════════════

@router.get("/api/agents/heartbeat/status")
async def heartbeat_status():
    """Show agent queue: who ran last, who is next."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT a.id, a.name, a.dept_id, a.is_ceo, a.last_heartbeat,
                   a.heartbeat_interval, a.title, a.role,
                   (SELECT summary FROM agent_heartbeat_log
                    WHERE agent_id=a.id ORDER BY ran_at DESC LIMIT 1) as last_summary,
                   (SELECT result_type FROM agent_heartbeat_log
                    WHERE agent_id=a.id ORDER BY ran_at DESC LIMIT 1) as last_result
            FROM agents a WHERE a.status='active'
            ORDER BY a.last_heartbeat ASC NULLS FIRST
        """) as cur:
            agents = _rows(await cur.fetchall())
    return {"agents": agents, "queue_length": len(agents)}


# ══════════════════════════════════════════════════════════════
#  AGENTS CRUD
# ══════════════════════════════════════════════════════════════

@router.get("/api/agents")
async def list_agents(dept_id: Optional[str] = None, status: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        clauses, params = ["1=1"], []
        if dept_id: clauses.append("a.dept_id=?");  params.append(dept_id.upper())
        if status:  clauses.append("a.status=?");   params.append(status)
        where = " AND ".join(clauses)
        async with db.execute(f"""
            SELECT a.*,
              (SELECT COUNT(*) FROM agents s WHERE s.parent_agent_id=a.id AND s.status='active') as subordinate_count,
              p.name as parent_name
            FROM agents a
            LEFT JOIN agents p ON a.parent_agent_id=p.id
            WHERE {where}
            ORDER BY a.dept_id, a.hierarchy_level, a.name
        """, params) as cur:
            return _rows(await cur.fetchall())


@router.get("/api/agents/{aid}")
async def get_agent(aid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT a.*, p.name as parent_name,
              (SELECT COUNT(*) FROM agents s WHERE s.parent_agent_id=a.id AND s.status='active') as subordinate_count
            FROM agents a LEFT JOIN agents p ON a.parent_agent_id=p.id
            WHERE a.id=?
        """, (aid,)) as cur:
            agent = _row(await cur.fetchone())
        if not agent: return {"error": "Not found"}
        async with db.execute(
            "SELECT * FROM agent_md_files WHERE agent_id=? ORDER BY category, filename", (aid,)
        ) as cur:
            agent["md_files"] = _rows(await cur.fetchall())
        async with db.execute(
            "SELECT id,name,role,title,status,hierarchy_level FROM agents WHERE parent_agent_id=?", (aid,)
        ) as cur:
            agent["subordinates"] = _rows(await cur.fetchall())
        async with db.execute(
            "SELECT * FROM agent_heartbeat_log WHERE agent_id=? ORDER BY ran_at DESC LIMIT 10", (aid,)
        ) as cur:
            agent["recent_heartbeats"] = _rows(await cur.fetchall())
        # chat history
        async with db.execute("""
            SELECT * FROM agent_chat_history WHERE agent_id=?
            ORDER BY created_at ASC LIMIT 50
        """, (aid,)) as cur:
            agent["chat_history"] = _rows(await cur.fetchall())
    return agent


@router.post("/api/agents")
async def create_agent(
    dept_id:            str           = Body(...),
    name:               str           = Body(...),
    role:               str           = Body("analyst"),
    title:              str           = Body(""),
    is_ceo:             int           = Body(0),
    hierarchy_level:    int           = Body(3),
    parent_agent_id:    Optional[str] = Body(None),
    personality:        str           = Body(""),
    tone:               str           = Body(""),
    heartbeat_interval: int           = Body(5),
    model_override:     str           = Body(""),
    extra_models:       str           = Body("[]"),
    profile_image_url:  str           = Body(""),
    created_by:         str           = Body("system"),
):
    aid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO agents
            (id,dept_id,name,role,title,is_ceo,hierarchy_level,parent_agent_id,
             personality,tone,heartbeat_interval,model_override,extra_models,
             profile_image_url,created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (aid, dept_id.upper(), name, role, title, is_ceo, hierarchy_level,
              parent_agent_id, personality, tone, heartbeat_interval,
              model_override, extra_models, profile_image_url, created_by))
        await db.commit()
    return {"id": aid}


@router.put("/api/agents/{aid}")
async def update_agent(
    aid: str,
    name:               Optional[str] = Body(None),
    role:               Optional[str] = Body(None),
    title:              Optional[str] = Body(None),
    personality:        Optional[str] = Body(None),
    tone:               Optional[str] = Body(None),
    heartbeat_interval: Optional[int] = Body(None),
    model_override:     Optional[str] = Body(None),
    extra_models:       Optional[str] = Body(None),
    profile_image_url:  Optional[str] = Body(None),
    status:             Optional[str] = Body(None),
):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = {
            "name": name, "role": role, "title": title,
            "personality": personality, "tone": tone,
            "heartbeat_interval": heartbeat_interval,
            "model_override": model_override, "extra_models": extra_models,
            "profile_image_url": profile_image_url, "status": status,
        }
        for col, val in fields.items():
            if val is not None:
                await db.execute(f"UPDATE agents SET {col}=? WHERE id=?", (val, aid))
        await db.commit()
    return {"ok": True}


@router.post("/api/agents/{aid}/fire")
async def fire_agent(
    aid:      str,
    fired_by: str = Body(...),
    reason:   str = Body(""),
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT dept_id FROM agents WHERE id=?", (aid,)) as cur:
            target = _row(await cur.fetchone())
        if not target: return {"error": "Agent not found"}
        await db.execute("UPDATE agents SET status='fired' WHERE id=?", (aid,))
        if fired_by != "founder":
            async with db.execute("SELECT id FROM agents WHERE id=? AND is_ceo=1", (fired_by,)) as cur:
                ceo = _row(await cur.fetchone())
            if ceo:
                did = str(uuid.uuid4())
                await db.execute("""
                    INSERT INTO ceo_decisions
                    (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes)
                    VALUES (?,?,?,?,?,?,?)
                """, (did, fired_by, target["dept_id"], "fire_agent", aid, "fired", reason))
        await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  CHAT WITH AGENT  (this was causing 422 — fixed)
# ══════════════════════════════════════════════════════════════

@router.post("/api/agents/{aid}/chat")
async def chat_with_agent(
    aid:     str,
    message: str = Body(..., embed=True),
):
    """Send a message to an agent and get a response. Uses JSON body: {"message": "..."}"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Load agent
        async with db.execute("""
            SELECT a.*, p.name as parent_name
            FROM agents a LEFT JOIN agents p ON a.parent_agent_id=p.id
            WHERE a.id=?
        """, (aid,)) as cur:
            agent = _row(await cur.fetchone())
        if not agent:
            return {"error": "Agent not found"}

        # Load agent files for context
        async with db.execute(
            "SELECT category, filename, content FROM agent_md_files WHERE agent_id=?", (aid,)
        ) as cur:
            files = _rows(await cur.fetchall())

        # Load dept files
        async with db.execute(
            "SELECT category, filename, content FROM dept_md_files WHERE dept_id=?",
            (agent["dept_id"],)
        ) as cur:
            dept_files = _rows(await cur.fetchall())

        # Load recent chat history for this agent (last 20 turns)
        async with db.execute("""
            SELECT role, content FROM agent_chat_history
            WHERE agent_id=? ORDER BY created_at DESC LIMIT 20
        """, (aid,)) as cur:
            history_rows = list(reversed(_rows(await cur.fetchall())))

    # Build system prompt
    from core.agent_runner import _build_system_prompt
    agent["md_files"]   = files
    agent["dept_files"] = dept_files

    system_prompt = _build_system_prompt(agent, chat_mode=True)

    # Build conversation messages
    messages = []
    for h in history_rows:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    # Call AI
    from core.ai_router import route_chat
    result = await route_chat(
        agent_id=aid,
        system_prompt=system_prompt,
        messages=messages,
    )
    reply = result.get("text", "…")

    # Persist both turns
    async with aiosqlite.connect(DB_PATH) as db:
        for role, content in [("user", message), ("assistant", reply)]:
            cid = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO agent_chat_history (id, agent_id, role, content)
                VALUES (?,?,?,?)
            """, (cid, aid, role, content))
        await db.commit()

    return {"reply": reply, "agent_name": agent["name"]}


@router.delete("/api/agents/{aid}/chat")
async def clear_chat(aid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM agent_chat_history WHERE agent_id=?", (aid,))
        await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  AGENT MD FILES
# ══════════════════════════════════════════════════════════════

@router.get("/api/agents/{aid}/files")
async def list_agent_files(aid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM agent_md_files WHERE agent_id=? ORDER BY category, filename", (aid,)
        ) as cur:
            return _rows(await cur.fetchall())


@router.post("/api/agents/{aid}/files")
async def upsert_agent_file(
    aid:      str,
    category: str = Body(...),
    filename: str = Body(...),
    content:  str = Body(""),
):
    ts = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM agent_md_files WHERE agent_id=? AND category=? AND filename=?",
            (aid, category, filename)
        ) as cur:
            existing = _row(await cur.fetchone())
        if existing:
            await db.execute(
                "UPDATE agent_md_files SET content=?,updated_at=? WHERE id=?",
                (content, ts, existing["id"])
            )
        else:
            fid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO agent_md_files (id,agent_id,category,filename,content) VALUES (?,?,?,?,?)",
                (fid, aid, category, filename, content)
            )
        await db.commit()
    return {"ok": True}


@router.delete("/api/agents/{aid}/files/{fid}")
async def delete_agent_file(aid: str, fid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM agent_md_files WHERE id=? AND agent_id=?", (fid, aid))
        await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  DEPARTMENT MD FILES
# ══════════════════════════════════════════════════════════════

@router.get("/api/deptfiles/{dept_id}")
async def list_dept_files(dept_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM dept_md_files WHERE dept_id=? ORDER BY category, filename",
            (dept_id.upper(),)
        ) as cur:
            return _rows(await cur.fetchall())


@router.post("/api/deptfiles/{dept_id}")
async def upsert_dept_file(
    dept_id:  str,
    category: str = Body(...),
    filename: str = Body(...),
    content:  str = Body(""),
):
    ts = datetime.utcnow().isoformat()
    did = dept_id.upper()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM dept_md_files WHERE dept_id=? AND filename=?", (did, filename)
        ) as cur:
            existing = _row(await cur.fetchone())
        if existing:
            await db.execute(
                "UPDATE dept_md_files SET content=?,category=?,updated_at=? WHERE id=?",
                (content, category, ts, existing["id"])
            )
        else:
            fid = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO dept_md_files (id,dept_id,category,filename,content) VALUES (?,?,?,?,?)",
                (fid, did, category, filename, content)
            )
        await db.commit()
    return {"ok": True}


@router.delete("/api/deptfiles/{dept_id}/{fid}")
async def delete_dept_file(dept_id: str, fid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM dept_md_files WHERE id=? AND dept_id=?", (fid, dept_id.upper())
        )
        await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  FOUNDER INBOX
# ══════════════════════════════════════════════════════════════

@router.get("/api/founder/inbox")
async def founder_inbox(status: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE f.status=?" if status else ""
        params = (status,) if status else ()
        async with db.execute(f"""
            SELECT f.*, a.name as agent_name, a.title as agent_title, a.profile_image_url
            FROM founder_mail f
            JOIN agents a ON f.from_agent_id=a.id
            {where}
            ORDER BY CASE f.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END,
                     f.created_at DESC
        """, params) as cur:
            return _rows(await cur.fetchall())


@router.post("/api/founder/inbox/{mid}/read")
async def mark_founder_mail_read(mid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE founder_mail SET status='read' WHERE id=?", (mid,))
        await db.commit()
    return {"ok": True}


@router.post("/api/founder/inbox/{mid}/reply")
async def reply_founder_mail(mid: str, reply_body: str = Body(..., embed=True)):
    ts = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE founder_mail SET status='replied', replied_at=?, reply_body=? WHERE id=?",
            (ts, reply_body, mid)
        )
        await db.commit()
    return {"ok": True}


@router.post("/api/founder/mail")
async def send_to_founder(
    from_agent_id:     str = Body(...),
    from_dept_id:      str = Body(...),
    subject:           str = Body(...),
    body:              str = Body(...),
    priority:          str = Body("high"),
    requires_decision: int = Body(0),
    context_json:      str = Body("{}"),
):
    mid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO founder_mail
            (id,from_agent_id,from_dept_id,subject,body,priority,requires_decision,context_json)
            VALUES (?,?,?,?,?,?,?,?)
        """, (mid, from_agent_id, from_dept_id.upper(), subject, body,
               priority, requires_decision, context_json))
        await db.commit()
    return {"id": mid}


@router.get("/api/founder/stats")
async def founder_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) as c FROM founder_mail WHERE status='unread'"
        ) as cur:
            unread = (await cur.fetchone())["c"]
        async with db.execute(
            "SELECT COUNT(*) as c FROM founder_mail WHERE requires_decision=1 AND status != 'replied'"
        ) as cur:
            pending_decisions = (await cur.fetchone())["c"]
        async with db.execute(
            "SELECT COUNT(*) as c FROM agent_spawn_requests WHERE status='pending'"
        ) as cur:
            spawn_requests = (await cur.fetchone())["c"]
        async with db.execute(
            "SELECT COUNT(*) as c FROM draft_endeavors WHERE status='pending'"
        ) as cur:
            draft_endeavors_count = (await cur.fetchone())["c"]
    return {
        "unread_mail": unread,
        "pending_decisions": pending_decisions,
        "spawn_requests": spawn_requests,
        "draft_endeavors": draft_endeavors_count,
    }


# ══════════════════════════════════════════════════════════════
#  SPAWN REQUESTS
# ══════════════════════════════════════════════════════════════

@router.get("/api/spawn-requests")
async def list_spawn_requests(status: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE s.status=?" if status else ""
        params = (status,) if status else ()
        async with db.execute(f"""
            SELECT s.*, a.name as requester_name, a.is_ceo as requester_is_ceo
            FROM agent_spawn_requests s
            JOIN agents a ON s.requesting_agent_id=a.id
            {where}
            ORDER BY s.created_at DESC
        """, params) as cur:
            return _rows(await cur.fetchall())


@router.post("/api/spawn-requests")
async def request_spawn(
    requesting_agent_id:  str = Body(...),
    dept_id:              str = Body(...),
    proposed_name:        str = Body(...),
    proposed_role:        str = Body(...),
    proposed_title:       str = Body(""),
    proposed_personality: str = Body(""),
    proposed_tone:        str = Body(""),
    proposed_skills:      str = Body(""),
    proposed_heartbeat:   int = Body(5),
):
    sid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT is_ceo FROM agents WHERE id=? AND dept_id=?",
            (requesting_agent_id, dept_id.upper())
        ) as cur:
            requester = _row(await cur.fetchone())
        auto_status = "approved" if (requester and requester["is_ceo"]) else "pending"
        await db.execute("""
            INSERT INTO agent_spawn_requests
            (id,requesting_agent_id,dept_id,proposed_name,proposed_role,
             proposed_title,proposed_personality,proposed_tone,proposed_skills,
             proposed_heartbeat,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (sid, requesting_agent_id, dept_id.upper(), proposed_name, proposed_role,
               proposed_title, proposed_personality, proposed_tone, proposed_skills,
               proposed_heartbeat, auto_status))
        new_agent_id = None
        if auto_status == "approved":
            new_agent_id = str(uuid.uuid4())
            async with db.execute(
                "SELECT hierarchy_level FROM agents WHERE id=?", (requesting_agent_id,)
            ) as cur:
                req_row = _row(await cur.fetchone())
            new_level = (req_row["hierarchy_level"] + 1) if req_row else 4
            await db.execute("""
                INSERT INTO agents
                (id,dept_id,name,role,title,hierarchy_level,parent_agent_id,
                 personality,tone,heartbeat_interval,created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (new_agent_id, dept_id.upper(), proposed_name, proposed_role,
                   proposed_title, new_level, requesting_agent_id,
                   proposed_personality, proposed_tone, proposed_heartbeat,
                   requesting_agent_id))
            await db.execute(
                "UPDATE agent_spawn_requests SET approved_by=? WHERE id=?",
                (requesting_agent_id, sid)
            )
        await db.commit()
    return {"id": sid, "auto_approved": auto_status == "approved", "agent_id": new_agent_id}


@router.post("/api/spawn-requests/{sid}/approve")
async def approve_spawn(sid: str, approved_by: str = Body("founder", embed=True)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM agent_spawn_requests WHERE id=?", (sid,)) as cur:
            req = _row(await cur.fetchone())
        if not req: return {"error": "Not found"}
        new_agent_id = str(uuid.uuid4())
        await db.execute("""
            INSERT INTO agents
            (id,dept_id,name,role,title,hierarchy_level,parent_agent_id,
             personality,tone,heartbeat_interval,created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (new_agent_id, req["dept_id"], req["proposed_name"], req["proposed_role"],
               req["proposed_title"], 3, req["requesting_agent_id"],
               req["proposed_personality"], req["proposed_tone"],
               req["proposed_heartbeat"], req["requesting_agent_id"]))
        await db.execute(
            "UPDATE agent_spawn_requests SET status='approved', approved_by=? WHERE id=?",
            (approved_by, sid)
        )
        await db.commit()
    return {"ok": True, "agent_id": new_agent_id}


@router.post("/api/spawn-requests/{sid}/reject")
async def reject_spawn(sid: str, reason: str = Body("", embed=True)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE agent_spawn_requests SET status='rejected', rejection_reason=? WHERE id=?",
            (reason, sid)
        )
        await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  DRAFT ENDEAVORS
# ══════════════════════════════════════════════════════════════

@router.get("/api/draft-endeavors")
async def list_draft_endeavors(status: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE de.status=?" if status else ""
        params = (status,) if status else ()
        async with db.execute(f"""
            SELECT de.*, a.name as agent_name, a.is_ceo
            FROM draft_endeavors de
            JOIN agents a ON de.created_by=a.id
            {where}
            ORDER BY de.created_at DESC
        """, params) as cur:
            rows = _rows(await cur.fetchall())
    for r in rows:
        try: r["phases"] = json.loads(r.get("phases_json","[]"))
        except: r["phases"] = []
    return rows


@router.post("/api/draft-endeavors")
async def create_draft_endeavor(
    created_by:  str = Body(...),
    dept_id:     str = Body(...),
    name:        str = Body(...),
    description: str = Body(""),
    phases_json: str = Body("[]"),
):
    eid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO draft_endeavors (id,created_by,dept_id,name,description,phases_json)
            VALUES (?,?,?,?,?,?)
        """, (eid, created_by, dept_id.upper(), name, description, phases_json))
        await db.commit()
    return {"id": eid}


@router.post("/api/draft-endeavors/{eid}/approve")
async def approve_draft_endeavor(
    eid:          str,
    reviewed_by:  str = Body("founder"),
    review_notes: str = Body(""),
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM draft_endeavors WHERE id=?", (eid,)) as cur:
            draft = _row(await cur.fetchone())
        if not draft: return {"error": "Not found"}
        real_id = str(uuid.uuid4())
        await db.execute("""
            INSERT INTO endeavors (id,dept_id,name,description,status,color)
            VALUES (?,?,?,?,'active','#58a6ff')
        """, (real_id, draft["dept_id"], draft["name"], draft["description"]))
        try:
            phases = json.loads(draft["phases_json"])
            for i, p in enumerate(phases):
                from datetime import timedelta
                pid = str(uuid.uuid4())
                dur = p.get("duration_days", 7)
                await db.execute("""
                    INSERT INTO endeavor_phases
                    (id,endeavor_id,name,description,order_index,duration_days)
                    VALUES (?,?,?,?,?,?)
                """, (pid, real_id, p.get("name","Phase"), p.get("description",""), i, dur))
        except: pass
        await db.execute(
            "UPDATE draft_endeavors SET status='approved', reviewed_by=?, review_notes=? WHERE id=?",
            (reviewed_by, review_notes, eid)
        )
        await db.commit()
    return {"ok": True, "endeavor_id": real_id}


@router.post("/api/draft-endeavors/{eid}/reject")
async def reject_draft_endeavor(
    eid:          str,
    reviewed_by:  str = Body("founder"),
    review_notes: str = Body(""),
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE draft_endeavors SET status='rejected', reviewed_by=?, review_notes=? WHERE id=?",
            (reviewed_by, review_notes, eid)
        )
        await db.commit()
    return {"ok": True}


@router.put("/api/draft-endeavors/{eid}")
async def edit_draft_endeavor(
    eid:         str,
    name:        Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    phases_json: Optional[str] = Body(None),
):
    async with aiosqlite.connect(DB_PATH) as db:
        if name:        await db.execute("UPDATE draft_endeavors SET name=? WHERE id=?",        (name, eid))
        if description: await db.execute("UPDATE draft_endeavors SET description=? WHERE id=?", (description, eid))
        if phases_json: await db.execute("UPDATE draft_endeavors SET phases_json=? WHERE id=?", (phases_json, eid))
        await db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  CEO DECISIONS
# ══════════════════════════════════════════════════════════════

@router.get("/api/ceo-decisions")
async def list_ceo_decisions(dept_id: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE cd.dept_id=?" if dept_id else ""
        params = (dept_id.upper(),) if dept_id else ()
        async with db.execute(f"""
            SELECT cd.*, a.name as ceo_name
            FROM ceo_decisions cd JOIN agents a ON cd.ceo_agent_id=a.id
            {where}
            ORDER BY cd.created_at DESC LIMIT 100
        """, params) as cur:
            return _rows(await cur.fetchall())


@router.post("/api/ceo-decisions")
async def record_ceo_decision(
    ceo_agent_id:  str = Body(...),
    dept_id:       str = Body(...),
    decision_type: str = Body(...),
    target_id:     str = Body(...),
    decision:      str = Body(...),
    notes:         str = Body(""),
):
    did = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO ceo_decisions
            (id,ceo_agent_id,dept_id,decision_type,target_id,decision,notes)
            VALUES (?,?,?,?,?,?,?)
        """, (did, ceo_agent_id, dept_id.upper(), decision_type, target_id, decision, notes))
        await db.commit()
    return {"id": did}


# ══════════════════════════════════════════════════════════════
#  HEARTBEAT TRIGGER
# ══════════════════════════════════════════════════════════════

@router.post("/api/agents/{aid}/heartbeat")
async def trigger_heartbeat(aid: str):
    from core.agent_runner import run_agent_heartbeat
    return await run_agent_heartbeat(aid)
