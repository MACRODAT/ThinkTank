"""
core/web_search.py — Multi-provider web search for agents.
Providers: brave (primary), serpapi, tavily, duckduckgo (free fallback).
"""
from __future__ import annotations
import logging, json, re
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# ── Provider implementations ──────────────────────────────────────────────────

async def _search_brave(query: str, api_key: str, max_results: int) -> list[dict]:
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip",
               "X-Subscription-Token": api_key}
    params  = {"q": query, "count": max_results, "safesearch": "moderate",
               "text_decorations": False, "search_lang": "en"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, headers=headers, params=params)
        r.raise_for_status()
    data    = r.json()
    results = []
    for item in data.get("web", {}).get("results", [])[:max_results]:
        results.append({
            "title":   item.get("title",""),
            "url":     item.get("url",""),
            "snippet": item.get("description",""),
        })
    return results


async def _search_serpapi(query: str, api_key: str, max_results: int) -> list[dict]:
    url    = "https://serpapi.com/search"
    params = {"q": query, "api_key": api_key, "num": max_results, "engine": "google"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
    data    = r.json()
    results = []
    for item in data.get("organic_results", [])[:max_results]:
        results.append({
            "title":   item.get("title",""),
            "url":     item.get("link",""),
            "snippet": item.get("snippet",""),
        })
    return results


async def _search_tavily(query: str, api_key: str, max_results: int) -> list[dict]:
    url     = "https://api.tavily.com/search"
    payload = {"api_key": api_key, "query": query, "max_results": max_results,
               "search_depth": "basic", "include_answer": True}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json=payload)
        r.raise_for_status()
    data    = r.json()
    results = []
    # Prepend Tavily's direct answer if present
    if data.get("answer"):
        results.append({"title": "Direct Answer", "url": "", "snippet": data["answer"]})
    for item in data.get("results", [])[:max_results]:
        results.append({
            "title":   item.get("title",""),
            "url":     item.get("url",""),
            "snippet": item.get("content","")[:400],
        })
    return results


async def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    """Free DDG instant-answer API — no JS, limited but always available."""
    url    = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
    data    = r.json()
    results = []
    if data.get("Abstract"):
        results.append({
            "title":   data.get("Heading", query),
            "url":     data.get("AbstractURL",""),
            "snippet": data["Abstract"][:500],
        })
    for item in data.get("RelatedTopics", [])[:max_results]:
        if isinstance(item, dict) and item.get("Text"):
            results.append({
                "title":   item.get("Text","")[:80],
                "url":     item.get("FirstURL",""),
                "snippet": item.get("Text","")[:300],
            })
    return results[:max_results]


# ── Public interface ──────────────────────────────────────────────────────────

async def web_search(query: str, settings: dict) -> str:
    """
    Run a web search using configured provider.
    Returns formatted markdown string with results.
    """
    if settings.get("web_search_enabled","false") != "true":
        return "Web search is disabled. Enable it in Settings → Web Search."

    provider   = settings.get("web_search_provider", "brave")
    api_key    = settings.get("web_search_api_key", "")
    max_r      = int(settings.get("web_search_max_results", "5"))

    results = []
    error   = None
    tried   = []

    # Try primary provider
    try:
        tried.append(provider)
        if provider == "brave" and api_key:
            results = await _search_brave(query, api_key, max_r)
        elif provider == "serpapi" and api_key:
            results = await _search_serpapi(query, api_key, max_r)
        elif provider == "tavily" and api_key:
            results = await _search_tavily(query, api_key, max_r)
        elif provider == "duckduckgo":
            results = await _search_duckduckgo(query, max_r)
        else:
            raise ValueError(f"Provider '{provider}' needs an API key or is unknown")
    except Exception as e:
        error = str(e)
        logger.warning(f"Web search primary ({provider}) failed: {e}")

    # Fallback to DuckDuckGo if primary failed and not already tried
    if not results and "duckduckgo" not in tried:
        try:
            results = await _search_duckduckgo(query, max_r)
        except Exception as e2:
            logger.warning(f"DDG fallback also failed: {e2}")

    if not results:
        return f"Web search failed (provider: {provider}, error: {error or 'no results'}). Check Settings → Web Search."

    # Format results
    lines = [f"**Web Search Results for:** `{query}`\n"]
    for i, r in enumerate(results, 1):
        title   = r.get("title","") or "Result"
        url     = r.get("url","")
        snippet = r.get("snippet","")
        lines.append(f"**{i}. {title}**")
        if url:
            lines.append(f"   🔗 {url}")
        if snippet:
            lines.append(f"   {snippet[:350]}")
        lines.append("")
    return "\n".join(lines)


async def test_search(provider: str, api_key: str) -> dict:
    """Test connectivity for the settings page."""
    settings = {
        "web_search_enabled": "true",
        "web_search_provider": provider,
        "web_search_api_key": api_key,
        "web_search_max_results": "3",
    }
    try:
        result = await web_search("Central Think Tank AI agents", settings)
        ok = "failed" not in result.lower() and "disabled" not in result.lower()
        return {"ok": ok, "preview": result[:400]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
