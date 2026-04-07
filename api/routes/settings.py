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
    # Heartbeat: seconds between scheduler ticks (default 60s = 1 minute)
    "heartbeat_tick_seconds": "60",
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
):
    current = await _load()
    real_key = claude_api_key
    if claude_api_key and "…" in claude_api_key:
        real_key = current.get("claude_api_key", "")

    await _save({
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
    })

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
