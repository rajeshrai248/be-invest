"""Run the be-invest FastAPI server locally."""
from __future__ import annotations

import sys
import logging
import os
import json
from pathlib import Path

# Set UTF-8 encoding for console output (supports emojis on Windows)
if sys.stdout.encoding and 'utf' not in sys.stdout.encoding.lower():
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Set Playwright browsers path before importing anything else
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = r'C:\Users\rajes\ms-playwright'

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import uvicorn  # type: ignore

# Create logs directory
log_dir = PROJECT_ROOT / "logs"
log_dir.mkdir(exist_ok=True)

# Load and update logging config with absolute paths
logging_config_path = Path(__file__).parent / "logging_config.json"

with open(logging_config_path, 'r') as f:
    log_config = json.load(f)

# Update file paths to absolute paths
log_config['handlers']['file']['filename'] = str(log_dir / "api.log")
log_config['handlers']['access_file']['filename'] = str(log_dir / "uvicorn_access.log")


if __name__ == "__main__":
    # Explicitly watch the 'src' directory for changes.
    # host="0.0.0.0" allows connections from any network interface
    uvicorn.run(
        "be_invest.api.server:app",
        host="0.0.0.0",  # Changed from 127.0.0.1 to allow network access
        port=8000,
        reload=True,
        reload_dirs=[str(SRC_PATH)],
        access_log=True,  # Enable access logging
        log_config=log_config,  # Use our updated logging config with absolute paths
    )
