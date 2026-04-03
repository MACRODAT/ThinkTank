"""
api/routes/settings.py — Read/write AI backend settings and probe Ollama models.
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
    "ai_backend":        "claude",          # "claude" | "ollama"
    "claude_api_key":    getattr(getattr(config, "ai", None) and config.ai.claude, "api_key", ""),
    "claude_model":      getattr(getattr(config, "ai", None) and config.ai.claude, "model", "claude-sonnet-4-20250514"),
    "ollama_base_url":   getattr(getattr(config, "ai", None) and config.ai.ollama, "base_url", "http://localhost:11434"),
    "ollama_model":      getattr(getattr(config, "ai", None) and config.ai.ollama, "model", "llama3"),
    "ollama_timeout":    "120",
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
    # Mask API key for display
    masked = {**s}
    if masked.get("claude_api_key") and len(masked["claude_api_key"]) > 8:
        masked["claude_api_key"] = masked["claude_api_key"][:8] + "…"
    return masked


@router.post("")
async def save_settings(
    ai_backend:      str = Body(...),
    claude_api_key:  Optional[str] = Body(None),
    claude_model:    str = Body("claude-sonnet-4-20250514"),
    ollama_base_url: str = Body("http://localhost:11434"),
    ollama_model:    str = Body("llama3"),
    ollama_timeout:  str = Body("120"),
):
    current = await _load()
    # Only update API key if a real new value was sent (not the masked version)
    real_key = claude_api_key
    if claude_api_key and "…" in claude_api_key:
        real_key = current.get("claude_api_key", "")

    await _save({
        "ai_backend":      ai_backend,
        "claude_api_key":  real_key or current.get("claude_api_key", ""),
        "claude_model":    claude_model,
        "ollama_base_url": ollama_base_url.rstrip("/"),
        "ollama_model":    ollama_model,
        "ollama_timeout":  ollama_timeout,
    })

    # Invalidate cached claude client so it picks up new key
    import core.ai_router as _r
    _r._claude_client = None

    return {"ok": True}


@router.get("/ollama-models")
async def fetch_ollama_models(base_url: Optional[str] = None):
    """Probe Ollama for installed models."""
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
        "claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5",
        "claude-opus-4-20250514", "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ]}
