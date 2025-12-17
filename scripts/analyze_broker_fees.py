"""Analysis and validation script for broker cost comparison.

This script provides the analysis requested by Rudolf:
1. Validate data quality against expected values
2. Identify fee structure types (tiered, flat, percentage)
3. Identify custody fee presence
4. Find cheapest broker by transaction size
5. Calculate investor scenario costs (A and B)
"""
from __future__ import annotations

import csv
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.be_invest.models import FeeRecord
from tests.test_data_quality_validation import (
    EXPECTED_BROKER_FEES,
    EXPECTED_CUSTODY_FEES,
    INVESTOR_SCENARIOS,
    calculate_total_cost,
    calculate_investor_scenario_cost,
    validate_fee_structure_type
)


@dataclass
class BrokerAnalysis:
    """Analysis results for a broker."""
    broker: str
    etf_fee_structure: str
    stock_fee_structure: str
    has_custody_fee: bool
    custody_fee_details: str
    etf_cost_250: float
    etf_cost_500: float
    etf_cost_1000: float
    etf_cost_5000: float
    stock_cost_250: float
    stock_cost_500: float
    stock_cost_1000: float
    stock_cost_5000: float
    investor_a_etf_cost: float
    investor_a_stock_cost: float
    investor_b_etf_cost: float
    investor_b_stock_cost: float
    data_quality_issues: List[str]


def analyze_broker_fees(fee_records: List[FeeRecord]) -> Dict[str, BrokerAnalysis]:
    """Analyze fee records and generate comprehensive broker analysis."""

    broker_analyses = {}

    # Group records by broker
    brokers = {}
    for record in fee_records:
        if record.broker not in brokers:
            brokers[record.broker] = {"ETFs": [], "Equities": []}

        if record.instrument_type in brokers[record.broker]:
            brokers[record.broker][record.instrument_type].append(record)

    for broker_name, instrument_records in brokers.items():
        etf_records = instrument_records.get("ETFs", [])
        stock_records = instrument_records.get("Equities", [])

        # Get primary records (first one for each instrument type)
        primary_etf = etf_records[0] if etf_records else None
        primary_stock = stock_records[0] if stock_records else None

        # Analyze fee structures
        etf_structure = validate_fee_structure_type(primary_etf) if primary_etf else "unknown"
        stock_structure = validate_fee_structure_type(primary_stock) if primary_stock else "unknown"

        # Get custody fee info
        custody_info = EXPECTED_CUSTODY_FEES.get(broker_name, {})
        has_custody = custody_info.get("has_custody_fee", False)
        custody_details = custody_info.get("amount", "") if has_custody else "None"

        # Calculate costs for different trade sizes
        trade_sizes = [250, 500, 1000, 5000]

        etf_costs = []
        stock_costs = []

        for size in trade_sizes:
            etf_cost = calculate_total_cost(primary_etf, size) if primary_etf else 0.0
            stock_cost = calculate_total_cost(primary_stock, size) if primary_stock else 0.0
            etf_costs.append(etf_cost)
            stock_costs.append(stock_cost)

        # Calculate investor scenarios
        investor_a = INVESTOR_SCENARIOS["A"]
        investor_b = INVESTOR_SCENARIOS["B"]

        etf_scenario_a = calculate_investor_scenario_cost(
            primary_etf, investor_a, custody_info
        ) if primary_etf else {"total_cost": 0.0}

        etf_scenario_b = calculate_investor_scenario_cost(
            primary_etf, investor_b, custody_info
        ) if primary_etf else {"total_cost": 0.0}

        stock_scenario_a = calculate_investor_scenario_cost(
            primary_stock, investor_a, custody_info
        ) if primary_stock else {"total_cost": 0.0}

        stock_scenario_b = calculate_investor_scenario_cost(
            primary_stock, investor_b, custody_info
        ) if primary_stock else {"total_cost": 0.0}

        # Data quality validation
        issues = validate_broker_data_quality(broker_name, primary_etf, primary_stock)

        analysis = BrokerAnalysis(
            broker=broker_name,
            etf_fee_structure=etf_structure,
            stock_fee_structure=stock_structure,
            has_custody_fee=has_custody,
            custody_fee_details=custody_details,
            etf_cost_250=etf_costs[0],
            etf_cost_500=etf_costs[1],
            etf_cost_1000=etf_costs[2],
            etf_cost_5000=etf_costs[3],
            stock_cost_250=stock_costs[0],
            stock_cost_500=stock_costs[1],
            stock_cost_1000=stock_costs[2],
            stock_cost_5000=stock_costs[3],
            investor_a_etf_cost=etf_scenario_a["total_cost"],
            investor_a_stock_cost=stock_scenario_a["total_cost"],
            investor_b_etf_cost=etf_scenario_b["total_cost"],
            investor_b_stock_cost=stock_scenario_b["total_cost"],
            data_quality_issues=issues
        )

        broker_analyses[broker_name] = analysis

    return broker_analyses


def validate_broker_data_quality(
    broker: str,
    etf_record: Optional[FeeRecord],
    stock_record: Optional[FeeRecord]
) -> List[str]:
    """Validate broker data against Rudolf's expected values."""

    issues = []

    # Check ETF expectations
    if broker in [e.broker for e in EXPECTED_BROKER_FEES["ETF"]]:
        expected_etf = next((e for e in EXPECTED_BROKER_FEES["ETF"] if e.broker == broker), None)

        if expected_etf and etf_record:
            if expected_etf.trade_size_eur and expected_etf.expected_total_cost_eur:
                actual_cost = calculate_total_cost(etf_record, expected_etf.trade_size_eur)
                if abs(actual_cost - expected_etf.expected_total_cost_eur) > 0.01:
                    issues.append(
                        f"ETF cost mismatch: expected {expected_etf.expected_total_cost_eur}€ "
                        f"for {expected_etf.trade_size_eur}€ trade, got {actual_cost}€"
                    )

    # Check stock expectations
    if broker in [e.broker for e in EXPECTED_BROKER_FEES["Stocks"]]:
        expected_stock = next((e for e in EXPECTED_BROKER_FEES["Stocks"] if e.broker == broker), None)

        if expected_stock and stock_record:
            if expected_stock.trade_size_eur and expected_stock.expected_total_cost_eur:
                actual_cost = calculate_total_cost(stock_record, expected_stock.trade_size_eur)
                if abs(actual_cost - expected_stock.expected_total_cost_eur) > 0.01:
                    issues.append(
                        f"Stock cost mismatch: expected {expected_stock.expected_total_cost_eur}€ "
                        f"for {expected_stock.trade_size_eur}€ trade, got {actual_cost}€"
                    )

    # Specific broker checks based on Rudolf's feedback
    if broker == "Bolero":
        if etf_record and calculate_total_cost(etf_record, 5000) != 15.0:
            issues.append("Bolero ETF 5k trade should cost €15, not €10")
        if stock_record and calculate_total_cost(stock_record, 5000) != 15.0:
            issues.append("Bolero stock 5k trade should cost €15, not €10")

    elif broker in ["Degiro Belgium", "Degiro"]:
        # Check for missing handling fee
        if etf_record and (etf_record.base_fee or 0) < 1.0:
            issues.append("Degiro missing €1 handling fee for ETFs")
        if stock_record and (stock_record.base_fee or 0) < 1.0:
            issues.append("Degiro missing €1 handling fee for stocks")

    elif broker == "Rebel":
        # Check for Brussels vs Paris/Amsterdam confusion
        if stock_record and stock_record.notes:
            if "Paris" in stock_record.notes or "Amsterdam" in stock_record.notes:
                issues.append("Rebel using Paris/Amsterdam data instead of Brussels")

        # Check specific fee for stocks up to 2.5k
        if stock_record and calculate_total_cost(stock_record, 2500) != 3.0:
            issues.append("Rebel stock trades up to €2.5k should cost €3")

    return issues


def find_cheapest_brokers(analyses: Dict[str, BrokerAnalysis]) -> Dict[str, Dict]:
    """Find cheapest broker for each trade size and instrument type."""

    trade_sizes = [250, 500, 1000, 5000]
    results = {
        "ETF": {},
        "Stocks": {}
    }

    for size in trade_sizes:
        # ETF cheapest
        etf_costs = {
            broker: getattr(analysis, f"etf_cost_{size}")
            for broker, analysis in analyses.items()
            if getattr(analysis, f"etf_cost_{size}") > 0
        }

        if etf_costs:
            cheapest_etf_broker = min(etf_costs.keys(), key=lambda b: etf_costs[b])
            results["ETF"][size] = {
                "broker": cheapest_etf_broker,
                "cost": etf_costs[cheapest_etf_broker]
            }

        # Stock cheapest
        stock_costs = {
            broker: getattr(analysis, f"stock_cost_{size}")
            for broker, analysis in analyses.items()
            if getattr(analysis, f"stock_cost_{size}") > 0
        }

        if stock_costs:
            cheapest_stock_broker = min(stock_costs.keys(), key=lambda b: stock_costs[b])
            results["Stocks"][size] = {
                "broker": cheapest_stock_broker,
                "cost": stock_costs[cheapest_stock_broker]
            }

    return results


def find_cheapest_for_scenarios(analyses: Dict[str, BrokerAnalysis]) -> Dict[str, Dict]:
    """Find cheapest broker for each investor scenario."""

    results = {
        "Investor A (€169/month for 5 years)": {
            "ETF": {"broker": None, "cost": float('inf')},
            "Stocks": {"broker": None, "cost": float('inf')}
        },
        "Investor B (€10k lump + €500/month for 5 years)": {
            "ETF": {"broker": None, "cost": float('inf')},
            "Stocks": {"broker": None, "cost": float('inf')}
        }
    }

    for broker, analysis in analyses.items():
        # Investor A
        if analysis.investor_a_etf_cost > 0 and analysis.investor_a_etf_cost < results["Investor A (€169/month for 5 years)"]["ETF"]["cost"]:
            results["Investor A (€169/month for 5 years)"]["ETF"] = {
                "broker": broker,
                "cost": analysis.investor_a_etf_cost
            }

        if analysis.investor_a_stock_cost > 0 and analysis.investor_a_stock_cost < results["Investor A (€169/month for 5 years)"]["Stocks"]["cost"]:
            results["Investor A (€169/month for 5 years)"]["Stocks"] = {
                "broker": broker,
                "cost": analysis.investor_a_stock_cost
            }

        # Investor B
        if analysis.investor_b_etf_cost > 0 and analysis.investor_b_etf_cost < results["Investor B (€10k lump + €500/month for 5 years)"]["ETF"]["cost"]:
            results["Investor B (€10k lump + €500/month for 5 years)"]["ETF"] = {
                "broker": broker,
                "cost": analysis.investor_b_etf_cost
            }

        if analysis.investor_b_stock_cost > 0 and analysis.investor_b_stock_cost < results["Investor B (€10k lump + €500/month for 5 years)"]["Stocks"]["cost"]:
            results["Investor B (€10k lump + €500/month for 5 years)"]["Stocks"] = {
                "broker": broker,
                "cost": analysis.investor_b_stock_cost
            }

    return results


def generate_analysis_report(analyses: Dict[str, BrokerAnalysis], output_dir: Path):
    """Generate comprehensive analysis reports."""

    output_dir.mkdir(exist_ok=True)

    # 1. Data quality report
    quality_issues = []
    for broker, analysis in analyses.items():
        for issue in analysis.data_quality_issues:
            quality_issues.append({"broker": broker, "issue": issue})

    with open(output_dir / "data_quality_issues.json", "w") as f:
        json.dump(quality_issues, f, indent=2)

    # 2. Fee structure analysis
    structure_analysis = {}
    for broker, analysis in analyses.items():
        structure_analysis[broker] = {
            "ETF_structure": analysis.etf_fee_structure,
            "Stock_structure": analysis.stock_fee_structure,
            "has_custody_fee": analysis.has_custody_fee,
            "custody_details": analysis.custody_fee_details
        }

    with open(output_dir / "fee_structure_analysis.json", "w") as f:
        json.dump(structure_analysis, f, indent=2)

    # 3. Cheapest broker by trade size
    cheapest_by_size = find_cheapest_brokers(analyses)
    with open(output_dir / "cheapest_by_trade_size.json", "w") as f:
        json.dump(cheapest_by_size, f, indent=2)

    # 4. Cheapest broker by investor scenario
    cheapest_by_scenario = find_cheapest_for_scenarios(analyses)
    with open(output_dir / "cheapest_by_scenario.json", "w") as f:
        json.dump(cheapest_by_scenario, f, indent=2)

    # 5. Full analysis CSV
    with open(output_dir / "full_broker_analysis.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "broker", "etf_fee_structure", "stock_fee_structure",
            "has_custody_fee", "custody_fee_details",
            "etf_cost_250", "etf_cost_500", "etf_cost_1000", "etf_cost_5000",
            "stock_cost_250", "stock_cost_500", "stock_cost_1000", "stock_cost_5000",
            "investor_a_etf_cost", "investor_a_stock_cost",
            "investor_b_etf_cost", "investor_b_stock_cost",
            "data_quality_issues"
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for broker, analysis in analyses.items():
            row = asdict(analysis)
            row["data_quality_issues"] = "; ".join(analysis.data_quality_issues)
            writer.writerow(row)

    return {
        "quality_issues": len(quality_issues),
        "brokers_analyzed": len(analyses),
        "output_files": [
            "data_quality_issues.json",
            "fee_structure_analysis.json",
            "cheapest_by_trade_size.json",
            "cheapest_by_scenario.json",
            "full_broker_analysis.csv"
        ]
    }


def create_summary_report(analyses: Dict[str, BrokerAnalysis]) -> str:
    """Create a text summary report for Rudolf."""

    summary = []
    summary.append("# Broker Fee Analysis Summary")
    summary.append("")

    # Data quality issues
    summary.append("## Data Quality Issues Found:")
    total_issues = 0
    for broker, analysis in analyses.items():
        if analysis.data_quality_issues:
            summary.append(f"\n**{broker}:**")
            for issue in analysis.data_quality_issues:
                summary.append(f"- {issue}")
                total_issues += 1

    if total_issues == 0:
        summary.append("✅ No data quality issues found!")

    summary.append("")

    # Fee structures
    summary.append("## Fee Structure Types:")
    for broker, analysis in analyses.items():
        etf_struct = analysis.etf_fee_structure
        stock_struct = analysis.stock_fee_structure
        custody = "Yes" if analysis.has_custody_fee else "No"

        summary.append(f"**{broker}:**")
        summary.append(f"- ETFs: {etf_struct}")
        summary.append(f"- Stocks: {stock_struct}")
        summary.append(f"- Custody Fee: {custody} ({analysis.custody_fee_details})")
        summary.append("")

    # Cheapest by trade size
    cheapest_by_size = find_cheapest_brokers(analyses)

    summary.append("## Cheapest Broker by Trade Size:")
    summary.append("\n**ETFs:**")
    for size, info in cheapest_by_size["ETF"].items():
        summary.append(f"- €{size}: {info['broker']} (€{info['cost']:.2f})")

    summary.append("\n**Stocks:**")
    for size, info in cheapest_by_size["Stocks"].items():
        summary.append(f"- €{size}: {info['broker']} (€{info['cost']:.2f})")

    summary.append("")

    # Investor scenarios
    cheapest_by_scenario = find_cheapest_for_scenarios(analyses)

    summary.append("## Cheapest Broker by Investor Profile:")
    for scenario, instruments in cheapest_by_scenario.items():
        summary.append(f"\n**{scenario}:**")
        for instrument, info in instruments.items():
            if info['broker']:
                summary.append(f"- {instrument}: {info['broker']} (€{info['cost']:.2f} total cost)")

    return "\n".join(summary)


def main():
    """Main analysis function."""

    # For now, create mock data based on expected values
    # In practice, this would load from actual LLM extraction results
    mock_records = []

    # Create mock records from expected data
    for etf_expected in EXPECTED_BROKER_FEES["ETF"]:
        record = FeeRecord(
            broker=etf_expected.broker,
            instrument_type="ETFs",
            order_channel=etf_expected.order_channel,
            base_fee=etf_expected.base_fee,
            variable_fee=etf_expected.variable_fee,
            currency=etf_expected.currency,
            source="validation_data",
            notes=etf_expected.notes
        )
        mock_records.append(record)

    for stock_expected in EXPECTED_BROKER_FEES["Stocks"]:
        record = FeeRecord(
            broker=stock_expected.broker,
            instrument_type="Equities",
            order_channel=stock_expected.order_channel,
            base_fee=stock_expected.base_fee,
            variable_fee=stock_expected.variable_fee,
            currency=stock_expected.currency,
            source="validation_data",
            notes=stock_expected.notes
        )
        mock_records.append(record)

    # Run analysis
    analyses = analyze_broker_fees(mock_records)

    # Generate reports
    output_dir = Path("data/output/analysis")
    results = generate_analysis_report(analyses, output_dir)

    # Generate summary
    summary = create_summary_report(analyses)
    with open(output_dir / "summary_report.md", "w", encoding="utf-8") as f:
        f.write(summary)

    print("Analysis completed!")
    print(f"- {results['brokers_analyzed']} brokers analyzed")
    print(f"- {results['quality_issues']} data quality issues found")
    print(f"- Reports saved to: {output_dir}")
    print("\nFiles created:")
    for filename in results['output_files'] + ['summary_report.md']:
        print(f"  - {filename}")

    return analyses, results


if __name__ == "__main__":
    main()
