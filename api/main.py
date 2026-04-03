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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏛️  Central Think Tank initializing...")
    await init_db()
    logger.info("✓ Database ready")
    setup_scheduler()
    logger.info("✓ Scheduler started")
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

# API routers (must be registered before the catch-all)
app.include_router(dept_router)
app.include_router(mail_router)
app.include_router(draft_router)
app.include_router(admin_router)


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve index.html for all non-API frontend routes."""
    # Don't intercept API calls that somehow missed routing
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"detail": "Frontend not found"}, status_code=404)
