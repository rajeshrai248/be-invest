"""Debug script to test fetching and text extraction for the Belfius PDF."""
from __future__ import annotations

import sys
from pathlib import Path
import logging

# Add src directory to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.config_loader import load_brokers_from_yaml
from be_invest.sources.scrape import _fetch_url
from be_invest.api.server import pdf_bytes_to_text  # Import the server's extraction logic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    """Finds the Belfius URL, fetches it, and attempts text extraction."""
    brokers_yaml_path = PROJECT_ROOT / "data" / "brokers.yaml"
    if not brokers_yaml_path.exists():
        logger.error("Could not find brokers.yaml at: %s", brokers_yaml_path)
        return

    logger.info("Loading brokers from: %s", brokers_yaml_path)
    brokers = load_brokers_from_yaml(brokers_yaml_path)

    belfius_broker = next((b for b in brokers if b.name.lower() == "belfius"), None)

    if not belfius_broker:
        logger.error("Belfius not found in brokers.yaml.")
        return

    if not belfius_broker.data_sources:
        logger.error("Belfius has no data sources defined in brokers.yaml.")
        return

    belfius_url = belfius_broker.data_sources[0].url
    logger.info("Found Belfius URL: %s", belfius_url)

    # --- Step 1: Fetch the URL ---
    logger.info("Attempting to fetch the URL...")
    data = None
    try:
        data = _fetch_url(belfius_url, timeout=20.0)
        if data:
            logger.info("✅ SUCCESS: Successfully fetched the Belfius PDF (%d bytes).", len(data))
        else:
            logger.error("❌ FAILURE: Fetching the URL returned no data.")
            return
    except Exception:
        logger.error("❌ EXCEPTION: An error occurred during fetching.", exc_info=True)
        return

    # --- Step 2: Attempt Text Extraction ---
    logger.info("Attempting to extract text from the downloaded PDF...")
    try:
        text = pdf_bytes_to_text(data)
        if text and text.strip():
            logger.info("✅ SUCCESS: Successfully extracted text.")
            logger.info("Extracted %d characters.", len(text))
            
            # Save the text to a debug file
            debug_output_path = PROJECT_ROOT / "data" / "output" / "pdf_text" / "debug_belfius_text.txt"
            debug_output_path.parent.mkdir(parents=True, exist_ok=True)
            debug_output_path.write_text(text, encoding="utf-8")
            logger.info("Saved extracted text for review to: %s", debug_output_path)

        else:
            logger.error("❌ FAILURE: Text extraction returned empty content. The PDF might be an image or have other issues.")
    except Exception:
        logger.error("❌ EXCEPTION: An error occurred during text extraction.", exc_info=True)


if __name__ == "__main__":
    main()
