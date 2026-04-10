"""core/ai_router.py — Routes tasks to Claude or Ollama. Supports multi-turn chat."""
from __future__ import annotations
import asyncio, logging, requests, re
from typing import Optional, List, Dict
import anthropic
from core.config import config

logger = logging.getLogger(__name__)

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


def _call_claude_sync(api_key: str, model: str, system_prompt: str,
                       messages: List[Dict]) -> tuple[str, str]:
    global _claude_client
    if _claude_client is None or _claude_client.api_key != api_key:
        _claude_client = anthropic.Anthropic(api_key=api_key)
    thinking_text = ""
    try:
        if any(m in model for m in ("claude-3-7", "claude-sonnet-4", "claude-opus-4")):
            response = _claude_client.messages.create(
                model=model, max_tokens=16000,
                thinking={"type": "enabled", "budget_tokens": 8000},
                system=system_prompt, messages=messages,
            )
            for block in response.content:
                if block.type == "thinking": thinking_text = block.thinking
                elif block.type == "text":   return block.text, thinking_text
            return "", thinking_text
        else:
            raise ValueError("no thinking")
    except Exception:
        response = _claude_client.messages.create(
            model=model, max_tokens=8096,
            system=system_prompt, messages=messages,
        )
        return response.content[0].text, ""


def _call_ollama_sync(base_url: str, model: str, timeout: int,
                       system_prompt: str, messages: List[Dict]) -> tuple[str, str]:
    # Convert messages to a single prompt for Ollama
    prompt_parts = []
    for m in messages:
        role = "USER" if m["role"] == "user" else "ASSISTANT"
        prompt_parts.append(f"{role}: {m['content']}")
    prompt = "\n\n".join(prompt_parts) + "\n\nASSISTANT:"

    resp = requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "system": system_prompt, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    resp.raise_for_status()
    raw = resp.json()["response"]
    thinking_text = ""
    think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
    if think_match:
        thinking_text = think_match.group(1).strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    return raw, thinking_text


async def route_chat(agent_id: str, system_prompt: str, messages: List[Dict]) -> dict:
    """Multi-turn chat route — uses agent's model_override if set."""
    s = await _get_settings()
    backend   = s.get("ai_backend", "claude")
    api_key   = s.get("claude_api_key", "")
    c_model   = s.get("claude_model", "claude-sonnet-4-20250514")
    o_url     = s.get("ollama_base_url", "http://localhost:11434")
    o_model   = s.get("ollama_model", "llama3")
    o_timeout = int(s.get("ollama_timeout", 120))

    # Check for per-agent model override
    try:
        import aiosqlite
        from core.database import DB_PATH
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT model_override FROM agents WHERE id=?", (agent_id,)
            ) as cur:
                row = await cur.fetchone()
            if row and row["model_override"]:
                override = row["model_override"].strip()
                if override.startswith("ollama:"):
                    o_model = override.replace("ollama:", "", 1)
                    backend = "ollama"
                elif override.startswith("claude"):
                    c_model = override
                    backend = "claude"
                else:
                    # Any other value (e.g. "llama3", "mistral") → treat as Ollama model
                    o_model = override
                    backend = "ollama"
    except Exception:
        pass

    if backend == "claude":
        text, thinking = await asyncio.to_thread(
            _call_claude_sync, api_key, c_model, system_prompt, messages
        )
        return {"text": text, "thinking": thinking, "backend": f"claude/{c_model}"}

    try:
        text, thinking = await asyncio.to_thread(
            _call_ollama_sync, o_url, o_model, o_timeout, system_prompt, messages
        )
        return {"text": text, "thinking": thinking, "backend": f"ollama/{o_model}"}
    except Exception as e:
        raise RuntimeError(
            f"Ollama unavailable ({e}). Switch to Claude in Settings."
        ) from e


async def route(task_type: str, system_prompt: str, user_prompt: str,
                context: Optional[str] = None, force_claude: bool = False,
                dept_id: Optional[str] = None) -> dict:
    """Single-turn route (existing API)."""
    messages = [{"role": "user", "content": (
        f"Context:\n{context}\n\n---\n\n{user_prompt}" if context else user_prompt
    )}]
    s = await _get_settings()
    backend       = s.get("ai_backend", "claude")
    api_key       = s.get("claude_api_key", "")
    c_model       = s.get("claude_model", "claude-sonnet-4-20250514")
    o_url         = s.get("ollama_base_url", "http://localhost:11434")
    o_model       = s.get("ollama_model", "llama3")
    o_timeout     = int(s.get("ollama_timeout", 120))
    custom_prompt = s.get("custom_prompt", "").strip()
    verbose       = s.get("verbose_thinking", "false").lower() == "true"

    if custom_prompt:
        system_prompt = system_prompt + "\n\n---\nADDITIONAL INSTRUCTIONS:\n" + custom_prompt

    use_claude = force_claude or backend == "claude"

    if use_claude:
        text, thinking = await asyncio.to_thread(
            _call_claude_sync, api_key, c_model, system_prompt, messages
        )
        if verbose and thinking:
            await _log_thinking(task_type, f"claude/{c_model}", thinking, dept_id)
        return {"text": text, "thinking": thinking,
                "backend": f"claude/{c_model}", "task_type": task_type}

    try:
        text, thinking = await asyncio.to_thread(
            _call_ollama_sync, o_url, o_model, o_timeout, system_prompt, messages
        )
        if verbose and thinking:
            await _log_thinking(task_type, f"ollama/{o_model}", thinking, dept_id)
        return {"text": text, "thinking": thinking,
                "backend": f"ollama/{o_model}", "task_type": task_type}
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        raise RuntimeError(
            f"Ollama is unavailable ({e}). Switch to Claude in Settings or start Ollama."
        ) from e


async def _log_thinking(task_type: str, backend: str, thinking: str,
                         dept_id: Optional[str]):
    try:
        from core.database import log_event
        await log_event(dept_id, "ai_thinking",
                        f"[{backend}] {task_type} — thinking captured",
                        {"thinking": thinking[:4000], "backend": backend})
    except Exception:
        pass


def classify_task(description: str) -> str:
    desc = description.lower()
    for t in ("strategy","comprehensive_report","full_analysis","research_brief","policy_document"):
        if t.replace("_"," ") in desc or t in desc: return t
    for t in ("memo","status_update","summary","recommendation"):
        if t.replace("_"," ") in desc or t in desc: return t
    return "analysis"
