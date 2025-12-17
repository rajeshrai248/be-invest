"""Comprehensive test script for LLM extraction validation.

This script validates LLM extraction results against Rudolf's specific feedback
and runs the improved extraction with enhanced prompts.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.be_invest.models import FeeRecord
from src.be_invest.sources.llm_extract import extract_fee_records_via_llm
from tests.test_data_quality_validation import (
    EXPECTED_BROKER_FEES,
    EXPECTED_CUSTODY_FEES,
    calculate_total_cost,
    validate_fee_structure_type
)


def create_test_pdf_text_samples() -> Dict[str, str]:
    """Create realistic PDF text samples for testing LLM extraction."""

    return {
        "Bolero": """
TARIEVENOVERZICHT 2025

TRANSACTIEKOSTEN

Online trading via Bolero platform:

Aandelen (Equities):
- Euronext Brussels: €15,00 per transactie
- Euronext Paris: €15,00 per transactie  
- Euronext Amsterdam: €15,00 per transactie

ETF's:
- Alle markten: €15,00 per transactie

Obligaties (Bonds):
- Minimum: €50,00
- 0,25% van transactiewaarde

DEPOTKOSTEN:
- 0,15% per jaar (minimum €15, maximum €150)
""",

        "Degiro Belgium": """
TARIEVENOVERZICHT DEGIRO

TRANSACTIEKOSTEN:

Aandelen Europa:
- Basisprijs: €2,00
- + 0,026% van orderwaarde  
- Verwerkingskosten: €1,00

ETF's:
- Gratis voor kernselectie
- Overige ETF's: €1,00 verwerkingskosten

DEPOTKOSTEN:
- Geen jaarlijkse kosten voor aandelen en ETF's
- Connectiviteitskosten: €2,50 per beurs per jaar
""",

        "Rebel": """
TARIFS REBEL 2025

FRAIS DE TRANSACTION:

Actions Euronext:
- Bruxelles: €3,00 (jusqu'à €2.500)
- Bruxelles: 0,60% (au-delà de €2.500)
- Paris: €7,50 (jusqu'à €2.500)  
- Amsterdam: €7,50 (jusqu'à €2.500)

ETF:
- 0,25% de la valeur de transaction
- Minimum €7,50

FRAIS DE GARDE:
- Aucun frais de garde pour les actions et ETF
""",

        "ING Self Invest": """
PRICING OVERVIEW ING SELF INVEST

TRANSACTION COSTS:

Shares & ETFs:
- All markets: €7,50 per transaction
- No minimum or maximum

Bonds:
- Corporate bonds: 0,30%
- Government bonds: 0,15%
- Minimum: €25

CUSTODY FEES:
- Annual fee: 0,24% of portfolio value
- Minimum: €18 per year
- Maximum: €240 per year
""",

        "Keytrade Bank": """
TARIFS KEYTRADE BANK 2025

FRAIS DE COURTAGE:

Actions:
- Euronext: 0,35% (minimum €7,50)
- Autres marchés européens: 0,50% (minimum €15)

ETF:
- 0,19% de la valeur
- Minimum €2,50

Options:
- €2,50 par contrat

FRAIS DE GARDE:
- Aucun frais de garde
- Service de prêt de titres disponible
"""
    }


def validate_extraction_against_rudolf_feedback(
    extracted_records: List[FeeRecord],
    broker: str
) -> List[str]:
    """Validate extraction results against Rudolf's specific feedback."""

    issues = []

    # Find relevant records
    etf_records = [r for r in extracted_records if r.instrument_type == "ETFs"]
    stock_records = [r for r in extracted_records if r.instrument_type == "Equities"]

    etf_record = etf_records[0] if etf_records else None
    stock_record = stock_records[0] if stock_records else None

    # Rudolf's specific checks
    if broker == "Bolero":
        # Check: 5k trade cost 15€ not 10€
        if etf_record:
            cost_5k = calculate_total_cost(etf_record, 5000)
            if abs(cost_5k - 15.0) > 0.01:
                issues.append(f"Bolero ETF 5k trade: expected €15, got €{cost_5k}")

        if stock_record:
            cost_5k = calculate_total_cost(stock_record, 5000)
            if abs(cost_5k - 15.0) > 0.01:
                issues.append(f"Bolero Stock 5k trade: expected €15, got €{cost_5k}")

    elif broker == "Degiro Belgium":
        # Check: must include 1€ handling fee
        if etf_record:
            if (etf_record.base_fee or 0) < 1.0:
                issues.append("Degiro ETF missing €1 handling fee")

        if stock_record:
            # Stock should have €2 + 0.026% + €1 handling = €3 + 0.026% for 5k trade
            expected_5k = 3.0 + (5000 * 0.00026)  # €3.13
            actual_5k = calculate_total_cost(stock_record, 5000)
            if abs(actual_5k - expected_5k) > 0.50:  # Allow some tolerance
                issues.append(f"Degiro Stock 5k trade: expected ~€{expected_5k:.2f}, got €{actual_5k}")

    elif broker == "Rebel":
        # Check: Brussels vs Paris/Amsterdam data
        if stock_record:
            cost_2500 = calculate_total_cost(stock_record, 2500)
            if abs(cost_2500 - 3.0) > 0.01:
                issues.append(f"Rebel Stock €2.5k trade: expected €3 (Brussels), got €{cost_2500}")

        # Check for wrong market references
        for record in extracted_records:
            if record.notes and ("Paris" in record.notes or "Amsterdam" in record.notes):
                if "Brussels" not in record.notes:
                    issues.append("Rebel: appears to use Paris/Amsterdam data instead of Brussels")

    return issues


def test_llm_extraction_with_enhanced_prompts():
    """Test LLM extraction with enhanced prompts for all brokers."""

    print("🧪 Testing Enhanced LLM Extraction")
    print("=" * 50)

    test_samples = create_test_pdf_text_samples()
    all_results = {}

    # Check if API keys are available
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

    if not (has_openai or has_anthropic):
        print("❌ No API keys found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY to test LLM extraction.")
        return create_mock_validation_results()

    for broker, pdf_text in test_samples.items():
        print(f"\n📊 Testing {broker}...")

        try:
            # Test with enhanced prompts
            extracted_records = extract_fee_records_via_llm(
                text=pdf_text,
                broker=broker,
                source_url=f"https://example.com/{broker.lower()}_fees.pdf",
                model="gpt-4o" if has_openai else "claude-3-haiku-20240307",
                llm_cache_dir=Path("data/cache"),
                chunk_chars=8000,
                focus_fee_lines=True,
                strict_mode=True
            )

            print(f"✅ Extracted {len(extracted_records)} fee records")

            # Validate against Rudolf's feedback
            validation_issues = validate_extraction_against_rudolf_feedback(
                extracted_records, broker
            )

            if validation_issues:
                print("⚠️  Validation Issues:")
                for issue in validation_issues:
                    print(f"   - {issue}")
            else:
                print("✅ No validation issues found")

            all_results[broker] = {
                "records": extracted_records,
                "validation_issues": validation_issues,
                "record_count": len(extracted_records)
            }

        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            all_results[broker] = {
                "records": [],
                "validation_issues": [f"Extraction failed: {e}"],
                "record_count": 0
            }

    return all_results


def create_mock_validation_results() -> Dict[str, Any]:
    """Create mock validation results when no API keys are available."""

    print("\n🔄 Creating mock validation results for testing...")

    mock_results = {}

    for broker_type in ["ETF", "Stocks"]:
        for expected in EXPECTED_BROKER_FEES[broker_type]:
            broker = expected.broker

            if broker not in mock_results:
                mock_results[broker] = {
                    "records": [],
                    "validation_issues": [],
                    "record_count": 0
                }

            # Create mock record from expected data
            mock_record = FeeRecord(
                broker=expected.broker,
                instrument_type=expected.instrument_type,
                order_channel=expected.order_channel,
                base_fee=expected.base_fee,
                variable_fee=expected.variable_fee,
                currency=expected.currency,
                source="mock_data",
                notes=expected.notes
            )

            mock_results[broker]["records"].append(mock_record)
            mock_results[broker]["record_count"] += 1

            # Add validation issues based on known problems
            if broker == "Bolero" and expected.trade_size_eur == 5000:
                if expected.expected_total_cost_eur != 15.0:
                    mock_results[broker]["validation_issues"].append(
                        f"Bolero {expected.instrument_type} 5k trade: should be €15"
                    )

            elif broker == "Degiro Belgium":
                if expected.base_fee and expected.base_fee < 1.0:
                    mock_results[broker]["validation_issues"].append(
                        f"Degiro {expected.instrument_type} missing €1 handling fee"
                    )

            elif broker == "Rebel" and expected.instrument_type == "Equities":
                mock_results[broker]["validation_issues"].append(
                    "Mock: Potential Brussels vs Paris/Amsterdam confusion"
                )

    return mock_results


def generate_test_report(results: Dict[str, Any]) -> str:
    """Generate a comprehensive test report."""

    report = []
    report.append("# LLM Extraction Validation Report")
    report.append("")
    report.append(f"Generated on: {Path(__file__).name}")
    report.append("")

    # Summary
    total_brokers = len(results)
    brokers_with_issues = sum(1 for r in results.values() if r["validation_issues"])
    total_issues = sum(len(r["validation_issues"]) for r in results.values())

    report.append("## Summary")
    report.append(f"- Brokers tested: {total_brokers}")
    report.append(f"- Brokers with issues: {brokers_with_issues}")
    report.append(f"- Total validation issues: {total_issues}")
    report.append("")

    # Detailed results
    report.append("## Detailed Results")

    for broker, result in results.items():
        report.append(f"\n### {broker}")
        report.append(f"Records extracted: {result['record_count']}")

        if result["validation_issues"]:
            report.append("**Issues found:**")
            for issue in result["validation_issues"]:
                report.append(f"- {issue}")
        else:
            report.append("✅ No issues found")

        # Show fee structures
        etf_records = [r for r in result["records"] if r.instrument_type == "ETFs"]
        stock_records = [r for r in result["records"] if r.instrument_type == "Equities"]

        if etf_records:
            etf_structure = validate_fee_structure_type(etf_records[0])
            report.append(f"ETF fee structure: {etf_structure}")

        if stock_records:
            stock_structure = validate_fee_structure_type(stock_records[0])
            report.append(f"Stock fee structure: {stock_structure}")

    # Recommendations
    report.append("\n## Recommendations")

    if total_issues > 0:
        report.append("### Immediate Actions:")
        report.append("1. **Enhance LLM prompts** for brokers with validation issues")
        report.append("2. **Add specific handling fee detection** for Degiro")
        report.append("3. **Improve market-specific extraction** for Rebel (Brussels vs Paris/Amsterdam)")
        report.append("4. **Validate tier-based fee structures** for complex pricing")
        report.append("")

        report.append("### Next Steps:")
        report.append("1. Update LLM prompts with broker-specific instructions")
        report.append("2. Implement post-processing validation rules")
        report.append("3. Add chunking for large PDF documents")
        report.append("4. Create automated validation pipeline")
    else:
        report.append("✅ All validation tests passed! LLM extraction is working correctly.")

    return "\n".join(report)


def main():
    """Main test execution function."""

    print("🚀 Starting LLM Extraction Validation Tests")
    print("=" * 60)

    # Run tests
    results = test_llm_extraction_with_enhanced_prompts()

    # Generate report
    report = generate_test_report(results)

    # Save report
    output_dir = Path("data/output/validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    report_file = output_dir / "llm_extraction_validation_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    # Save detailed results
    results_file = output_dir / "validation_results.json"

    # Convert FeeRecord objects to dictionaries for JSON serialization
    json_results = {}
    for broker, result in results.items():
        json_results[broker] = {
            "validation_issues": result["validation_issues"],
            "record_count": result["record_count"],
            "records": [
                {
                    "broker": r.broker,
                    "instrument_type": r.instrument_type,
                    "order_channel": r.order_channel,
                    "base_fee": r.base_fee,
                    "variable_fee": r.variable_fee,
                    "currency": r.currency,
                    "source": r.source,
                    "notes": r.notes
                }
                for r in result["records"]
            ]
        }

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 60)
    print("📋 VALIDATION COMPLETE")
    print("=" * 60)

    total_issues = sum(len(r["validation_issues"]) for r in results.values())
    if total_issues > 0:
        print(f"⚠️  Found {total_issues} validation issues across {len(results)} brokers")
        print("\nKey issues to address:")
        for broker, result in results.items():
            if result["validation_issues"]:
                print(f"  {broker}: {len(result['validation_issues'])} issue(s)")
    else:
        print("✅ All validation tests passed!")

    print(f"\n📄 Reports saved to:")
    print(f"  - {report_file}")
    print(f"  - {results_file}")

    return results


if __name__ == "__main__":
    main()
