"""
api/main.py — FastAPI application entry point.
"""
from __future__ import annotations
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from core.database import init_db
from core.scheduler import setup_scheduler
from api.routes.departments import router as dept_router
from api.routes.mail        import router as mail_router
from api.routes.drafts      import router as draft_router
from api.routes.admin       import router as admin_router
from api.routes.settings    import router as settings_router
from api.routes.endeavors   import router as endeavors_router
from api.routes.agents      import router as agents_router
from api.routes.topics      import router as topics_router
from api.routes.extensions  import router as extensions_router
from api.routes.economy     import router as economy_router
from api.routes.files       import router as files_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏛️  Central Think Tank initializing...")
    await init_db()
    from core.endeavors_db import init_endeavors_db
    await init_endeavors_db()
    from core.agents_db import init_agents_db, seed_ceo_agents
    await init_agents_db()
    await seed_ceo_agents()
    from core.economy import init_economy_db
    await init_economy_db()
    logger.info("✓ Database + Economy ready")
    setup_scheduler()
    logger.info("✓ Scheduler started")
    from core.agent_scheduler import start_agent_scheduler
    start_agent_scheduler()
    logger.info("✓ Agent heartbeat scheduler started")
    logger.info("🟢 Think Tank online — http://localhost:8000")
    yield
    logger.info("🔴 Think Tank shutting down")


app = FastAPI(title="Central Think Tank", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dept_router)
app.include_router(mail_router)
app.include_router(draft_router)
app.include_router(admin_router)
app.include_router(settings_router)
app.include_router(endeavors_router)
app.include_router(agents_router)
app.include_router(topics_router)
app.include_router(extensions_router)
app.include_router(economy_router)
app.include_router(files_router)

import json, os
from fastapi.responses import JSONResponse

PRESETS_DIR = Path(__file__).parent.parent / "data" / "presets"
PRESETS_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/api/presets")
async def list_presets():
    return {"files": [f.stem for f in PRESETS_DIR.glob("*.json")]}

@app.get("/api/presets/{name}")
async def get_preset(name: str):
    p = PRESETS_DIR / f"{name}.json"
    if not p.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return json.loads(p.read_text(encoding="utf-8"))

@app.put("/api/presets/{name}")
async def save_preset(name: str, request: Request):
    data = await request.json()
    (PRESETS_DIR / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True}

import httpx

@app.get("/api/agents/random-face")
async def random_face():
    import base64, random as _random
    SOURCES = [
        f"https://i.pravatar.cc/256?img={_random.randint(1, 70)}",
        f"https://api.dicebear.com/7.x/personas/jpg?seed={_random.randint(1,9999)}&size=256",
        f"https://api.dicebear.com/7.x/adventurer-neutral/jpg?seed={_random.randint(1,9999)}&size=256",
    ]
    for url in _random.sample(SOURCES, len(SOURCES)):
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ThinkTank/1.0)"})
            if resp.status_code == 200 and len(resp.content) > 500:
                b64 = base64.b64encode(resp.content).decode()
                ct  = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                return {"data_url": f"data:{ct};base64,{b64}"}
        except Exception as e:
            logger.warning(f"Face source failed: {e}")
    return {"error": "All face sources failed"}

@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.post("/api/server/stop")
async def stop_server():
    import asyncio, os, signal
    async def _shutdown():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)
    asyncio.create_task(_shutdown())
    return {"ok": True, "message": "Server shutting down…"}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"detail": "Frontend not found"}, status_code=404)
