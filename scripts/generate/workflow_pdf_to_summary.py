"""Unified workflow to download PDFs, extract text, and generate exhaustive summary.

This is the main orchestration script that:
1. Downloads all broker PDFs from brokers.yaml
2. Converts PDFs to text
3. Generates exhaustive cost and charges summary
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent


def run_script(script_name: str, args: list[str], description: str) -> int:
    """Run a Python script as a subprocess.

    Args:
        script_name: Name of the script in scripts/ directory
        args: Command line arguments
        description: Description of what the script does

    Returns:
        Exit code
    """
    script_path = SCRIPTS_DIR / script_name

    logger.info("\n" + "="*80)
    logger.info(f"▶️  STEP: {description}")
    logger.info("="*80)

    cmd = [sys.executable, str(script_path)] + args
    logger.info(f"Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        logger.error(f"❌ Failed to run {script_name}: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Complete workflow: Download broker PDFs → Extract text → Generate exhaustive summary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python workflow_pdf_to_summary.py
  python workflow_pdf_to_summary.py --skip-download
  python workflow_pdf_to_summary.py --log-level DEBUG
  python workflow_pdf_to_summary.py --pdf-dir data/pdfs --text-dir data/output/pdf_text
        """
    )

    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip PDF download step (use if already downloaded)",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip summary generation step (only extract text)",
    )
    parser.add_argument(
        "--brokers",
        type=Path,
        default=Path("data/brokers.yaml"),
        help="Path to brokers.yaml (default: data/brokers.yaml)",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=Path("data/pdfs"),
        help="Directory for downloaded PDFs (default: data/pdfs)",
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=Path("data/output/pdf_text"),
        help="Directory for extracted text (default: data/output/pdf_text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/exhaustive_cost_charges_summary.md"),
        help="Output file for summary",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="OpenAI model to use (default: gpt-4o)",
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
    logger.info("🚀 COMPLETE WORKFLOW: PDF DOWNLOAD → TEXT EXTRACTION → EXHAUSTIVE SUMMARY")
    logger.info("="*80)

    # Step 1: Download PDFs
    if not args.skip_download:
        common_args = [
            "--brokers", str(args.brokers),
            "--pdf-dir", str(args.pdf_dir),
            "--text-dir", str(args.text_dir),
            "--log-level", args.log_level,
            "--save-metadata",
        ]

        exit_code = run_script(
            "download_broker_pdfs.py",
            common_args,
            "Download all broker PDFs from URLs in brokers.yaml"
        )

        if exit_code != 0:
            logger.error("❌ PDF download failed")
            return 1
    else:
        logger.info("⏭️  Skipping PDF download step")

    # Step 2: Generate exhaustive summary
    if not args.skip_summary:
        summary_args = [
            "--brokers", str(args.brokers),
            "--pdf-text-dir", str(args.text_dir),
            "--output", str(args.output),
            "--model", args.model,
            "--log-level", args.log_level,
        ]

        exit_code = run_script(
            "generate_exhaustive_summary.py",
            summary_args,
            "Generate exhaustive cost and charges summary"
        )

        if exit_code != 0:
            logger.error("❌ Summary generation failed")
            return 1
    else:
        logger.info("⏭️  Skipping summary generation step")

    # Final status
    logger.info("\n" + "="*80)
    logger.info("✅ COMPLETE WORKFLOW FINISHED SUCCESSFULLY!")
    logger.info("="*80)
    logger.info(f"\n📄 Output files:")
    logger.info(f"  - Extracted texts: {args.text_dir}/")
    logger.info(f"  - Summary: {args.output}")
    logger.info(f"  - Analyses JSON: {args.output.parent / 'broker_cost_analyses.json'}")
    logger.info(f"  - Metadata: {args.text_dir.parent / 'pdf_metadata.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

