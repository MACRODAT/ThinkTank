"""api/routes/endeavors.py — Full CRUD for Endeavors, Phases, Objectives, Time tracking."""
from __future__ import annotations
import uuid
from datetime import date, datetime, timedelta
from typing import Optional
import aiosqlite
from fastapi import APIRouter, Body
from core.database import DB_PATH

router = APIRouter(tags=["endeavors"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _row(r): return dict(r) if r else None
def _rows(rs): return [dict(r) for r in rs]

async def _phases_for(db, endeavor_id: str):
    async with db.execute("""
        SELECT ep.*,
          (SELECT COUNT(*) FROM phase_objectives po WHERE po.phase_id=ep.id) as total_objectives,
          (SELECT COUNT(*) FROM phase_objectives po WHERE po.phase_id=ep.id AND po.is_done=1) as done_objectives
        FROM endeavor_phases ep WHERE ep.endeavor_id=? ORDER BY ep.order_index
    """, (endeavor_id,)) as cur:
        return _rows(await cur.fetchall())

async def _objectives_for(db, phase_id: str):
    async with db.execute("""
        SELECT po.*,
          COALESCE((SELECT SUM(tl.duration_seconds)
                    FROM objective_time_logs tl
                    WHERE tl.objective_id=po.id AND tl.stopped_at IS NOT NULL), 0) as total_seconds,
          (SELECT tl.id FROM objective_time_logs tl
           WHERE tl.objective_id=po.id AND tl.stopped_at IS NULL LIMIT 1) as active_log_id,
          (SELECT tl.started_at FROM objective_time_logs tl
           WHERE tl.objective_id=po.id AND tl.stopped_at IS NULL LIMIT 1) as active_since
        FROM phase_objectives po WHERE po.phase_id=? ORDER BY po.order_index
    """, (phase_id,)) as cur:
        return _rows(await cur.fetchall())


# ── Dashboard tasks ───────────────────────────────────────────────────────────

@router.get("/api/endeavors/today")
async def today_tasks():
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT po.*, ep.name as phase_name, ep.id as phase_id, ep.is_current,
                   COALESCE(ep.extended_end_date, ep.planned_end_date) as effective_end,
                   e.name as endeavor_name, e.id as endeavor_id, e.color as endeavor_color
            FROM phase_objectives po
            JOIN endeavor_phases ep ON po.phase_id=ep.id
            JOIN endeavors e ON ep.endeavor_id=e.id
            WHERE po.is_done=0 AND ep.is_current=1
            ORDER BY po.order_index
        """) as cur:
            today_list = _rows(await cur.fetchall())
        async with db.execute("""
            SELECT po.*, ep.name as phase_name, ep.id as phase_id,
                   COALESCE(ep.extended_end_date, ep.planned_end_date) as effective_end,
                   e.name as endeavor_name, e.id as endeavor_id, e.color as endeavor_color
            FROM phase_objectives po
            JOIN endeavor_phases ep ON po.phase_id=ep.id
            JOIN endeavors e ON ep.endeavor_id=e.id
            WHERE po.is_done=0
              AND COALESCE(ep.extended_end_date, ep.planned_end_date) < ?
              AND ep.status != 'completed'
            ORDER BY effective_end
        """, (today,)) as cur:
            overdue = _rows(await cur.fetchall())
    return {"today": today_list, "overdue": overdue}


@router.get("/api/endeavors/calendar")
async def calendar_events(year: int = None, month: int = None):
    if not year or not month:
        n = date.today(); year, month = n.year, n.month
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT ep.start_date, ep.planned_end_date, ep.extended_end_date,
                   ep.name as phase_name, ep.is_current, e.name as endeavor_name, e.color
            FROM endeavor_phases ep JOIN endeavors e ON ep.endeavor_id=e.id
            WHERE (strftime('%Y',ep.start_date)=? AND strftime('%m',ep.start_date)=?)
               OR (strftime('%Y',COALESCE(ep.extended_end_date,ep.planned_end_date))=?
                   AND strftime('%m',COALESCE(ep.extended_end_date,ep.planned_end_date))=?)
        """, (str(year), f"{month:02d}", str(year), f"{month:02d}")) as cur:
            phases = _rows(await cur.fetchall())
    events = {}
    for p in phases:
        def add(d, evt):
            if d: events.setdefault(d, []).append(evt)
        add(p.get("start_date"), {"type":"phase_start","name":p["phase_name"],"endeavor":p["endeavor_name"],"color":p["color"]})
        end = p.get("extended_end_date") or p.get("planned_end_date")
        add(end, {"type":"phase_end","name":p["phase_name"],"endeavor":p["endeavor_name"],"color":p["color"],"is_current":bool(p["is_current"])})
    return {"events": events, "year": year, "month": month}


# ── Endeavors CRUD ────────────────────────────────────────────────────────────

@router.get("/api/endeavors")
async def list_endeavors(dept_id: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        where = "WHERE e.dept_id=?" if dept_id else ""
        params = (dept_id.upper(),) if dept_id else ()
        async with db.execute(f"""
            SELECT e.*,
              (SELECT COUNT(*) FROM endeavor_phases ep WHERE ep.endeavor_id=e.id) as phase_count,
              (SELECT ep.name FROM endeavor_phases ep WHERE ep.endeavor_id=e.id AND ep.is_current=1 LIMIT 1) as current_phase,
              (SELECT COUNT(*) FROM phase_objectives po
               JOIN endeavor_phases ep ON po.phase_id=ep.id
               WHERE ep.endeavor_id=e.id AND po.is_done=0 AND ep.is_current=1) as pending_tasks
            FROM endeavors e {where} ORDER BY e.created_at DESC
        """, params) as cur:
            return _rows(await cur.fetchall())


@router.post("/api/endeavors")
async def create_endeavor(
    name:        str           = Body(...),
    description: str           = Body(""),
    dept_id:     Optional[str] = Body(None),
    color:       str           = Body("#58a6ff"),
    status:      str           = Body("active"),
):
    eid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO endeavors (id,dept_id,name,description,status,color) VALUES (?,?,?,?,?,?)",
            (eid, dept_id.upper() if dept_id else None, name, description, status, color)
        )
        await db.commit()
    return {"id": eid}


@router.get("/api/endeavors/{eid}")
async def get_endeavor(eid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM endeavors WHERE id=?", (eid,)) as cur:
            e = _row(await cur.fetchone())
        if not e: return {"error": "Not found"}
        phases = await _phases_for(db, eid)
        for p in phases:
            p["objectives"] = await _objectives_for(db, p["id"])
        e["phases"] = phases
    return e


@router.put("/api/endeavors/{eid}")
async def update_endeavor(
    eid: str,
    name:        Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    dept_id:     Optional[str] = Body(None),
    color:       Optional[str] = Body(None),
    status:      Optional[str] = Body(None),
):
    async with aiosqlite.connect(DB_PATH) as db:
        if name        is not None: await db.execute("UPDATE endeavors SET name=? WHERE id=?",        (name, eid))
        if description is not None: await db.execute("UPDATE endeavors SET description=? WHERE id=?", (description, eid))
        if dept_id     is not None: await db.execute("UPDATE endeavors SET dept_id=? WHERE id=?",     (dept_id.upper(), eid))
        if color       is not None: await db.execute("UPDATE endeavors SET color=? WHERE id=?",       (color, eid))
        if status      is not None: await db.execute("UPDATE endeavors SET status=? WHERE id=?",      (status, eid))
        await db.commit()
    return {"ok": True}


@router.delete("/api/endeavors/{eid}")
async def delete_endeavor(eid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM endeavors WHERE id=?", (eid,))
        await db.commit()
    return {"ok": True}


# ── Phases ────────────────────────────────────────────────────────────────────

@router.get("/api/endeavors/{eid}/phases")
async def list_phases(eid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _phases_for(db, eid)


@router.post("/api/endeavors/{eid}/phases")
async def add_phase(
    eid: str,
    name:          str           = Body(...),
    description:   str           = Body(""),
    duration_days: int           = Body(7),
    start_date:    Optional[str] = Body(None),
):
    pid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT MAX(order_index) as m FROM endeavor_phases WHERE endeavor_id=?", (eid,)) as cur:
            row = await cur.fetchone(); idx = (row["m"] or 0) + 1
        planned_end = None
        if start_date:
            planned_end = (datetime.fromisoformat(start_date) + timedelta(days=duration_days)).date().isoformat()
        await db.execute(
            "INSERT INTO endeavor_phases (id,endeavor_id,name,description,order_index,duration_days,start_date,planned_end_date) VALUES (?,?,?,?,?,?,?,?)",
            (pid, eid, name, description, idx, duration_days, start_date, planned_end)
        )
        await db.commit()
    return {"id": pid}


@router.put("/api/phases/{pid}")
async def update_phase(
    pid: str,
    name:          Optional[str] = Body(None),
    description:   Optional[str] = Body(None),
    duration_days: Optional[int] = Body(None),
    start_date:    Optional[str] = Body(None),
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if name          is not None: await db.execute("UPDATE endeavor_phases SET name=? WHERE id=?",          (name, pid))
        if description   is not None: await db.execute("UPDATE endeavor_phases SET description=? WHERE id=?",   (description, pid))
        if duration_days is not None: await db.execute("UPDATE endeavor_phases SET duration_days=? WHERE id=?", (duration_days, pid))
        if start_date    is not None:
            await db.execute("UPDATE endeavor_phases SET start_date=? WHERE id=?", (start_date, pid))
            async with db.execute("SELECT duration_days FROM endeavor_phases WHERE id=?", (pid,)) as c:
                r = await c.fetchone()
            if r:
                planned = (datetime.fromisoformat(start_date) + timedelta(days=r["duration_days"])).date().isoformat()
                await db.execute("UPDATE endeavor_phases SET planned_end_date=? WHERE id=?", (planned, pid))
        await db.commit()
    return {"ok": True}


@router.delete("/api/phases/{pid}")
async def delete_phase(pid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM endeavor_phases WHERE id=?", (pid,))
        await db.commit()
    return {"ok": True}


@router.post("/api/phases/{pid}/set-current")
async def set_current_phase(pid: str, start_date: Optional[str] = Body(None)):
    today = date.today().isoformat()
    sd = start_date or today
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM endeavor_phases WHERE id=?", (pid,)) as cur:
            phase = _row(await cur.fetchone())
        if not phase: return {"error": "Not found"}
        await db.execute("UPDATE endeavor_phases SET is_current=0, status='pending' WHERE endeavor_id=?", (phase["endeavor_id"],))
        planned_end = (datetime.fromisoformat(sd) + timedelta(days=phase["duration_days"])).date().isoformat()
        await db.execute("""
            UPDATE endeavor_phases SET is_current=1, status='active',
              start_date=?, planned_end_date=?, extended_end_date=NULL WHERE id=?
        """, (sd, planned_end, pid))
        await db.execute("""
            UPDATE endeavor_phases SET status='completed'
            WHERE endeavor_id=? AND order_index < (SELECT order_index FROM endeavor_phases WHERE id=?)
        """, (phase["endeavor_id"], pid))
        await db.commit()
    return {"ok": True, "start_date": sd, "planned_end_date": planned_end}


@router.post("/api/phases/{pid}/extend")
async def extend_phase(pid: str, new_end_date: str = Body(...)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE endeavor_phases SET extended_end_date=? WHERE id=?", (new_end_date, pid))
        await db.commit()
    return {"ok": True}


# ── Objectives ────────────────────────────────────────────────────────────────

@router.get("/api/phases/{pid}/objectives")
async def list_objectives(pid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _objectives_for(db, pid)


@router.post("/api/phases/{pid}/objectives")
async def add_objective(pid: str, title: str = Body(...), notes: str = Body("")):
    oid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT MAX(order_index) as m FROM phase_objectives WHERE phase_id=?", (pid,)) as cur:
            row = await cur.fetchone(); idx = (row["m"] or 0) + 1
        await db.execute(
            "INSERT INTO phase_objectives (id,phase_id,title,notes,order_index) VALUES (?,?,?,?,?)",
            (oid, pid, title, notes, idx)
        )
        await db.commit()
    return {"id": oid}


@router.put("/api/objectives/{oid}")
async def update_objective(
    oid: str,
    title:       Optional[str] = Body(None),
    notes:       Optional[str] = Body(None),
    order_index: Optional[int] = Body(None),
):
    ts = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        if title       is not None: await db.execute("UPDATE phase_objectives SET title=?,updated_at=? WHERE id=?",       (title, ts, oid))
        if notes       is not None: await db.execute("UPDATE phase_objectives SET notes=?,updated_at=? WHERE id=?",       (notes, ts, oid))
        if order_index is not None: await db.execute("UPDATE phase_objectives SET order_index=? WHERE id=?",              (order_index, oid))
        await db.commit()
    return {"ok": True}


@router.delete("/api/objectives/{oid}")
async def delete_objective(oid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM phase_objectives WHERE id=?", (oid,))
        await db.commit()
    return {"ok": True}


@router.post("/api/objectives/{oid}/toggle")
async def toggle_objective(oid: str):
    ts = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT is_done FROM phase_objectives WHERE id=?", (oid,)) as cur:
            row = await cur.fetchone()
        if not row: return {"error": "Not found"}
        new_done = 0 if row["is_done"] else 1
        done_at  = ts if new_done else None
        await db.execute("UPDATE phase_objectives SET is_done=?,done_at=?,updated_at=? WHERE id=?",
                         (new_done, done_at, ts, oid))
        await db.commit()
    return {"ok": True, "is_done": new_done}


# ── Time tracking ─────────────────────────────────────────────────────────────

@router.post("/api/objectives/{oid}/time/start")
async def start_timer(oid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM objective_time_logs WHERE objective_id=? AND stopped_at IS NULL", (oid,)) as cur:
            if await cur.fetchone(): return {"ok": False, "error": "Timer already running"}
        lid = str(uuid.uuid4()); now = datetime.utcnow().isoformat()
        await db.execute("INSERT INTO objective_time_logs (id,objective_id,started_at) VALUES (?,?,?)", (lid, oid, now))
        await db.commit()
    return {"ok": True, "log_id": lid, "started_at": now}


@router.post("/api/objectives/{oid}/time/stop")
async def stop_timer(oid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM objective_time_logs WHERE objective_id=? AND stopped_at IS NULL ORDER BY started_at DESC LIMIT 1", (oid,)) as cur:
            log = _row(await cur.fetchone())
        if not log: return {"ok": False, "error": "No active timer"}
        now = datetime.utcnow()
        duration = int((now - datetime.fromisoformat(log["started_at"])).total_seconds())
        await db.execute("UPDATE objective_time_logs SET stopped_at=?,duration_seconds=? WHERE id=?",
                         (now.isoformat(), duration, log["id"]))
        await db.commit()
    return {"ok": True, "duration_seconds": duration}


@router.get("/api/objectives/{oid}/time")
async def get_time_logs(oid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM objective_time_logs WHERE objective_id=? ORDER BY started_at DESC", (oid,)) as cur:
            logs = _rows(await cur.fetchall())
        total  = sum(l["duration_seconds"] for l in logs if l.get("stopped_at"))
        active = next((l for l in logs if not l.get("stopped_at")), None)
    return {"logs": logs, "total_seconds": total, "active_log": active}
