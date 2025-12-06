"""
Test script to verify cost-comparison-tables endpoint improvements.
"""
import requests
import json
from pathlib import Path

API_URL = "http://localhost:8000"

def test_cost_comparison_tables():
    """Test the /cost-comparison-tables endpoint."""
    print("=" * 80)
    print("Testing /cost-comparison-tables endpoint")
    print("=" * 80)

    # Check if broker_cost_analyses.json exists
    data_file = Path("data/output/broker_cost_analyses.json")
    if not data_file.exists():
        print("❌ broker_cost_analyses.json not found!")
        print("   Run: python scripts/generate_exhaustive_summary.py")
        return False

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n✅ Found analysis data for {len(data)} brokers:")
    for broker in data.keys():
        print(f"   - {broker}")

    print("\n🔄 Calling /cost-comparison-tables endpoint...")
    print("   (This may take 30-60 seconds with GPT-4o)")

    try:
        response = requests.get(f"{API_URL}/cost-comparison-tables", params={"model": "gpt-4o"})
        response.raise_for_status()
        result = response.json()

        print("\n✅ Response received successfully!")

        # Validate structure
        required_keys = ["etfs", "stocks", "bonds"]
        for key in required_keys:
            if key not in result:
                print(f"   ❌ Missing key: {key}")
                return False
            print(f"   ✅ {key}: {len(result[key])} brokers")

        # Check for ING Self Invest
        etf_brokers = [row["broker"] for row in result["etfs"]]
        if etf_brokers and etf_brokers[0] == "ING Self Invest":
            print("\n   ✅ ING Self Invest is first in the list")
        elif "ING Self Invest" in etf_brokers:
            print(f"\n   ⚠️  ING Self Invest found but not first (position {etf_brokers.index('ING Self Invest') + 1})")
        else:
            print("\n   ❌ ING Self Invest not found in results")

        # Sample ETF table
        print("\n📊 Sample ETF Costs (€250 transaction):")
        for row in result["etfs"][:5]:
            broker = row.get("broker", "Unknown")
            cost_250 = row.get("250", "N/A")
            print(f"   {broker:20s}: €{cost_250}")

        # Check transaction sizes
        transaction_sizes = ["250", "500", "1000", "1500", "2000", "2500", "5000", "10000", "50000"]
        missing_sizes = []
        for row in result["etfs"]:
            for size in transaction_sizes:
                if size not in row:
                    missing_sizes.append((row["broker"], size))

        if missing_sizes:
            print(f"\n   ⚠️  {len(missing_sizes)} missing transaction size values")
            for broker, size in missing_sizes[:3]:
                print(f"      - {broker}: missing €{size}")
        else:
            print(f"\n   ✅ All transaction sizes present for all brokers")

        # Check notes if present
        if "notes" in result and result["notes"]:
            print(f"\n📝 Notes provided for {len(result['notes'])} brokers:")
            for broker, notes in list(result["notes"].items())[:3]:
                print(f"   {broker}:")
                for product, note in notes.items():
                    print(f"      {product}: {note}")

        # Save result for inspection
        output_file = Path("data/output/cost_comparison_tables.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Full results saved to: {output_file}")

        print("\n" + "=" * 80)
        print("✅ TEST PASSED")
        print("=" * 80)
        return True

    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to API server!")
        print("   Start server with: python scripts/run_api.py")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"   Response: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_health():
    """Quick health check."""
    try:
        response = requests.get(f"{API_URL}/health")
        response.raise_for_status()
        return True
    except:
        return False


if __name__ == "__main__":
    print("\n🏥 Checking if API server is running...")
    if not test_health():
        print("❌ API server not responding at http://localhost:8000")
        print("\nStart the server first:")
        print("   python scripts/run_api.py")
        exit(1)

    print("✅ API server is running\n")

    success = test_cost_comparison_tables()
    exit(0 if success else 1)

