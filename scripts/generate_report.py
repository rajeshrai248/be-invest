"""Generate a broker fee comparison report from manual data."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from be_invest.pipeline import generate_report, load_fee_records
from be_invest.sources.manual import export_fee_records_to_csv


DEFAULT_DATA_DIR = Path("data")
DEFAULT_FEES_PATHS = [DEFAULT_DATA_DIR / "fees" / "manual_fees.csv"]
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
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write the aggregated comparison report (CSV).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fee_records = load_fee_records(args.fee_files)
    report_rows = generate_report(fee_records)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    export_fee_records_to_csv(fee_records, args.output)

    print(
        f"Wrote {len(report_rows)} rows to {args.output}. "
        "Populate manual_fees.csv with real data to enrich the report."
    )


if __name__ == "__main__":
    main()
