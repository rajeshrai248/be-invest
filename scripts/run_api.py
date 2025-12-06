"""Run the be-invest FastAPI server locally."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import uvicorn  # type: ignore


if __name__ == "__main__":
    # Explicitly watch the 'src' directory for changes.
    # host="0.0.0.0" allows connections from any network interface
    uvicorn.run(
        "be_invest.api.server:app",
        host="0.0.0.0",  # Changed from 127.0.0.1 to allow network access
        port=8000,
        reload=True,
        reload_dirs=[str(SRC_PATH)]
    )
