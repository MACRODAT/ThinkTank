"""
core/prompt_parser.py — Resolves {{placeholder}} tokens in prompts before LLM call.

Supported tokens:
  {{time_of_day}}            — Morning / Afternoon / Evening / Night
  {{date}}                   — 2025-01-15 Wednesday
  {{current_points}}         — Department's current balance
  {{ledger}}                 — Last 10 transactions for department
  {{weather}}                — Weather for configured city (or "unknown")
  {{founder_mood}}           — Derived from recent founder activity
  {{other_department_points}}— All departments' balances
  {{loan_balance}}           — Outstanding loans for this department
"""
from __future__ import annotations
import re, json, logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r'\{\{(\w+)\}\}')


async def resolve_prompt(text: str, dept_id: str = "",
                          agent_id: str = "") -> str:
    """Replace all {{tokens}} in text. Unknown tokens are left unchanged."""
    if '{{' not in text:
        return text

    tokens = set(_TOKEN_RE.findall(text))
    resolved: dict[str, str] = {}

    for tok in tokens:
        try:
            resolved[tok] = await _resolve_token(tok, dept_id, agent_id)
        except Exception as e:
            logger.warning(f"Prompt token {{{{{tok}}}}} failed: {e}")
            resolved[tok] = f"[{tok}: unavailable]"

    def replacer(m):
        return resolved.get(m.group(1), m.group(0))

    return _TOKEN_RE.sub(replacer, text)


async def _resolve_token(tok: str, dept_id: str, agent_id: str) -> str:
    now = datetime.utcnow()

    if tok == "time_of_day":
        h = now.hour
        if   h < 6:  return "Night"
        elif h < 12: return "Morning"
        elif h < 17: return "Afternoon"
        elif h < 21: return "Evening"
        else:        return "Night"

    elif tok == "date":
        return now.strftime("%Y-%m-%d %A")

    elif tok == "current_points":
        if not dept_id:
            return "N/A"
        from core.economy import get_balance
        bal = await get_balance(dept_id.upper())
        return str(bal)

    elif tok == "ledger":
        if not dept_id:
            return "N/A"
        from core.economy import get_ledger
        rows = await get_ledger(dept_id.upper(), limit=10)
        if not rows:
            return "No transactions yet."
        lines = []
        for r in rows:
            sign = "+" if r["delta"] > 0 else ""
            lines.append(f"  {r['created_at'][:16]} | {r['event']}: {sign}{r['delta']} → {r['balance']} | {r['note']}")
        return "\n".join(lines)

    elif tok == "other_department_points":
        from core.economy import get_all_balances
        bals = await get_all_balances()
        lines = [f"  {d}: {b} pts" for d, b in sorted(bals.items())]
        return "\n".join(lines) if lines else "No data"

    elif tok == "weather":
        return await _fetch_weather()

    elif tok == "founder_mood":
        return await _founder_mood()

    elif tok == "loan_balance":
        if not dept_id:
            return "N/A"
        from core.economy import get_loan_summary
        return await get_loan_summary(dept_id.upper())

    return f"{{{{{tok}}}}}"  # unknown — leave as-is


async def _fetch_weather() -> str:
    """Open-Meteo — free, no key required. Uses stored city coords or defaults."""
    try:
        from api.routes.settings import _load
        s   = await _load()
        lat = s.get("weather_lat", "48.8566")   # Paris default
        lon = s.get("weather_lon", "2.3522")
        city= s.get("weather_city", "Paris")
        import httpx
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,weathercode",
                    "timezone": "UTC",
                }
            )
            r.raise_for_status()
        d   = r.json()
        cur = d.get("current", {})
        t   = cur.get("temperature_2m", "?")
        wc  = cur.get("weathercode", 0)
        desc = _wmo_to_desc(wc)
        return f"{city}: {t}°C, {desc}"
    except Exception as e:
        return f"Weather unavailable ({e})"


def _wmo_to_desc(code: int) -> str:
    if code == 0:              return "Clear sky"
    if code in (1, 2, 3):     return "Partly cloudy"
    if code in (45, 48):      return "Foggy"
    if code in range(51, 68): return "Drizzle/Rain"
    if code in range(71, 78): return "Snow"
    if code in range(80, 83): return "Rain showers"
    if code in range(95, 100):return "Thunderstorm"
    return "Unknown"


async def _founder_mood() -> str:
    """Derive mood from recent founder activity (last 24h)."""
    try:
        from core.database import DB_PATH
        import aiosqlite
        from datetime import timedelta
        since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            # Count replies in last 24h
            async with db.execute(
                "SELECT COUNT(*) FROM founder_mail WHERE replied_at > ? AND status='replied'",
                (since,)
            ) as cur:
                replies = (await cur.fetchone())[0]
            # Count approvals
            async with db.execute(
                "SELECT COUNT(*) FROM drafts WHERE reviewed_by='founder' AND reviewed_at > ? AND status='approved'",
                (since,)
            ) as cur:
                approvals = (await cur.fetchone())[0]
            # Count rejections
            async with db.execute(
                "SELECT COUNT(*) FROM drafts WHERE reviewed_by='founder' AND reviewed_at > ? AND status='rejected'",
                (since,)
            ) as cur:
                rejections = (await cur.fetchone())[0]
        if replies + approvals == 0:
            return "Quiet / unresponsive today"
        if rejections > approvals:
            return "Critical — has been rejecting drafts"
        if approvals > 3:
            return "Engaged and approving — good time to submit work"
        return "Active and responsive"
    except Exception:
        return "Unknown"
