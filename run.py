"""
run.py — Entry point. Run with: python run.py
"""
import uvicorn
from core.config import config

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=getattr(config.server, "host", "0.0.0.0"),
        port=int(getattr(config.server, "port", 8000)),
        reload=getattr(config.server, "debug", False),
    )
