#!/usr/bin/env python3
"""Convert existing Degiro PDF to text."""
from pathlib import Path
import hashlib
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define paths
pdf_path = Path("data/pdfs/degiro_tarievenoverzicht.pdf")
output_dir = Path("data/output/pdf_text")
output_dir.mkdir(parents=True, exist_ok=True)

if not pdf_path.exists():
    logger.error(f"❌ Degiro PDF not found: {pdf_path}")
    exit(1)

logger.info(f"📄 Converting: {pdf_path.name}")

try:
    import pdfplumber
except ImportError:
    logger.error("❌ pdfplumber not installed. Run: pip install pdfplumber")
    exit(1)

try:
    # Extract text from PDF
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for i, page in enumerate(pdf.pages, 1):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                logger.debug(f"  Page {i}: {len(page_text) if page_text else 0} chars")
            except Exception as e:
                logger.warning(f"  Page {i}: Failed to extract - {e}")
                continue

    if not text.strip():
        logger.error("❌ No text extracted from PDF")
        exit(1)

    logger.info(f"✅ Extracted {len(text):,} characters from {len(pdf.pages)} pages")

    # Generate consistent filename
    file_hash = hashlib.md5(pdf_path.read_bytes()).hexdigest()[:8]
    output_filename = f"degiro_1_{file_hash}.txt"
    output_path = output_dir / output_filename

    # Write text file
    output_path.write_text(text, encoding="utf-8")
    logger.info(f"✅ Saved: {output_filename}")
    logger.info(f"📊 Summary:")
    logger.info(f"   Input:  {pdf_path.name}")
    logger.info(f"   Output: {output_filename}")
    logger.info(f"   Size:   {len(text):,} characters")

except Exception as e:
    logger.error(f"❌ Conversion failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

logger.info("✅ Done!")

