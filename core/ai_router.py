"""
core/ai_router.py — Routes tasks to Claude (heavy) or Ollama (routine).
Falls back to Claude if Ollama is unavailable.

NOTE: The Anthropic SDK is synchronous. We run it in a thread pool via
asyncio.to_thread() so it doesn't block the event loop.
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


def _get_claude() -> anthropic.Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=config.ai.claude.api_key)
    return _claude_client


# ── Sync workers (run inside thread pool) ────────────────────────────────────

def _call_claude_sync(system_prompt: str, user_prompt: str) -> str:
    """Synchronous Claude call — executed via asyncio.to_thread."""
    client = _get_claude()
    response = client.messages.create(
        model=config.ai.claude.model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_ollama_sync(system_prompt: str, user_prompt: str) -> str:
    """Synchronous Ollama call — executed via asyncio.to_thread."""
    cfg = config.ai.ollama
    resp = requests.post(
        f"{cfg.base_url}/api/generate",
        json={
            "model": cfg.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
        },
        timeout=getattr(cfg, "timeout", 120),
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
    """
    Route a generation task to the appropriate AI backend.
    Returns {"text": ..., "backend": "claude"|"ollama", "task_type": ...}
    """
    full_prompt = (
        f"Context:\n{context}\n\n---\n\n{user_prompt}" if context else user_prompt
    )
    use_claude = force_claude or task_type in HEAVY

    if use_claude:
        text = await asyncio.to_thread(_call_claude_sync, system_prompt, full_prompt)
        return {"text": text, "backend": "claude", "task_type": task_type}

    # Routine → try Ollama first, fall back to Claude
    try:
        text = await asyncio.to_thread(_call_ollama_sync, system_prompt, full_prompt)
        return {"text": text, "backend": "ollama", "task_type": task_type}
    except Exception as e:
        logger.warning(f"Ollama unavailable ({e}), falling back to Claude.")
        text = await asyncio.to_thread(_call_claude_sync, system_prompt, full_prompt)
        return {"text": text, "backend": "claude (fallback)", "task_type": task_type}


def classify_task(description: str) -> str:
    """Guess task type from a free-text description."""
    desc = description.lower()
    for t in HEAVY:
        if t.replace("_", " ") in desc or t in desc:
            return t
    for t in ROUTINE:
        if t.replace("_", " ") in desc or t in desc:
            return t
    return "analysis"
