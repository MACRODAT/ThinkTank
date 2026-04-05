"""core/endeavors_db.py — Create endeavors-related tables on startup."""
import aiosqlite
from core.database import DB_PATH


async def init_endeavors_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS endeavors (
                id          TEXT PRIMARY KEY,
                dept_id     TEXT,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                status      TEXT DEFAULT 'active',
                color       TEXT DEFAULT '#58a6ff',
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS endeavor_phases (
                id                TEXT PRIMARY KEY,
                endeavor_id       TEXT NOT NULL,
                name              TEXT NOT NULL,
                description       TEXT DEFAULT '',
                order_index       INTEGER NOT NULL DEFAULT 0,
                duration_days     INTEGER NOT NULL DEFAULT 7,
                start_date        TEXT,
                planned_end_date  TEXT,
                extended_end_date TEXT,
                status            TEXT DEFAULT 'pending',
                is_current        INTEGER DEFAULT 0,
                created_at        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (endeavor_id) REFERENCES endeavors(id) ON DELETE CASCADE
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS phase_objectives (
                id          TEXT PRIMARY KEY,
                phase_id    TEXT NOT NULL,
                title       TEXT NOT NULL,
                notes       TEXT DEFAULT '',
                is_done     INTEGER DEFAULT 0,
                done_at     TEXT,
                order_index INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                updated_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (phase_id) REFERENCES endeavor_phases(id) ON DELETE CASCADE
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS objective_time_logs (
                id               TEXT PRIMARY KEY,
                objective_id     TEXT NOT NULL,
                started_at       TEXT NOT NULL,
                stopped_at       TEXT,
                duration_seconds INTEGER DEFAULT 0,
                FOREIGN KEY (objective_id) REFERENCES phase_objectives(id) ON DELETE CASCADE
            )""")

        await db.commit()
