"""Download all broker PDFs from brokers.yaml and convert to text.

This script:
1. Reads all broker data sources from brokers.yaml
2. Downloads PDF files from configured URLs
3. Converts PDFs to text using pdfplumber
4. Saves extracted text to data/output/pdf_text/
5. Handles errors gracefully with detailed logging
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path
import logging
from typing import Optional
import yaml
import hashlib
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.config_loader import load_brokers_from_yaml

DEFAULT_DATA_DIR = Path("data")
DEFAULT_BROKERS_PATH = DEFAULT_DATA_DIR / "brokers.yaml"
DEFAULT_DOWNLOAD_DIR = DEFAULT_DATA_DIR / "pdfs"
DEFAULT_TEXT_DIR = DEFAULT_DATA_DIR / "output" / "pdf_text"
DEFAULT_METADATA_FILE = DEFAULT_DATA_DIR / "output" / "pdf_metadata.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if required packages are installed."""
    required = {
        "requests": "HTTP client for downloading PDFs",
        "pdfplumber": "PDF text extraction",
        "yaml": "YAML parsing",  # yaml is the module name for pyyaml package
    }

    missing = []
    for package, description in required.items():
        try:
            __import__(package)
        except ImportError:
            missing.append(f"  - {package}: {description}")

    if missing:
        logger.error("❌ Missing required packages:")
        for m in missing:
            logger.error(m)
        logger.error("\nInstall with:")
        logger.error("  pip install " + " ".join([p for p in required.keys() if any(p in m for m in missing)]))
        return False

    return True


def download_pdf(url: str, output_path: Path, timeout: int = 30) -> bool:
    """Download a PDF from URL and save to file.

    Args:
        url: URL of the PDF
        output_path: Where to save the PDF
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    try:
        import requests
    except ImportError:
        logger.error("❌ requests package not installed")
        return False

    try:
        logger.info(f"📥 Downloading: {url}")
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        # Create directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Download in chunks
        total_size = int(response.headers.get('content-length', 0))
        with open(output_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        logger.debug(f"  Progress: {percent:.1f}%")

        file_size = output_path.stat().st_size
        logger.info(f"✅ Downloaded: {output_path.name} ({file_size:,} bytes)")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to download {url}: {e}")
        return False


def extract_pdf_text(pdf_path: Path, output_path: Path) -> bool:
    """Convert PDF to text using pdfplumber.

    Args:
        pdf_path: Path to PDF file
        output_path: Where to save extracted text

    Returns:
        True if successful, False otherwise
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("❌ pdfplumber package not installed")
        return False

    try:
        logger.info(f"🔄 Converting PDF to text: {pdf_path.name}")

        text_content = []
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"   Pages: {total_pages}")

            for i, page in enumerate(pdf.pages, 1):
                # Extract text from page
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_content.append(f"--- PAGE {i} ---\n{page_text}\n")

                # Extract tables if available
                if hasattr(page, 'extract_tables'):
                    tables = page.extract_tables()
                    if tables:
                        text_content.append(f"\n--- TABLES ON PAGE {i} ---\n")
                        for table in tables:
                            for row in table:
                                text_content.append(" | ".join(str(cell or "") for cell in row))
                            text_content.append("")
                        text_content.append("\n")

        if not text_content:
            logger.warning(f"⚠️  No text extracted from {pdf_path.name}")
            return False

        # Save text
        output_path.parent.mkdir(parents=True, exist_ok=True)
        full_text = "\n".join(text_content)
        output_path.write_text(full_text, encoding="utf-8")

        char_count = len(full_text)
        logger.info(f"✅ Converted: {output_path.name} ({char_count:,} chars)")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to extract text from {pdf_path}: {e}")
        return False


def process_broker_pdfs(brokers_yaml_path: Path, download_dir: Path, text_dir: Path) -> dict:
    """Process all broker PDFs from brokers.yaml.

    Args:
        brokers_yaml_path: Path to brokers.yaml
        download_dir: Directory to download PDFs to
        text_dir: Directory to save extracted text

    Returns:
        Dictionary with processing results
    """
    brokers = load_brokers_from_yaml(brokers_yaml_path)
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_brokers": len(brokers),
        "brokers": {}
    }

    for broker in brokers:
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 Processing: {broker.name}")
        logger.info(f"{'='*80}")

        broker_result = {
            "name": broker.name,
            "website": broker.website,
            "data_sources": [],
            "success": False,
            "error": None
        }

        if not broker.data_sources:
            logger.warning(f"⚠️  No data sources for {broker.name}")
            broker_result["error"] = "No data sources defined"
            results["brokers"][broker.name] = broker_result
            continue

        for idx, source in enumerate(broker.data_sources, 1):
            if not source.url:
                logger.warning(f"⚠️  Data source {idx}: No URL")
                continue

            logger.info(f"\n📄 Source {idx}/{len(broker.data_sources)}: {source.description}")
            logger.info(f"   URL: {source.url}")
            logger.info(f"   Type: {source.type}")
            logger.info(f"   Allowed to scrape: {source.allowed_to_scrape}")

            # Create safe filenames
            url_hash = hashlib.md5(source.url.encode()).hexdigest()[:8]
            pdf_filename = f"{broker.name.lower().replace(' ', '_')}_{idx}_{url_hash}.pdf"
            text_filename = pdf_filename.replace(".pdf", ".txt")

            pdf_path = download_dir / pdf_filename
            text_path = text_dir / text_filename

            source_result = {
                "description": source.description,
                "url": source.url,
                "pdf_file": pdf_filename,
                "text_file": text_filename,
                "download_success": False,
                "conversion_success": False,
                "error": None
            }

            # Download PDF
            if not pdf_path.exists():
                if download_pdf(source.url, pdf_path):
                    source_result["download_success"] = True
                else:
                    source_result["error"] = "Download failed"
                    broker_result["data_sources"].append(source_result)
                    continue
            else:
                logger.info(f"✓ Already downloaded: {pdf_filename}")
                source_result["download_success"] = True

            # Convert to text
            if extract_pdf_text(pdf_path, text_path):
                source_result["conversion_success"] = True
                broker_result["success"] = True
            else:
                source_result["error"] = "Conversion failed"

            broker_result["data_sources"].append(source_result)

        results["brokers"][broker.name] = broker_result

    return results


def print_summary(results: dict):
    """Print processing summary."""
    logger.info("\n" + "="*80)
    logger.info("📋 PROCESSING SUMMARY")
    logger.info("="*80)

    successful = sum(1 for b in results["brokers"].values() if b["success"])

    logger.info(f"\nTotal brokers: {results['total_brokers']}")
    logger.info(f"Successfully processed: {successful}/{results['total_brokers']}")

    logger.info("\nBroker Details:")
    for broker_name, broker_data in results["brokers"].items():
        status = "✅" if broker_data["success"] else "❌"
        logger.info(f"\n{status} {broker_name}")
        if broker_data["error"]:
            logger.info(f"   Error: {broker_data['error']}")
        else:
            source_count = len([s for s in broker_data["data_sources"] if s["conversion_success"]])
            logger.info(f"   Sources processed: {source_count}/{len(broker_data['data_sources'])}")
            for source in broker_data["data_sources"]:
                if source["conversion_success"]:
                    logger.info(f"   ✓ {source['description']} → {source['text_file']}")
                elif source.get("error"):
                    logger.info(f"   ✗ {source['description']}: {source['error']}")


def main():
    parser = argparse.ArgumentParser(
        description="Download all broker PDFs from brokers.yaml and convert to text",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_broker_pdfs.py
  python download_broker_pdfs.py --pdf-dir data/pdfs --text-dir data/output/pdf_text
  python download_broker_pdfs.py --log-level DEBUG
  python download_broker_pdfs.py --save-metadata
        """
    )

    parser.add_argument(
        "--brokers",
        type=Path,
        default=DEFAULT_BROKERS_PATH,
        help="Path to brokers.yaml (default: data/brokers.yaml)",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_DOWNLOAD_DIR,
        help="Directory to download PDFs (default: data/pdfs)",
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=DEFAULT_TEXT_DIR,
        help="Directory to save extracted text (default: data/output/pdf_text)",
    )
    parser.add_argument(
        "--save-metadata",
        action="store_true",
        help="Save processing metadata to JSON",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("="*80)
    logger.info("🚀 BROKER PDF DOWNLOADER & CONVERTER")
    logger.info("="*80)

    # Check dependencies
    if not check_dependencies():
        return 1

    # Process PDFs
    results = process_broker_pdfs(args.brokers, args.pdf_dir, args.text_dir)

    # Print summary
    print_summary(results)

    # Save metadata
    if args.save_metadata:
        args.text_dir.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = args.text_dir.parent / "pdf_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"\n💾 Metadata saved: {metadata_path}")

    # Final status
    all_success = all(b["success"] for b in results["brokers"].values())
    if all_success:
        logger.info("\n✅ All brokers processed successfully!")
        return 0
    else:
        failed_count = sum(1 for b in results["brokers"].values() if not b["success"])
        logger.warning(f"\n⚠️  {failed_count} broker(s) had issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())

