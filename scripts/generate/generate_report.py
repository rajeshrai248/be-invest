"""Generate a broker fee comparison report from manual and/or scraped data."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import logging

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.pipeline import generate_report, load_fee_records, load_brokers
from be_invest.sources.scrape import scrape_fee_records  # type: ignore
from be_invest.sources.manual import export_fee_records_to_csv


DEFAULT_DATA_DIR = Path("data")
DEFAULT_FEES_PATHS = [DEFAULT_DATA_DIR / "fees" / "manual_fees.csv"]
DEFAULT_BROKERS_PATH = DEFAULT_DATA_DIR / "brokers.yaml"
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_DIR / "output" / "comparison_report.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fee-files",
        nargs="*",
        type=Path,
        default=DEFAULT_FEES_PATHS,
        help="Paths to CSV files containing manually curated fee data.",
    )
    parser.add_argument(
        "--no-manual",
        action="store_true",
        help="Do not load manual CSV data; use only scraped sources.",
    )
    parser.add_argument(
        "--brokers",
        type=Path,
        default=DEFAULT_BROKERS_PATH,
        help="Path to YAML file with broker definitions and data-source URLs.",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help=(
            "Attempt to fetch fees from broker data sources marked allowed_to_scrape=true. "
            "Respects legal flags; use --force-scrape to override (not recommended)."
        ),
    )
    parser.add_argument(
        "--force-scrape",
        action="store_true",
        help="Scrape even if allowed_to_scrape is false. Use only if you have permission.",
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Use Playwright for fetching dynamic pages (requires playwright installed).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_DATA_DIR / "cache",
        help="Directory to store HTTP cache entries (default: data/cache).",
    )
    parser.add_argument(
        "--cache-ttl-seconds",
        type=int,
        default=0,
        help="Cache time-to-live in seconds (0 disables TTL and always refetches).",
    )
    parser.add_argument(
        "--strict-parse",
        action="store_true",
        help="Only keep parsed rows that include BOTH base_fee and variable_fee.",
    )
    parser.add_argument(
        "--dump-pdf-text",
        type=Path,
        help="If set, write extracted PDF text files to this directory for debugging.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level (default: INFO).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write the aggregated comparison report (CSV).",
    )
    # LLM options
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use OpenAI GPT-4o to extract rows when heuristics yield none.",
    )
    parser.add_argument(
        "--llm-model",
        default="claude-sonnet-4-20250514",
        help="LLM model to use (default: claude-sonnet-4-20250514).",
    )
    parser.add_argument(
        "--llm-api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable name that holds your OpenAI API key.",
    )
    parser.add_argument(
        "--llm-cache-dir",
        type=Path,
        default=DEFAULT_DATA_DIR / "llm_cache",
        help="Directory to cache LLM outputs keyed by content hash.",
    )
    parser.add_argument(
        "--llm-max-tokens",
        type=int,
        default=1500,
        help="Max tokens for LLM output.",
    )
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=0.0,
        help="LLM temperature (default 0.0 for deterministic extraction).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    level = logging.DEBUG if args.verbose else getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s:%(name)s:%(message)s")
    log = logging.getLogger("generate_report")
    # Load manual fee records (if any files are provided/present and not disabled)
    fee_records = [] if args.no_manual else load_fee_records(args.fee_files)
    log.debug("Loaded %d manual fee records from %s", len(fee_records), [str(p) for p in args.fee_files])

    # Optionally augment with scraped fee records
    scraped_count = 0
    if args.scrape:
        brokers = load_brokers([args.brokers]) if args.brokers.exists() else []
        log.debug("Loaded %d brokers from %s", len(brokers), args.brokers)
        scraped = scrape_fee_records(
            brokers,
            force=args.force_scrape,
            pdf_text_dump_dir=args.dump_pdf_text,
            cache_dir=args.cache_dir,
            cache_ttl_seconds=args.cache_ttl_seconds,
            use_playwright=args.use_playwright,
            strict_parse=args.strict_parse,
            use_llm=args.use_llm,
            llm_model=args.llm_model,
            llm_api_key_env=args.llm_api_key_env,
            llm_cache_dir=args.llm_cache_dir,
            llm_max_tokens=args.llm_max_tokens,
            llm_temperature=args.llm_temperature,
        )
        scraped_count = len(scraped)
        fee_records.extend(scraped)
        log.debug("Scraped %d records from broker sources", scraped_count)
    report_rows = generate_report(fee_records)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    export_fee_records_to_csv(fee_records, args.output)
    log.info("Exported %d total records to %s", len(fee_records), args.output)

    manual_count = 0 if args.no_manual else len(load_fee_records(args.fee_files))
    total = len(report_rows)
    if total == 0:
        msg = (
            f"Wrote 0 rows to {args.output}. "
            "No manual data found and no scraped data produced. "
            "Add entries to data/fees/manual_fees.csv or run with --scrape."
        )
    else:
        parts = [f"Wrote {total} rows to {args.output}."]
        if manual_count:
            parts.append(f"Manual: {manual_count}")
        if scraped_count:
            parts.append(f"Scraped: {scraped_count}")
        msg = " ".join(parts)
    print(msg)


if __name__ == "__main__":
    main()
