"""
api/routes/settings.py — AI backend settings with prepend/append global prompts.
"""
import json
import aiosqlite
import requests
from fastapi import APIRouter, Body
from typing import Optional
from core.database import DB_PATH
from core.config import config

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "ai_backend":          "claude",
    "claude_api_key":      getattr(getattr(config, "ai", None) and config.ai.claude, "api_key", ""),
    "claude_model":        getattr(getattr(config, "ai", None) and config.ai.claude, "model", "claude-sonnet-4-20250514"),
    "ollama_base_url":     getattr(getattr(config, "ai", None) and config.ai.ollama, "base_url", "http://localhost:11434"),
    "ollama_model":        getattr(getattr(config, "ai", None) and config.ai.ollama, "model", "llama3"),
    "ollama_timeout":      "120",
    "custom_prompt":       "",
    "custom_prompt_prepend": "",
    "custom_prompt_append":  "",
    "verbose_thinking":    "false",
    "heartbeat_tick_seconds": "60",

    # ── Web Search ─────────────────────────────────────────────────────────
    "web_search_enabled":      "false",
    "web_search_provider":     "brave",
    "web_search_api_key":      "",
    "web_search_max_results":  "5",

    # ── Editable system prompt templates ───────────────────────────────────
    # These replace the formerly hardcoded strings in agent_runner.py
    "prompt_ceo_authority": """## CEO Authority

You lead your department. Full autonomous authority within mandate.

**Independent decisions:** approve/reject drafts, respond to mail, create/edit strategies,
hire/fire agents, delegate to senior agents, update projects, propose draft endeavors.

**Escalate to Founder when:** unsure about major decision, cross-dept impact,
resource authority exceeded, critical/urgent situation.

**Weekly Report (Monday):** invoke all agents → collect briefs → write and submit one weekly report.

**Strict dedup:** Search BEFORE any draft action. Approved draft on same topic → revert to pending, then edit.
NEVER create a new draft if one exists. NEVER create duplicate projects or endeavors.

**Mail discipline:** ONE mail per recipient per topic. Use military format for urgent matters.

**Hierarchy:** You may only directly manage agents in your department.""",

    "prompt_agent_role": """## Your Role
- Produce drafts within your domain. CHECK for existing drafts first — update them, do NOT create new ones on the same topic.
- Max ONE mail per topic per recipient. Keep mails short.
- Escalate only genuinely important items to your CEO.
- Only interact with agents that report to you or your direct superior.
- Use hire_agent to hire — never create_draft for that purpose.""",

    "prompt_chat_mode": """## Chat Mode

You are speaking directly with the Founder. Be direct, in-character, and use your full personality.
When using tools: announce what you're doing, emit [TOOL_CALL: {...}], then reference the result naturally.
You may take real actions during chat (create drafts, send mail, etc.) — the Founder is watching in real time.""",

    "prompt_tools_spec_header": """## Available Tools

Emit tool calls anywhere in your response:
  [TOOL_CALL: {"tool": "tool_name", "params": {...}}]

Results come back as [TOOL:name]...[/TOOL].

Use the correct tool for each task:
- To HIRE someone → use hire_agent, NOT create_draft
- To SEARCH web → use web_search
- To WRITE a document → use create_draft (but check for existing drafts first!)""",

    "prompt_heartbeat_rules": """RULES:
1. MINIMIZE — only act when genuinely needed.
2. STRICT DEDUP — ALWAYS check existing drafts/projects/endeavors before creating. Update/append to existing ones.
3. MAIL DISCIPLINE — one mail per recipient per topic. Check recent mail before sending.
4. HIERARCHY — only act on personnel reporting to you.
5. REVISED DRAFTS — if you see drafts with REVISION REQUEST notes, address them FIRST.
6. RIGHT TOOL — use hire_agent to hire, create_draft for documents only, web_search for research.
7. NO DUPLICATE PROJECTS/ENDEAVORS — if one already exists, add to it or update it.""",
}


async def _ensure_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )""")
        await db.commit()


async def _load() -> dict:
    await _ensure_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT key, value FROM app_settings") as cur:
            rows = await cur.fetchall()
    stored = {r["key"]: r["value"] for r in rows}
    return {**DEFAULTS, **stored}


async def _save(data: dict):
    await _ensure_table()
    async with aiosqlite.connect(DB_PATH) as db:
        for k, v in data.items():
            await db.execute(
                "INSERT INTO app_settings (key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, str(v))
            )
        await db.commit()


@router.get("")
async def get_settings():
    s = await _load()
    masked = {**s}
    if masked.get("claude_api_key") and len(masked["claude_api_key"]) > 8:
        masked["claude_api_key"] = masked["claude_api_key"][:8] + "…"
    return masked


@router.post("")
async def save_settings(
    ai_backend:             str           = Body(...),
    claude_api_key:         Optional[str] = Body(None),
    claude_model:           str           = Body("claude-sonnet-4-20250514"),
    ollama_base_url:        str           = Body("http://localhost:11434"),
    ollama_model:           str           = Body("llama3"),
    ollama_timeout:         str           = Body("120"),
    custom_prompt:          str           = Body(""),
    custom_prompt_prepend:  str           = Body(""),
    custom_prompt_append:   str           = Body(""),
    verbose_thinking:       str           = Body("false"),
    heartbeat_tick_seconds: str           = Body("60"),
    # Web Search
    web_search_enabled:     str           = Body("false"),
    web_search_provider:    str           = Body("brave"),
    web_search_api_key:     Optional[str] = Body(None),
    web_search_max_results: str           = Body("5"),
    # Prompt templates
    prompt_ceo_authority:       Optional[str] = Body(None),
    prompt_agent_role:          Optional[str] = Body(None),
    prompt_chat_mode:           Optional[str] = Body(None),
    prompt_tools_spec_header:   Optional[str] = Body(None),
    prompt_heartbeat_rules:     Optional[str] = Body(None),
):
    current  = await _load()
    real_key = claude_api_key
    if claude_api_key and "…" in claude_api_key:
        real_key = current.get("claude_api_key", "")

    # Preserve existing search key if masked
    real_search_key = web_search_api_key
    if web_search_api_key and "…" in web_search_api_key:
        real_search_key = current.get("web_search_api_key", "")

    data = {
        "ai_backend":             ai_backend,
        "claude_api_key":         real_key or current.get("claude_api_key", ""),
        "claude_model":           claude_model,
        "ollama_base_url":        ollama_base_url.rstrip("/"),
        "ollama_model":           ollama_model,
        "ollama_timeout":         ollama_timeout,
        "custom_prompt":          custom_prompt,
        "custom_prompt_prepend":  custom_prompt_prepend,
        "custom_prompt_append":   custom_prompt_append,
        "verbose_thinking":       verbose_thinking,
        "heartbeat_tick_seconds": heartbeat_tick_seconds,
        "web_search_enabled":     web_search_enabled,
        "web_search_provider":    web_search_provider,
        "web_search_api_key":     real_search_key or current.get("web_search_api_key", ""),
        "web_search_max_results": web_search_max_results,
    }
    # Only save prompt templates if provided (don't wipe them with None)
    for k, v in [
        ("prompt_ceo_authority",     prompt_ceo_authority),
        ("prompt_agent_role",        prompt_agent_role),
        ("prompt_chat_mode",         prompt_chat_mode),
        ("prompt_tools_spec_header", prompt_tools_spec_header),
        ("prompt_heartbeat_rules",   prompt_heartbeat_rules),
    ]:
        if v is not None:
            data[k] = v

    await _save(data)

    import core.ai_router as _r
    _r._claude_client = None
    return {"ok": True}


@router.get("/ollama-models")
async def fetch_ollama_models(base_url: Optional[str] = None):
    settings = await _load()
    url = (base_url or settings.get("ollama_base_url", "http://localhost:11434")).rstrip("/")
    try:
        resp = requests.get(f"{url}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m["name"] for m in data.get("models", [])]
        return {"ok": True, "models": models, "url": url}
    except Exception as e:
        return {"ok": False, "models": [], "error": str(e)}


@router.get("/claude-models")
async def claude_models():
    return {"models": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ]}


@router.post("/test-search")
async def test_search(
    provider: str = Body(...),
    api_key:  str = Body(""),
):
    from core.web_search import test_search as _test
    return await _test(provider, api_key)


@router.get("/thinking-log")
async def thinking_log(limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM audit_log WHERE event_type='ai_thinking'
            ORDER BY created_at DESC LIMIT ?
        """, (limit,)) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:    d["meta_parsed"] = json.loads(d.get("metadata", "{}"))
        except: d["meta_parsed"] = {}
        result.append(d)
    return result
