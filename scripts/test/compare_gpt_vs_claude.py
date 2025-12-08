"""
Compare cost-comparison-tables results between OpenAI and Claude models.

This script:
1. Calls the endpoint with GPT-4o
2. Calls the endpoint with Claude 3.5 Sonnet
3. Compares the results for accuracy
4. Highlights any differences
"""
import requests
import json
import time
from pathlib import Path
from typing import Dict, Any

API_URL = "http://localhost:8000"

def call_cost_comparison(model: str) -> Dict[str, Any]:
    """Call the cost-comparison-tables endpoint with specified model."""
    print(f"\n{'='*80}")
    print(f"🔄 Testing with {model}")
    print('='*80)

    start_time = time.time()

    try:
        response = requests.get(
            f"{API_URL}/cost-comparison-tables",
            params={"model": model},
            timeout=120  # 2 minutes timeout
        )
        response.raise_for_status()

        duration = time.time() - start_time
        result = response.json()

        print(f"✅ Response received in {duration:.2f}s")

        # Quick validation
        if "etfs" in result and "stocks" in result and "bonds" in result:
            print(f"✅ Has all three tables")
            print(f"   - ETFs: {len(result['etfs'])} brokers")
            print(f"   - Stocks: {len(result['stocks'])} brokers")
            print(f"   - Bonds: {len(result['bonds'])} brokers")

        return result

    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after 120 seconds")
        return {}
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if e.response:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:1000]}")
        return {}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {}


def compare_broker_costs(gpt_result: Dict, claude_result: Dict, product: str, broker: str):
    """Compare costs for a specific broker and product."""
    gpt_rows = [r for r in gpt_result.get(product, []) if r["broker"] == broker]
    claude_rows = [r for r in claude_result.get(product, []) if r["broker"] == broker]

    if not gpt_rows or not claude_rows:
        return None, None

    gpt_row = gpt_rows[0]
    claude_row = claude_rows[0]

    sizes = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
    differences = []

    for size in sizes:
        gpt_val = gpt_row.get(size)
        claude_val = claude_row.get(size)

        if gpt_val is None and claude_val is None:
            continue

        if gpt_val is None or claude_val is None:
            differences.append({
                "size": size,
                "gpt": gpt_val,
                "claude": claude_val,
                "diff": "One is null"
            })
        elif abs(gpt_val - claude_val) > 0.01:  # Allow 1 cent rounding difference
            differences.append({
                "size": size,
                "gpt": gpt_val,
                "claude": claude_val,
                "diff": abs(gpt_val - claude_val)
            })

    return gpt_row, claude_row, differences


def detailed_comparison(gpt_result: Dict, claude_result: Dict):
    """Perform detailed comparison of results."""
    print("\n" + "="*80)
    print("📊 DETAILED COMPARISON")
    print("="*80)

    products = ["stocks", "etfs", "bonds"]

    for product in products:
        print(f"\n{'─'*80}")
        print(f"📈 {product.upper()}")
        print('─'*80)

        gpt_brokers = set(r["broker"] for r in gpt_result.get(product, []))
        claude_brokers = set(r["broker"] for r in claude_result.get(product, []))

        if gpt_brokers != claude_brokers:
            print(f"⚠️  Broker list mismatch!")
            print(f"   GPT only: {gpt_brokers - claude_brokers}")
            print(f"   Claude only: {claude_brokers - gpt_brokers}")
            continue

        for broker in sorted(gpt_brokers):
            gpt_row, claude_row, differences = compare_broker_costs(gpt_result, claude_result, product, broker)

            if gpt_row is None:
                continue

            if differences:
                print(f"\n⚠️  {broker} - Found {len(differences)} differences:")
                for diff in differences[:3]:  # Show first 3
                    print(f"   €{diff['size']:>6}: GPT=€{diff['gpt']}, Claude=€{diff['claude']}, diff={diff['diff']}")
            else:
                print(f"✅ {broker} - All values match")


def accuracy_check(result: Dict, model_name: str):
    """Check known expected values for accuracy."""
    print(f"\n{'─'*80}")
    print(f"🎯 Accuracy Check: {model_name}")
    print('─'*80)

    checks = []

    # Check ING Self Invest stocks
    ing_stocks = [r for r in result.get("stocks", []) if "ING" in r["broker"]]
    if ing_stocks:
        ing = ing_stocks[0]
        # Expected: 0.35% with €1 min
        expected = {
            "250": 1.0,
            "1000": 3.5,
            "10000": 35.0,
            "50000": 175.0
        }
        for size, exp_val in expected.items():
            actual = ing.get(size)
            if actual is None:
                checks.append(f"❌ ING €{size}: null (expected €{exp_val})")
            elif abs(actual - exp_val) < 0.1:
                checks.append(f"✅ ING €{size}: €{actual:.2f}")
            else:
                checks.append(f"⚠️  ING €{size}: €{actual:.2f} (expected €{exp_val})")

    # Check Keytrade Bank stocks
    kt_stocks = [r for r in result.get("stocks", []) if "Keytrade" in r["broker"]]
    if kt_stocks:
        kt = kt_stocks[0]
        # Expected: tiered pricing
        expected = {
            "250": 2.45,
            "500": 5.95,
            "5000": 14.95,
            "50000": 44.95
        }
        for size, exp_val in expected.items():
            actual = kt.get(size)
            if actual is None:
                checks.append(f"❌ Keytrade €{size}: null (expected €{exp_val})")
            elif abs(actual - exp_val) < 0.1:
                checks.append(f"✅ Keytrade €{size}: €{actual:.2f}")
            else:
                checks.append(f"⚠️  Keytrade €{size}: €{actual:.2f} (expected €{exp_val})")

    for check in checks:
        print(f"   {check}")

    # Count accuracy
    passed = sum(1 for c in checks if c.startswith("✅"))
    total = len(checks)
    accuracy = (passed / total * 100) if total > 0 else 0

    print(f"\n   Accuracy: {passed}/{total} ({accuracy:.1f}%)")

    return accuracy


def main():
    """Run comparison test."""
    print("="*80)
    print("🔬 CLAUDE vs GPT-4o COMPARISON TEST")
    print("="*80)

    # Check server health
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
        print("✅ API server is running\n")
    except:
        print("❌ API server not responding at http://localhost:8000")
        print("\nStart the server first:")
        print("   python scripts/run_api.py")
        return 1

    # Check if broker data exists
    data_file = Path("data/output/broker_cost_analyses.json")
    if not data_file.exists():
        print("❌ broker_cost_analyses.json not found!")
        print("   Run: python scripts/generate_exhaustive_summary.py")
        return 1

    # Test both models
    print("\n⏱️  This will take 1-2 minutes total...")

    gpt_result = call_cost_comparison("gpt-4o")

    # Try Claude Sonnet 4 (available in Tier 1)
    print("\n🔄 Testing Claude Sonnet 4...")
    claude_result = call_cost_comparison("claude-sonnet-4-20250514")  # Claude Sonnet 4

    if not gpt_result:
        print("\n❌ GPT-4o test failed")
        return 1

    if not claude_result:
        print("\n⚠️  Claude test failed - this is usually because:")
        print("   1. Model name incorrect (check Anthropic console for available models)")
        print("   2. API rate limits exceeded")
        print("   3. Network/API issue")
        print("\n✅ Showing GPT-4o results only...")

        # Just show GPT results
        gpt_accuracy = accuracy_check(gpt_result, "GPT-4o")

        # Save GPT result
        output_dir = Path("data/output")
        with open(output_dir / "cost_comparison_gpt4o.json", "w", encoding="utf-8") as f:
            json.dump(gpt_result, f, indent=2, ensure_ascii=False)

        print(f"\n💾 GPT-4o results saved to {output_dir / 'cost_comparison_gpt4o.json'}")
        print(f"\n📊 GPT-4o Accuracy: {gpt_accuracy:.1f}%")
        print("\nTo enable Claude comparison:")
        print("  1. Check available models at https://console.anthropic.com/settings/limits")
        print("  2. Verify ANTHROPIC_API_KEY is set: $env:ANTHROPIC_API_KEY = 'sk-ant-...'")
        print("  3. Try model: claude-sonnet-4-20250514 or claude-opus-4-20250514")
        return 0

    if not gpt_result or not claude_result:
        print("\n❌ Failed to get results from one or both models")
        return 1

    # Save results
    output_dir = Path("data/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "cost_comparison_gpt4o.json", "w", encoding="utf-8") as f:
        json.dump(gpt_result, f, indent=2, ensure_ascii=False)

    with open(output_dir / "cost_comparison_claude.json", "w", encoding="utf-8") as f:
        json.dump(claude_result, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to {output_dir}")

    # Accuracy checks
    gpt_accuracy = accuracy_check(gpt_result, "GPT-4o")
    claude_accuracy = accuracy_check(claude_result, "Claude Sonnet 4")

    # Detailed comparison
    detailed_comparison(gpt_result, claude_result)

    # Summary
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"GPT-4o accuracy: {gpt_accuracy:.1f}%")
    print(f"Claude Sonnet 4 accuracy: {claude_accuracy:.1f}%")

    if claude_accuracy > gpt_accuracy:
        print(f"\n🏆 Claude is more accurate (+{claude_accuracy - gpt_accuracy:.1f}%)")
    elif gpt_accuracy > claude_accuracy:
        print(f"\n🏆 GPT-4o is more accurate (+{gpt_accuracy - claude_accuracy:.1f}%)")
    else:
        print(f"\n🤝 Both models have equal accuracy")

    print("\nCheck the detailed JSON files for full comparison:")
    print(f"  - {output_dir / 'cost_comparison_gpt4o.json'}")
    print(f"  - {output_dir / 'cost_comparison_claude.json'}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

