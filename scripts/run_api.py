"""Run the be-invest FastAPI server locally."""
from __future__ import annotations

import sys
import logging
import os
from pathlib import Path

# Set Playwright browsers path before importing anything else
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = r'C:\Users\rajes\ms-playwright'

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import uvicorn  # type: ignore

# Configure logging - warnings for most, debug for scraping
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Set be_invest modules to WARNING by default
logging.getLogger('be_invest').setLevel(logging.WARNING)
# Enable DEBUG for scraping-related modules
logging.getLogger('be_invest.fetchers').setLevel(logging.DEBUG)
logging.getLogger('be_invest.sources.scrape').setLevel(logging.DEBUG)
logging.getLogger('be_invest.sources.llm_extract').setLevel(logging.DEBUG)
# Keep uvicorn logs at WARNING
logging.getLogger('uvicorn').setLevel(logging.WARNING)


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
