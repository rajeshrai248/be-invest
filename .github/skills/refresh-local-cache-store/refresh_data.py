"""
Refresh all cached data: PDFs, cost analysis, financial analysis.

This script orchestrates the complete data refresh workflow:
1. Refresh PDF files and cache
2. Run refresh-and-analyze to scrape and extract broker fees
3. Regenerate cost comparison tables
4. Regenerate financial analyses
"""
from __future__ import annotations

import sys
import time
import logging
import json
from pathlib import Path
from typing import Any

import requests

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Configuration
API_BASE_URL = "http://localhost:8000"
REQUEST_TIMEOUT = 600  # 10 minutes for long operations


def check_api_health() -> bool:
    """Check if API is running and healthy."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error(f"❌ API health check failed: {e}")
        return False


def refresh_pdfs() -> dict[str, Any]:
    """Step 1: Refresh all PDF files and their cache."""
    logger.info("=" * 80)
    logger.info("STEP 1: Refreshing PDF files and cache...")
    logger.info("=" * 80)
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/refresh-pdfs",
            timeout=REQUEST_TIMEOUT,
            json={}
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"✅ PDF refresh completed: {result}")
        return {"status": "success", "result": result}
    except requests.RequestException as e:
        logger.error(f"❌ PDF refresh failed: {e}")
        return {"status": "failed", "error": str(e)}


def refresh_and_analyze() -> dict[str, Any]:
    """Step 2: Run refresh-and-analyze to scrape broker data and extract fee rules."""
    logger.info("=" * 80)
    logger.info("STEP 2: Running refresh-and-analyze (scrape + analyze)...")
    logger.info("=" * 80)
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/refresh-and-analyze",
            timeout=REQUEST_TIMEOUT,
            json={"model": "claude-sonnet-4-20250514"}
        )
        response.raise_for_status()
        result = response.json()
        
        # Extract key metrics
        status = result.get("status", "unknown")
        brokers_analyzed = result.get("analysis_results", {}).get("brokers_analyzed", 0)
        duration = result.get("analysis_results", {}).get("duration_seconds", 0)
        
        logger.info(f"✅ Refresh-and-analyze completed:")
        logger.info(f"   Status: {status}")
        logger.info(f"   Brokers analyzed: {brokers_analyzed}")
        logger.info(f"   Duration: {duration:.2f}s")
        
        if result.get("fee_rules_changes"):
            logger.info(f"   Fee rules changes detected: {len(result['fee_rules_changes'])} changes")
        
        return {"status": "success", "result": result}
    except requests.RequestException as e:
        logger.error(f"❌ Refresh-and-analyze failed: {e}")
        return {"status": "failed", "error": str(e)}


def regenerate_cost_comparison() -> dict[str, Any]:
    """Step 3: Regenerate cost comparison tables."""
    logger.info("=" * 80)
    logger.info("STEP 3: Regenerating cost comparison tables...")
    logger.info("=" * 80)
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/cost-comparison-tables",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"✅ Cost comparison tables regenerated")
        logger.info(f"   Brokers in comparison: {len(result.get('brokers', []))}")
        logger.info(f"   Scenarios analyzed: {len(result.get('scenarios', {}))}")
        
        return {"status": "success", "result": result}
    except requests.RequestException as e:
        logger.error(f"❌ Cost comparison regeneration failed: {e}")
        return {"status": "failed", "error": str(e)}


def regenerate_financial_analysis() -> dict[str, Any]:
    """Step 4: Regenerate financial analyses."""
    logger.info("=" * 80)
    logger.info("STEP 4: Regenerating financial analyses...")
    logger.info("=" * 80)
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/financial-analysis",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"✅ Financial analyses regenerated")
        
        return {"status": "success", "result": result}
    except requests.RequestException as e:
        logger.error(f"❌ Financial analysis regeneration failed: {e}")
        return {"status": "failed", "error": str(e)}


def save_refresh_report(refresh_results: dict[str, Any]) -> None:
    """Save refresh results to a report file."""
    output_dir = PROJECT_ROOT / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / "refresh_report.json"
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(refresh_results, f, indent=2, ensure_ascii=False)
        logger.info(f"📄 Refresh report saved to: {report_path}")
    except Exception as e:
        logger.error(f"❌ Failed to save refresh report: {e}")


def main() -> int:
    """Run the complete refresh workflow."""
    logger.info("🚀 Starting data refresh workflow...")
    
    # Check API health
    if not check_api_health():
        logger.error("❌ API is not running. Please start the API server first:")
        logger.error("   python scripts/run_api.py")
        return 1
    
    logger.info("✅ API is running and healthy")
    
    start_time = time.time()
    refresh_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": {}
    }
    
    # Step 1: Refresh PDFs
    refresh_results["steps"]["refresh_pdfs"] = refresh_pdfs()
    if refresh_results["steps"]["refresh_pdfs"]["status"] != "success":
        logger.warning("⚠️  PDF refresh had issues, continuing...")
    
    # Step 2: Refresh and analyze
    refresh_results["steps"]["refresh_and_analyze"] = refresh_and_analyze()
    if refresh_results["steps"]["refresh_and_analyze"]["status"] != "success":
        logger.error("❌ Refresh-and-analyze failed, stopping workflow")
        save_refresh_report(refresh_results)
        return 1
    
    # Step 3: Regenerate cost comparison
    refresh_results["steps"]["cost_comparison"] = regenerate_cost_comparison()
    if refresh_results["steps"]["cost_comparison"]["status"] != "success":
        logger.warning("⚠️  Cost comparison regeneration had issues")
    
    # Step 4: Regenerate financial analysis
    refresh_results["steps"]["financial_analysis"] = regenerate_financial_analysis()
    if refresh_results["steps"]["financial_analysis"]["status"] != "success":
        logger.warning("⚠️  Financial analysis regeneration had issues")
    
    # Summary
    elapsed = time.time() - start_time
    refresh_results["duration_seconds"] = round(elapsed, 2)
    
    logger.info("=" * 80)
    logger.info("🎉 DATA REFRESH COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total duration: {elapsed:.2f}s")
    
    # Summary of results
    for step_name, step_result in refresh_results["steps"].items():
        status = "✅" if step_result["status"] == "success" else "❌"
        logger.info(f"{status} {step_name}: {step_result['status']}")
    
    # Save report
    save_refresh_report(refresh_results)
    
    # Determine exit code
    all_success = all(
        step["status"] == "success"
        for step in refresh_results["steps"].values()
    )
    
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
