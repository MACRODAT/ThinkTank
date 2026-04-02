"""
core/database.py — SQLite async database with full think tank schema.
"""
from __future__ import annotations
import aiosqlite
import json
import uuid
from pathlib import Path
from typing import Optional, Dict

DB_PATH = Path(__file__).parent.parent / "data" / "think_tank.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS departments (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    code          TEXT NOT NULL,
    description   TEXT,
    system_prompt TEXT,
    active        INTEGER DEFAULT 1,
    schedule      TEXT,
    last_run      TEXT,
    config        TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS mail_messages (
    id          TEXT PRIMARY KEY,
    from_dept   TEXT NOT NULL,
    to_dept     TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    priority    TEXT DEFAULT 'normal',
    status      TEXT DEFAULT 'unread',
    thread_id   TEXT,
    reply_to    TEXT,
    created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    read_at     TEXT,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS drafts (
    id              TEXT PRIMARY KEY,
    dept_id         TEXT NOT NULL,
    draft_type      TEXT NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    priority        TEXT DEFAULT 'normal',
    created_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    reviewed_at     TEXT,
    review_notes    TEXT,
    related_project TEXT,
    metadata        TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    dept_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'active',
    priority    TEXT DEFAULT 'normal',
    created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    updated_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    context     TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS dept_context (
    id          TEXT PRIMARY KEY,
    dept_id     TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT,
    updated_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    UNIQUE(dept_id, key)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    dept_id     TEXT,
    description TEXT,
    metadata    TEXT DEFAULT '{}',
    created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_mail_to_dept  ON mail_messages(to_dept, status);
CREATE INDEX IF NOT EXISTS idx_mail_thread   ON mail_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status, dept_id);
CREATE INDEX IF NOT EXISTS idx_projects_dept ON projects(dept_id, status);
"""


async def init_db():
    """Initialise the database and seed departments."""
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        await _seed_departments(db)


async def _seed_departments(db: aiosqlite.Connection):
    from departments.hf   import DEPT_META as HF
    from departments.fin  import DEPT_META as FIN
    from departments.res  import DEPT_META as RES
    from departments.ing  import DEPT_META as ING
    from departments.str_ import DEPT_META as STR

    for d in [HF, FIN, RES, ING, STR]:
        await db.execute(
            """INSERT OR IGNORE INTO departments
               (id, name, code, description, system_prompt, schedule, config)
               VALUES (?,?,?,?,?,?,?)""",
            (d["id"], d["name"], d["code"], d["description"],
             d["system_prompt"], d["schedule"], json.dumps(d.get("config", {})))
        )
        for proj in d.get("initial_projects", []):
            await db.execute(
                """INSERT OR IGNORE INTO projects
                   (id, dept_id, name, description, priority)
                   VALUES (?,?,?,?,?)""",
                (str(uuid.uuid4()), d["id"],
                 proj["name"], proj["description"], proj.get("priority", "normal"))
            )
    await db.commit()


async def log_event(dept_id: Optional[str], event_type: str,
                    description: str, metadata: dict = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO audit_log (event_type, dept_id, description, metadata) VALUES (?,?,?,?)",
            (event_type, dept_id, description, json.dumps(metadata or {}))
        )
        await db.commit()


async def set_context(dept_id: str, key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO dept_context (id, dept_id, key, value, updated_at)
               VALUES (?,?,?,?, strftime('%Y-%m-%dT%H:%M:%S','now'))
               ON CONFLICT(dept_id, key) DO UPDATE
               SET value=excluded.value,
                   updated_at=strftime('%Y-%m-%dT%H:%M:%S','now')""",
            (str(uuid.uuid4()), dept_id, key, value)
        )
        await db.commit()


async def get_context(dept_id: str) -> Dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT key, value FROM dept_context WHERE dept_id=?", (dept_id,)
        ) as cur:
            rows = await cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


def new_id() -> str:
    return str(uuid.uuid4())
