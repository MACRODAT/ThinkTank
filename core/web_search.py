"""
core/web_search.py — Multi-provider web search for agents.
Free providers: duckduckgo, wikipedia, jina, bing_free, searx, youcom
Paid providers: brave, serpapi, tavily, exa
Strategy: try enabled providers in random order, fall back to free DDG/Wikipedia.
"""
from __future__ import annotations
import logging, json, random
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# ── Provider implementations ──────────────────────────────────────────────────

async def _search_brave(query: str, api_key: str, max_results: int) -> list[dict]:
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip",
               "X-Subscription-Token": api_key}
    params  = {"q": query, "count": max_results, "safesearch": "moderate", "text_decorations": False}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, headers=headers, params=params)
        r.raise_for_status()
    return [{"title": i.get("title",""), "url": i.get("url",""), "snippet": i.get("description","")}
            for i in r.json().get("web", {}).get("results", [])[:max_results]]


async def _search_serpapi(query: str, api_key: str, max_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://serpapi.com/search",
                        params={"q": query, "api_key": api_key, "num": max_results, "engine": "google"})
        r.raise_for_status()
    return [{"title": i.get("title",""), "url": i.get("link",""), "snippet": i.get("snippet","")}
            for i in r.json().get("organic_results", [])[:max_results]]


async def _search_tavily(query: str, api_key: str, max_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("https://api.tavily.com/search",
                         json={"api_key": api_key, "query": query, "max_results": max_results,
                               "search_depth": "basic", "include_answer": True})
        r.raise_for_status()
    data = r.json()
    results = []
    if data.get("answer"):
        results.append({"title": "Direct Answer", "url": "", "snippet": data["answer"]})
    results += [{"title": i.get("title",""), "url": i.get("url",""), "snippet": i.get("content","")[:400]}
                for i in data.get("results", [])[:max_results]]
    return results


async def _search_exa(query: str, api_key: str, max_results: int) -> list[dict]:
    """Exa.ai (formerly Metaphor) — semantic search, free tier 1000/month."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("https://api.exa.ai/search",
                         headers={"x-api-key": api_key, "Content-Type": "application/json"},
                         json={"query": query, "numResults": max_results,
                               "useAutoprompt": True, "type": "neural"})
        r.raise_for_status()
    data = r.json()
    return [{"title": i.get("title",""), "url": i.get("url",""),
             "snippet": i.get("text","")[:400] if i.get("text") else i.get("highlights",[""])[0][:400]}
            for i in data.get("results", [])[:max_results]]


async def _search_bing(query: str, api_key: str, max_results: int) -> list[dict]:
    """Bing Web Search API — free tier 3 calls/sec, 1000/month."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("https://api.bing.microsoft.com/v7.0/search",
                        headers={"Ocp-Apim-Subscription-Key": api_key},
                        params={"q": query, "count": max_results, "mkt": "en-US"})
        r.raise_for_status()
    data = r.json()
    return [{"title": i.get("name",""), "url": i.get("url",""), "snippet": i.get("snippet","")}
            for i in data.get("webPages", {}).get("value", [])[:max_results]]


async def _search_you(query: str, api_key: str, max_results: int) -> list[dict]:
    """You.com Search API — free tier 60/hour."""
    async with httpx.AsyncClient(timeout=12) as c:
        r = await c.get("https://api.ydc-index.io/search",
                        headers={"X-API-Key": api_key},
                        params={"query": query, "num_web_results": max_results})
        r.raise_for_status()
    data = r.json()
    results = []
    for hit in data.get("hits", [])[:max_results]:
        snippets = hit.get("snippets", [])
        results.append({
            "title":   hit.get("title",""),
            "url":     hit.get("url",""),
            "snippet": " ".join(snippets[:2])[:400] if snippets else "",
        })
    return results


async def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    """DDG instant-answer API — always free, limited but reliable."""
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        r = await c.get("https://api.duckduckgo.com/",
                        params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
        r.raise_for_status()
    data    = r.json()
    results = []
    if data.get("Abstract"):
        results.append({"title": data.get("Heading", query), "url": data.get("AbstractURL",""),
                         "snippet": data["Abstract"][:500]})
    for item in data.get("RelatedTopics", [])[:max_results]:
        if isinstance(item, dict) and item.get("Text"):
            results.append({"title": item.get("Text","")[:80], "url": item.get("FirstURL",""),
                             "snippet": item.get("Text","")[:300]})
    return results[:max_results]


async def _search_wikipedia(query: str, max_results: int) -> list[dict]:
    """Wikipedia search API — completely free, great for factual queries."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("https://en.wikipedia.org/w/api.php",
                        params={"action":"query","list":"search","srsearch":query,
                                "srlimit":max_results,"format":"json","utf8":1})
        r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("query",{}).get("search",[]):
        title   = item.get("title","")
        snippet = item.get("snippet","").replace('<span class="searchmatch">','').replace('</span>','')
        results.append({
            "title":   title,
            "url":     f"https://en.wikipedia.org/wiki/{title.replace(' ','_')}",
            "snippet": snippet[:400],
        })
    return results


async def _search_jina(query: str, max_results: int) -> list[dict]:
    """Jina AI s.jina.ai reader — free tier, converts URLs to clean text.
    Here we use their search endpoint which finds + summarizes pages."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        r = await c.get(f"https://s.jina.ai/{query}",
                        headers={"Accept": "application/json", "X-Return-Format": "markdown"})
        r.raise_for_status()
    # Jina returns markdown — extract first 3 sections as results
    content = r.text[:3000]
    lines   = [l.strip() for l in content.splitlines() if l.strip()]
    snippet = " ".join(lines[:20])[:500]
    return [{"title": f"Jina Search: {query}", "url": f"https://s.jina.ai/{query}", "snippet": snippet}]


async def _search_searx(query: str, instance_url: str, max_results: int) -> list[dict]:
    """SearXNG public instance — free, aggregates many engines."""
    url = instance_url.rstrip("/") + "/search"
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as c:
        r = await c.get(url, params={"q": query, "format": "json", "engines": "google,bing,ddg",
                                     "language": "en-US", "pageno": 1})
        r.raise_for_status()
    data = r.json()
    return [{"title": i.get("title",""), "url": i.get("url",""), "snippet": i.get("content","")[:400]}
            for i in data.get("results", [])[:max_results]]


# ── Provider registry ─────────────────────────────────────────────────────────

PROVIDERS = {
    # Free — no key needed
    "duckduckgo": {"label": "DuckDuckGo",    "free": True,  "needs_key": False},
    "wikipedia":  {"label": "Wikipedia",     "free": True,  "needs_key": False},
    "jina":       {"label": "Jina AI",       "free": True,  "needs_key": False},
    # Free tier with API key
    "bing":       {"label": "Bing",          "free": False, "needs_key": True, "limit": "1000/mo",  "signup": "https://azure.microsoft.com/en-us/free/"},
    "you":        {"label": "You.com",       "free": False, "needs_key": True, "limit": "60/hr",    "signup": "https://api.you.com"},
    "exa":        {"label": "Exa.ai",        "free": False, "needs_key": True, "limit": "1000/mo",  "signup": "https://exa.ai"},
    "searx":      {"label": "SearXNG",       "free": False, "needs_key": False, "limit": "varies",  "is_url": True},
    # Paid (best quality)
    "brave":      {"label": "Brave Search",  "free": False, "needs_key": True, "limit": "2000/mo free", "signup": "https://api.search.brave.com"},
    "tavily":     {"label": "Tavily AI",     "free": False, "needs_key": True, "limit": "1000/mo free", "signup": "https://tavily.com"},
    "serpapi":    {"label": "SerpAPI",       "free": False, "needs_key": True, "limit": "100/mo free",  "signup": "https://serpapi.com"},
}


async def _run_provider(provider: str, query: str, api_key: str, max_results: int,
                         searx_url: str = "") -> list[dict]:
    """Run a single provider. Returns [] on failure (caller handles fallback)."""
    try:
        if provider == "duckduckgo":
            return await _search_duckduckgo(query, max_results)
        elif provider == "wikipedia":
            return await _search_wikipedia(query, max_results)
        elif provider == "jina":
            return await _search_jina(query, max_results)
        elif provider == "brave" and api_key:
            return await _search_brave(query, api_key, max_results)
        elif provider == "serpapi" and api_key:
            return await _search_serpapi(query, api_key, max_results)
        elif provider == "tavily" and api_key:
            return await _search_tavily(query, api_key, max_results)
        elif provider == "exa" and api_key:
            return await _search_exa(query, api_key, max_results)
        elif provider == "bing" and api_key:
            return await _search_bing(query, api_key, max_results)
        elif provider == "you" and api_key:
            return await _search_you(query, api_key, max_results)
        elif provider == "searx":
            url = searx_url or "https://searx.be"
            return await _search_searx(query, url, max_results)
    except Exception as e:
        logger.warning(f"Provider {provider} failed: {e}")
    return []


# ── Public interface ──────────────────────────────────────────────────────────

async def web_search(query: str, settings: dict) -> str:
    if settings.get("web_search_enabled", "false") != "true":
        return "Web search is disabled. Enable it in Settings → Web Search."

    # Parse enabled providers list (JSON array of provider names)
    enabled_raw = settings.get("web_search_providers_enabled", "")
    if enabled_raw:
        try:    enabled = json.loads(enabled_raw)
        except: enabled = []
    else:
        # Legacy single-provider setting
        single = settings.get("web_search_provider", "brave")
        enabled = [single]

    api_key    = settings.get("web_search_api_key", "")
    api_keys   = {}
    try:    api_keys = json.loads(settings.get("web_search_api_keys", "{}"))
    except: pass
    api_keys.setdefault("brave",   api_key)
    api_keys.setdefault("serpapi", api_key)
    api_keys.setdefault("tavily",  api_key)
    api_keys.setdefault("exa",     api_key)
    api_keys.setdefault("bing",    settings.get("web_search_bing_key", ""))
    api_keys.setdefault("you",     settings.get("web_search_you_key", ""))

    max_r     = int(settings.get("web_search_max_results", "5"))
    searx_url = settings.get("web_search_searx_url", "https://searx.be")
    strategy  = settings.get("web_search_strategy", "random")  # "random" | "ordered"

    # Build provider order
    if strategy == "random":
        providers = enabled.copy()
        random.shuffle(providers)
    else:
        providers = enabled.copy()

    # Always add free fallbacks at end if not already included
    for fb in ("duckduckgo", "wikipedia"):
        if fb not in providers:
            providers.append(fb)

    results = []
    used_provider = "unknown"
    for p in providers:
        key = api_keys.get(p, "")
        r = await _run_provider(p, query, key, max_r, searx_url)
        if r:
            results = r
            used_provider = p
            break

    if not results:
        return f"All web search providers failed for query: `{query}`. Check Settings → Web Search."

    lines = [f"**Web Search** ({used_provider}) — `{query}`\n"]
    for i, r in enumerate(results, 1):
        title   = r.get("title","") or "Result"
        url     = r.get("url","")
        snippet = r.get("snippet","")
        lines.append(f"**{i}. {title}**")
        if url:     lines.append(f"   {url}")
        if snippet: lines.append(f"   {snippet[:350]}")
        lines.append("")
    return "\n".join(lines)


async def test_search(provider: str, api_key: str, searx_url: str = "") -> dict:
    settings = {
        "web_search_enabled": "true",
        "web_search_providers_enabled": json.dumps([provider]),
        "web_search_api_key": api_key,
        "web_search_bing_key": api_key,
        "web_search_you_key": api_key,
        "web_search_max_results": "3",
        "web_search_searx_url": searx_url or "https://searx.be",
        "web_search_strategy": "ordered",
    }
    try:
        result = await web_search("Central Think Tank AI agents", settings)
        ok = "failed" not in result.lower() and "disabled" not in result.lower()
        return {"ok": ok, "preview": result[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_providers_info() -> dict:
    """Return provider registry for the settings UI."""
    return PROVIDERS
