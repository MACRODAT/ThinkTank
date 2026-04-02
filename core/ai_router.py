"""
core/ai_router.py — Routes tasks to Claude (heavy) or Ollama (routine).
Falls back to Claude if Ollama is unavailable.
"""
from __future__ import annotations
import anthropic
import requests
import logging
from typing import Optional
from core.config import config

logger = logging.getLogger(__name__)

HEAVY = {
    "strategy", "comprehensive_report", "full_analysis",
    "research_brief", "annual_plan", "policy_document",
    "strategic_memo", "cross_dept_coordination", "cancer_strategy",
    "long_term_plan", "framework", "roadmap"
}

ROUTINE = {
    "memo", "status_update", "summary", "mail_draft",
    "brief_note", "acknowledgment", "weekly_digest",
    "reminder", "quick_analysis", "response"
}

_claude_client: Optional[anthropic.Anthropic] = None


def _get_claude() -> anthropic.Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=config.ai.claude.api_key)
    return _claude_client


async def route(task_type: str, system_prompt: str, user_prompt: str,
                context: Optional[str] = None, force_claude: bool = False) -> dict:
    full_prompt = f"Context:\n{context}\n\n---\n\n{user_prompt}" if context else user_prompt
    use_claude = force_claude or task_type in HEAVY

    if use_claude:
        text = await _call_claude(system_prompt, full_prompt)
        return {"text": text, "backend": "claude", "task_type": task_type}

    try:
        text = _call_ollama(system_prompt, full_prompt)
        return {"text": text, "backend": "ollama", "task_type": task_type}
    except Exception as e:
        logger.warning(f"Ollama unavailable ({e}), falling back to Claude.")
        text = await _call_claude(system_prompt, full_prompt)
        return {"text": text, "backend": "claude (fallback)", "task_type": task_type}


async def _call_claude(system_prompt: str, user_prompt: str) -> str:
    client = _get_claude()
    response = client.messages.create(
        model=config.ai.claude.model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    cfg = config.ai.ollama
    resp = requests.post(
        f"{cfg.base_url}/api/generate",
        json={"model": cfg.model, "system": system_prompt,
              "prompt": user_prompt, "stream": False},
        timeout=getattr(cfg, "timeout", 120),
    )
    resp.raise_for_status()
    return resp.json()["response"]


def classify_task(description: str) -> str:
    desc = description.lower()
    for t in HEAVY:
        if t.replace("_", " ") in desc or t in desc:
            return t
    for t in ROUTINE:
        if t.replace("_", " ") in desc or t in desc:
            return t
    return "analysis"
