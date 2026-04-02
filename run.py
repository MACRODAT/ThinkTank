"""
run.py — Entry point. Run with: python run.py
"""
import sys
from pathlib import Path

# Ensure the project root is on the path regardless of where the script is called from
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from core.config import config

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=getattr(config.server, "host", "0.0.0.0"),
        port=int(getattr(config.server, "port", 8000)),
        reload=bool(getattr(config.server, "debug", False)),
    )
