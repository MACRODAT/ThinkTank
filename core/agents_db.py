"""core/agents_db.py — Multi-agent system tables."""
import aiosqlite
from core.database import DB_PATH


async def init_agents_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id                 TEXT PRIMARY KEY,
                dept_id            TEXT NOT NULL,
                name               TEXT NOT NULL,
                role               TEXT NOT NULL DEFAULT 'analyst',
                title              TEXT DEFAULT '',
                is_ceo             INTEGER DEFAULT 0,
                hierarchy_level    INTEGER DEFAULT 3,
                parent_agent_id    TEXT,
                status             TEXT DEFAULT 'active',
                profile_image_url  TEXT DEFAULT '',
                personality        TEXT DEFAULT '',
                tone               TEXT DEFAULT '',
                heartbeat_interval INTEGER DEFAULT 5,
                model_override     TEXT DEFAULT '',
                extra_models       TEXT DEFAULT '[]',
                created_by         TEXT DEFAULT 'system',
                created_at         TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                last_heartbeat     TEXT,
                FOREIGN KEY (dept_id) REFERENCES departments(id),
                FOREIGN KEY (parent_agent_id) REFERENCES agents(id)
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_md_files (
                id         TEXT PRIMARY KEY,
                agent_id   TEXT,
                dept_id    TEXT,
                category   TEXT NOT NULL,
                filename   TEXT NOT NULL,
                content    TEXT DEFAULT '',
                updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS dept_md_files (
                id         TEXT PRIMARY KEY,
                dept_id    TEXT NOT NULL,
                category   TEXT NOT NULL,
                filename   TEXT NOT NULL,
                content    TEXT DEFAULT '',
                updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (dept_id) REFERENCES departments(id)
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS founder_mail (
                id                TEXT PRIMARY KEY,
                from_agent_id     TEXT NOT NULL,
                from_dept_id      TEXT NOT NULL,
                subject           TEXT NOT NULL,
                body              TEXT NOT NULL,
                priority          TEXT DEFAULT 'high',
                status            TEXT DEFAULT 'unread',
                requires_decision INTEGER DEFAULT 0,
                context_json      TEXT DEFAULT '{}',
                created_at        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                replied_at        TEXT,
                reply_body        TEXT DEFAULT '',
                FOREIGN KEY (from_agent_id) REFERENCES agents(id)
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_spawn_requests (
                id                   TEXT PRIMARY KEY,
                requesting_agent_id  TEXT NOT NULL,
                dept_id              TEXT NOT NULL,
                proposed_name        TEXT NOT NULL,
                proposed_role        TEXT NOT NULL,
                proposed_title       TEXT DEFAULT '',
                proposed_personality TEXT DEFAULT '',
                proposed_tone        TEXT DEFAULT '',
                proposed_skills      TEXT DEFAULT '',
                proposed_heartbeat   INTEGER DEFAULT 5,
                status               TEXT DEFAULT 'pending',
                approved_by          TEXT DEFAULT '',
                rejection_reason     TEXT DEFAULT '',
                created_at           TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (requesting_agent_id) REFERENCES agents(id)
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ceo_decisions (
                id            TEXT PRIMARY KEY,
                ceo_agent_id  TEXT NOT NULL,
                dept_id       TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                target_id     TEXT NOT NULL,
                decision      TEXT NOT NULL,
                notes         TEXT DEFAULT '',
                created_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (ceo_agent_id) REFERENCES agents(id)
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_heartbeat_log (
                id          TEXT PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                ran_at      TEXT NOT NULL,
                result_type TEXT DEFAULT 'ok',
                summary     TEXT DEFAULT '',
                actions_json TEXT DEFAULT '[]',
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS draft_endeavors (
                id           TEXT PRIMARY KEY,
                created_by   TEXT NOT NULL,
                dept_id      TEXT NOT NULL,
                name         TEXT NOT NULL,
                description  TEXT DEFAULT '',
                phases_json  TEXT DEFAULT '[]',
                status       TEXT DEFAULT 'pending',
                reviewed_by  TEXT DEFAULT '',
                review_notes TEXT DEFAULT '',
                created_at   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (created_by) REFERENCES agents(id),
                FOREIGN KEY (dept_id)    REFERENCES departments(id)
            )""")

        # Chat history per agent
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_chat_history (
                id         TEXT PRIMARY KEY,
                agent_id   TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )""")

        # Edit / status-change history for drafts
        await db.execute("""
            CREATE TABLE IF NOT EXISTS draft_history (
                id          TEXT PRIMARY KEY,
                draft_id    TEXT NOT NULL,
                actor       TEXT NOT NULL DEFAULT 'system',
                action      TEXT NOT NULL,
                notes       TEXT DEFAULT '',
                snapshot    TEXT DEFAULT '',
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )""")
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_draft_history ON draft_history(draft_id, created_at)")
        except Exception:
            pass

        # ── Live migrations (add columns to existing tables safely) ──────
        migrations = [
            ("agent_heartbeat_log", "actions_json",  "ALTER TABLE agent_heartbeat_log ADD COLUMN actions_json TEXT DEFAULT '[]'"),
            ("agents",             "extra_models",   "ALTER TABLE agents ADD COLUMN extra_models TEXT DEFAULT '[]'"),
            ("agents",             "profile_image_url", "ALTER TABLE agents ADD COLUMN profile_image_url TEXT DEFAULT ''"),
            ("drafts",             "topic_id",       "ALTER TABLE drafts ADD COLUMN topic_id TEXT DEFAULT ''"),
            ("drafts",             "reviewed_by",    "ALTER TABLE drafts ADD COLUMN reviewed_by TEXT DEFAULT ''"),
            ("drafts",             "revised_by",     "ALTER TABLE drafts ADD COLUMN revised_by TEXT DEFAULT ''"),
            ("drafts",             "revised_at",     "ALTER TABLE drafts ADD COLUMN revised_at TEXT DEFAULT ''"),
            ("drafts",             "assigned_to",    "ALTER TABLE drafts ADD COLUMN assigned_to TEXT DEFAULT ''"),
            ("drafts",             "created_by_agent","ALTER TABLE drafts ADD COLUMN created_by_agent TEXT DEFAULT ''"),
            ("mail_messages",      "topic_id",       "ALTER TABLE mail_messages ADD COLUMN topic_id TEXT DEFAULT ''"),
            ("projects",           "topic_id",       "ALTER TABLE projects ADD COLUMN topic_id TEXT DEFAULT ''"),
        ]
        for table, column, sql in migrations:
            try:
                await db.execute(sql)
            except Exception:
                pass  # Column already exists — safe to ignore

        await db.commit()


async def seed_ceo_agents():
    """Create default CEO agents for each department if not already present."""
    CEO_DEFS = {
        "HF":  (
            "Dr. Aria Wellstone", "Chief Wellbeing Officer",
            "Empathetic, thorough, protective. Deeply cares about agent welfare. Cautious with escalation. Notices patterns others miss. Strong intuition for team dynamics.",
            "Warm, professional, concise. Uses inclusive language. Checks emotional temperature before diving into facts."
        ),
        "FIN": (
            "Victor Ledge", "Chief Financial Officer",
            "Analytical, precise, risk-aware. Methodical decision-maker. Values long-term stability over short-term gains. Never approves without seeing the numbers.",
            "Formal, data-driven, brief. States assumptions. Uses tables and lists. Ends with clear recommendation."
        ),
        "RES": (
            "Dr. Lyra Voss", "Chief Research Officer",
            "Curious, rigorous, evidence-based. Never asserts without data. Loves deep dives and citations. Comfortable sitting with uncertainty.",
            "Academic, detailed, objective. Cites sources. Distinguishes between evidence levels (strong/weak/speculative)."
        ),
        "ING": (
            "Kai Solaris", "Chief Engineering Officer",
            "Systems thinker, first-principles approach. Builds for robustness. Skeptical of shortcuts. Always asks 'what breaks first?'",
            "Technical, precise, direct. Uses code/pseudocode when helpful. Flags dependencies and failure modes."
        ),
        "STR": (
            "Commander Rex Altair", "Chief Strategy Officer",
            "Bold, visionary, adaptive. Sees 10 steps ahead. Calculates risk vs reward constantly. Never acts without considering second-order effects.",
            "Commanding, strategic, confident. Uses military-style brevity for urgent matters. Structured: SITUATION → ASSESSMENT → RECOMMENDATION."
        ),
    }

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        for dept_id, (name, title, personality, tone) in CEO_DEFS.items():
            async with db.execute(
                "SELECT id FROM agents WHERE dept_id=? AND is_ceo=1", (dept_id,)
            ) as cur:
                existing = await cur.fetchone()
            if not existing:
                import uuid
                aid = str(uuid.uuid4())
                await db.execute("""
                    INSERT INTO agents
                    (id,dept_id,name,role,title,is_ceo,hierarchy_level,
                     status,personality,tone,heartbeat_interval,created_by)
                    VALUES (?,?,?,?,?,1,1,'active',?,?,3,'system')
                """, (aid, dept_id, name, "ceo", title, personality, tone))
        await db.commit()
