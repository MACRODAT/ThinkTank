"""
core/ai_router.py — Routes tasks to Claude or Ollama.
Reads active backend + credentials from DB settings at runtime.
Falls back to Claude if Ollama is unavailable.
"""
from __future__ import annotations
import asyncio
import logging
import requests
from typing import Optional

import anthropic
from core.config import config

logger = logging.getLogger(__name__)

HEAVY = {
    "strategy", "comprehensive_report", "full_analysis",
    "research_brief", "annual_plan", "policy_document",
    "strategic_memo", "cross_dept_coordination", "cancer_strategy",
    "long_term_plan", "framework", "roadmap",
}
ROUTINE = {
    "memo", "status_update", "summary", "mail_draft",
    "brief_note", "acknowledgment", "weekly_digest",
    "reminder", "quick_analysis", "response",
}

_claude_client: Optional[anthropic.Anthropic] = None


# ── Settings loader (lazy import avoids circular deps) ────────────────────────

async def _get_settings() -> dict:
    """Load live settings from DB; fall back to config.yaml values."""
    try:
        from api.routes.settings import _load
        return await _load()
    except Exception:
        return {
            "ai_backend":      "claude",
            "claude_api_key":  config.ai.claude.api_key,
            "claude_model":    config.ai.claude.model,
            "ollama_base_url": config.ai.ollama.base_url,
            "ollama_model":    config.ai.ollama.model,
            "ollama_timeout":  str(getattr(config.ai.ollama, "timeout", 120)),
        }


# ── Sync workers ──────────────────────────────────────────────────────────────

def _call_claude_sync(api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    global _claude_client
    if _claude_client is None or _claude_client.api_key != api_key:
        _claude_client = anthropic.Anthropic(api_key=api_key)
    response = _claude_client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_ollama_sync(base_url: str, model: str, timeout: int,
                      system_prompt: str, user_prompt: str) -> str:
    resp = requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "system": system_prompt, "prompt": user_prompt, "stream": False},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["response"]


# ── Public async API ──────────────────────────────────────────────────────────

async def route(
    task_type: str,
    system_prompt: str,
    user_prompt: str,
    context: Optional[str] = None,
    force_claude: bool = False,
) -> dict:
    s = await _get_settings()
    full_prompt = f"Context:\n{context}\n\n---\n\n{user_prompt}" if context else user_prompt

    backend   = s.get("ai_backend", "claude")
    api_key   = s.get("claude_api_key", "")
    c_model   = s.get("claude_model", "claude-sonnet-4-20250514")
    o_url     = s.get("ollama_base_url", "http://localhost:11434")
    o_model   = s.get("ollama_model", "llama3")
    o_timeout = int(s.get("ollama_timeout", 120))

    use_claude = force_claude or backend == "claude" or task_type in HEAVY

    if use_claude:
        text = await asyncio.to_thread(_call_claude_sync, api_key, c_model, system_prompt, full_prompt)
        return {"text": text, "backend": f"claude/{c_model}", "task_type": task_type}

    # Ollama path
    try:
        text = await asyncio.to_thread(_call_ollama_sync, o_url, o_model, o_timeout, system_prompt, full_prompt)
        return {"text": text, "backend": f"ollama/{o_model}", "task_type": task_type}
    except Exception as e:
        logger.warning(f"Ollama unavailable ({e}), falling back to Claude.")
        text = await asyncio.to_thread(_call_claude_sync, api_key, c_model, system_prompt, full_prompt)
        return {"text": text, "backend": f"claude/{c_model} (fallback)", "task_type": task_type}


def classify_task(description: str) -> str:
    desc = description.lower()
    for t in HEAVY:
        if t.replace("_", " ") in desc or t in desc:
            return t
    for t in ROUTINE:
        if t.replace("_", " ") in desc or t in desc:
            return t
    return "analysis"
