"""
api/routes/extensions.py — Extension registry, install, enable/disable.
Extensions are Python modules dropped into core/extensions/ that can
expose new agent tools, heartbeat hooks, or API routes.
"""
from __future__ import annotations
import uuid, json, logging, importlib, sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Request
import aiosqlite
from core.database import DB_PATH

router = APIRouter(tags=["extensions"])
logger = logging.getLogger(__name__)

EXTENSIONS_DIR = Path(__file__).parent.parent.parent / "core" / "extensions"
EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── Built-in extension catalogue ─────────────────────────────────────────────
BUILTIN_CATALOGUE = [
    {
        "id":          "web_search_tool",
        "name":        "Web Search Tool",
        "description": "Lets agents call web_search during heartbeats and chat. Supports Brave, Tavily, SerpAPI, Bing, You.com, Exa, SearXNG, DuckDuckGo, Wikipedia, Jina.",
        "category":    "tool",
        "version":     "1.2.0",
        "author":      "Think Tank",
        "builtin":     True,
        "enabled":     True,
    },
    {
        "id":          "military_mail",
        "name":        "Military Mail Format",
        "description": "Automatically formats high-priority mail in military SITREP style with FROM/TIME/STOP markers.",
        "category":    "formatting",
        "version":     "1.0.0",
        "author":      "Think Tank",
        "builtin":     True,
        "enabled":     True,
    },
    {
        "id":          "draft_history",
        "name":        "Draft History Tracker",
        "description": "Logs every create/edit/status-change on drafts. View full audit trail per draft.",
        "category":    "audit",
        "version":     "1.0.0",
        "author":      "Think Tank",
        "builtin":     True,
        "enabled":     True,
    },
    {
        "id":          "topic_tagging",
        "name":        "Topic Tagging",
        "description": "Agents can tag drafts, mail, and projects with topics. Enables topic-based filtering across the platform.",
        "category":    "organisation",
        "version":     "1.0.0",
        "author":      "Think Tank",
        "builtin":     True,
        "enabled":     True,
    },
    {
        "id":          "slack_integration",
        "name":        "Slack Notifications",
        "description": "Post agent heartbeat summaries and founder-mail escalations to a Slack channel via webhook.",
        "category":    "integration",
        "version":     "0.9.0",
        "author":      "Community",
        "builtin":     False,
        "enabled":     False,
        "config_keys": ["slack_webhook_url", "slack_channel"],
        "install_hint": "Set slack_webhook_url in extension config below.",
    },
    {
        "id":          "email_digest",
        "name":        "Email Digest",
        "description": "Send a daily HTML digest of all agent activity to a configured email address using SMTP.",
        "category":    "integration",
        "version":     "0.8.0",
        "author":      "Community",
        "builtin":     False,
        "enabled":     False,
        "config_keys": ["smtp_host","smtp_port","smtp_user","smtp_pass","digest_to"],
        "install_hint": "Configure SMTP settings in extension config.",
    },
    {
        "id":          "calendar_sync",
        "name":        "Calendar Sync",
        "description": "Sync endeavor phases and deadlines to Google Calendar or an iCal feed.",
        "category":    "integration",
        "version":     "0.7.0",
        "author":      "Community",
        "builtin":     False,
        "enabled":     False,
        "config_keys": ["gcal_credentials_json"],
        "install_hint": "Upload Google service account credentials JSON.",
    },
    {
        "id":          "agent_personas",
        "name":        "Agent Persona Packs",
        "description": "Pre-built personality + tone + skill packs for common agent archetypes (strategist, lawyer, engineer, marketer).",
        "category":    "content",
        "version":     "1.0.0",
        "author":      "Think Tank",
        "builtin":     False,
        "enabled":     False,
        "install_hint": "Enable to add persona packs to the Model Importer.",
    },
    {
        "id":          "custom_tool",
        "name":        "Custom Tool Builder",
        "description": "Write a Python async function and expose it as a new agent tool, callable from chat and heartbeats.",
        "category":    "dev",
        "version":     "1.0.0",
        "author":      "Think Tank",
        "builtin":     False,
        "enabled":     False,
        "install_hint": "Drop a .py file in core/extensions/ with an async def run(params, agent) function.",
    },
]

async def _get_ext_settings() -> dict:
    try:
        from api.routes.settings import _load
        s = await _load()
        return json.loads(s.get("extensions_config", "{}"))
    except Exception:
        return {}

async def _save_ext_settings(data: dict):
    try:
        from api.routes.settings import _load, _save
        s = await _load()
        s["extensions_config"] = json.dumps(data)
        await _save(s)
    except Exception as e:
        logger.error(f"Failed to save extension settings: {e}")


@router.get("/api/extensions")
async def list_extensions():
    ext_cfg = await _get_ext_settings()
    result  = []
    for ext in BUILTIN_CATALOGUE:
        e = dict(ext)
        cfg_key = f"ext_{e['id']}"
        if cfg_key in ext_cfg:
            e["enabled"] = ext_cfg[cfg_key].get("enabled", e["enabled"])
            e["config"]  = ext_cfg[cfg_key].get("config", {})
        else:
            e["config"] = {}
        result.append(e)

    # Also scan core/extensions/ for custom .py files
    for p in EXTENSIONS_DIR.glob("*.py"):
        if p.stem.startswith("_"): continue
        eid = p.stem
        if not any(e["id"] == eid for e in result):
            enabled = ext_cfg.get(f"ext_{eid}", {}).get("enabled", False)
            result.append({
                "id": eid, "name": eid.replace("_"," ").title(),
                "description": f"Custom extension: {p.name}",
                "category": "custom", "version": "custom",
                "author": "local", "builtin": False,
                "enabled": enabled, "config": {},
                "source_file": str(p),
            })
    return result


@router.post("/api/extensions/{ext_id}/toggle")
async def toggle_extension(ext_id: str, enabled: bool = Body(..., embed=True)):
    ext_cfg = await _get_ext_settings()
    key     = f"ext_{ext_id}"
    if key not in ext_cfg:
        ext_cfg[key] = {}
    ext_cfg[key]["enabled"] = enabled
    await _save_ext_settings(ext_cfg)
    return {"ok": True, "ext_id": ext_id, "enabled": enabled}


@router.post("/api/extensions/{ext_id}/config")
async def save_extension_config(ext_id: str, request: Request):
    data    = await request.json()
    ext_cfg = await _get_ext_settings()
    key     = f"ext_{ext_id}"
    if key not in ext_cfg:
        ext_cfg[key] = {"enabled": False}
    ext_cfg[key]["config"] = data
    await _save_ext_settings(ext_cfg)
    return {"ok": True}


@router.post("/api/extensions/install-file")
async def install_extension_file(request: Request):
    """Accept a base64-encoded .py file and write to core/extensions/."""
    import base64
    data     = await request.json()
    filename = data.get("filename", "custom_ext.py")
    b64      = data.get("content_b64", "")
    if not filename.endswith(".py"):
        return {"error": "Only .py files allowed"}
    try:
        content = base64.b64decode(b64).decode("utf-8")
        (EXTENSIONS_DIR / filename).write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(EXTENSIONS_DIR / filename)}
    except Exception as e:
        return {"error": str(e)}
