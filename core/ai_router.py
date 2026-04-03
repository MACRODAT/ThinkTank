"""
core/ai_router.py — Routes tasks to Claude or Ollama.
Backend is determined SOLELY by the user's saved setting.
HEAVY/ROUTINE classification only affects Claude-side routing when Claude is active.
When Ollama is selected it handles ALL tasks (including "heavy" ones).
"""
from __future__ import annotations
import asyncio
import logging
import requests
from typing import Optional

import anthropic
from core.config import config

logger = logging.getLogger(__name__)

# Task labels (informational only — no longer force Claude)
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


async def _get_settings() -> dict:
    try:
        from api.routes.settings import _load
        return await _load()
    except Exception:
        return {
            "ai_backend":        "claude",
            "claude_api_key":    config.ai.claude.api_key,
            "claude_model":      config.ai.claude.model,
            "ollama_base_url":   config.ai.ollama.base_url,
            "ollama_model":      config.ai.ollama.model,
            "ollama_timeout":    str(getattr(config.ai.ollama, "timeout", 120)),
            "custom_prompt":     "",
            "verbose_thinking":  "false",
        }


def _call_claude_sync(api_key: str, model: str,
                      system_prompt: str, user_prompt: str) -> tuple[str, str]:
    """Returns (answer_text, thinking_text)."""
    global _claude_client
    if _claude_client is None or _claude_client.api_key != api_key:
        _claude_client = anthropic.Anthropic(api_key=api_key)

    # Try extended thinking for supported models, fall back gracefully
    thinking_text = ""
    try:
        if "claude-3-7" in model or "claude-sonnet-4" in model or "claude-opus-4" in model:
            response = _claude_client.messages.create(
                model=model,
                max_tokens=16000,
                thinking={"type": "enabled", "budget_tokens": 8000},
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            for block in response.content:
                if block.type == "thinking":
                    thinking_text = block.thinking
                elif block.type == "text":
                    return block.text, thinking_text
            return "", thinking_text
        else:
            raise ValueError("model does not support thinking")
    except Exception:
        # Fallback: standard call without thinking
        response = _claude_client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text, ""


def _call_ollama_sync(base_url: str, model: str, timeout: int,
                      system_prompt: str, user_prompt: str) -> tuple[str, str]:
    """Returns (answer_text, thinking_text). Extracts <think> tags if present."""
    resp = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    raw = resp.json()["response"]

    # Extract <think>…</think> if model emits reasoning (e.g. deepseek-r1, qwq)
    thinking_text = ""
    import re
    think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
    if think_match:
        thinking_text = think_match.group(1).strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    return raw, thinking_text


async def _log_thinking(task_type: str, backend: str,
                        thinking: str, dept_id: Optional[str]):
    """Persist thinking to audit log when verbose mode is on."""
    if not thinking:
        return
    try:
        from core.database import log_event
        await log_event(dept_id, "ai_thinking",
                        f"[{backend}] {task_type} — thinking captured",
                        {"thinking": thinking[:4000], "backend": backend})
    except Exception:
        pass


async def route(
    task_type: str,
    system_prompt: str,
    user_prompt: str,
    context: Optional[str] = None,
    force_claude: bool = False,
    dept_id: Optional[str] = None,
) -> dict:
    s = await _get_settings()
    full_prompt = (
        f"Context:\n{context}\n\n---\n\n{user_prompt}" if context else user_prompt
    )

    backend        = s.get("ai_backend", "claude")
    api_key        = s.get("claude_api_key", "")
    c_model        = s.get("claude_model", "claude-sonnet-4-20250514")
    o_url          = s.get("ollama_base_url", "http://localhost:11434")
    o_model        = s.get("ollama_model", "llama3")
    o_timeout      = int(s.get("ollama_timeout", 120))
    custom_prompt  = s.get("custom_prompt", "").strip()
    verbose        = s.get("verbose_thinking", "false").lower() == "true"

    # Append user's custom prompt addition if set
    if custom_prompt:
        system_prompt = system_prompt + "\n\n---\nADDITIONAL INSTRUCTIONS:\n" + custom_prompt

    # Backend decision: force_claude only overrides when explicitly requested by code,
    # NOT based on task type. User's setting always wins otherwise.
    use_claude = force_claude or backend == "claude"

    if use_claude:
        text, thinking = await asyncio.to_thread(
            _call_claude_sync, api_key, c_model, system_prompt, full_prompt
        )
        if verbose:
            await _log_thinking(task_type, f"claude/{c_model}", thinking, dept_id)
        return {
            "text": text,
            "thinking": thinking,
            "backend": f"claude/{c_model}",
            "task_type": task_type,
        }

    # Ollama path — no fallback to Claude (user explicitly chose offline mode)
    try:
        text, thinking = await asyncio.to_thread(
            _call_ollama_sync, o_url, o_model, o_timeout, system_prompt, full_prompt
        )
        if verbose:
            await _log_thinking(task_type, f"ollama/{o_model}", thinking, dept_id)
        return {
            "text": text,
            "thinking": thinking,
            "backend": f"ollama/{o_model}",
            "task_type": task_type,
        }
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        raise RuntimeError(
            f"Ollama is unavailable ({e}). "
            "Switch to Claude in Settings or start your Ollama instance."
        ) from e


def classify_task(description: str) -> str:
    desc = description.lower()
    for t in HEAVY:
        if t.replace("_", " ") in desc or t in desc:
            return t
    for t in ROUTINE:
        if t.replace("_", " ") in desc or t in desc:
            return t
    return "analysis"
