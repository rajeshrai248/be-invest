"""
Test to verify the specific bug fixes for cost-comparison-tables endpoint.

This test checks:
1. ING Self Invest returns actual calculated values (not all null)
2. Keytrade Bank uses tiered pricing (not €29.95 for everything)
3. No duplicate broker entries
4. ING Self Invest appears first
"""
import json
from pathlib import Path

def verify_fixes():
    """Verify the fixes by checking the output file."""
    output_file = Path("data/output/cost_comparison_tables.json")

    if not output_file.exists():
        print("❌ Output file not found. Run the test first:")
        print("   python scripts/test_cost_comparison.py")
        return False

    with open(output_file, "r", encoding="utf-8") as f:
        result = json.load(f)

    print("=" * 80)
    print("VERIFYING BUG FIXES")
    print("=" * 80)

    all_passed = True

    # Test 1: Check for duplicate ING Self Invest entries
    print("\n1. Checking for duplicate broker entries...")
    for table_name in ["etfs", "stocks", "bonds"]:
        brokers = [row["broker"] for row in result[table_name]]
        duplicates = [b for b in brokers if brokers.count(b) > 1]
        if duplicates:
            print(f"   ❌ {table_name}: Found duplicates: {set(duplicates)}")
            all_passed = False
        else:
            print(f"   ✅ {table_name}: No duplicates")

    # Test 2: Check ING Self Invest has non-null values
    print("\n2. Checking ING Self Invest calculations...")
    for table_name in ["etfs", "stocks"]:
        ing_rows = [row for row in result[table_name] if "ING" in row["broker"]]
        if not ing_rows:
            print(f"   ❌ {table_name}: ING Self Invest not found")
            all_passed = False
            continue

        ing_row = ing_rows[0]
        null_count = sum(1 for k, v in ing_row.items() if k != "broker" and v is None)

        if null_count > 3:  # Allow a few nulls for missing data
            print(f"   ❌ {table_name}: ING has {null_count} null values (expected < 3)")
            print(f"      Row: {ing_row}")
            all_passed = False
        else:
            # Check expected values for stocks/ETFs
            expected_250 = 1.0  # 0.35% of 250 = 0.875, min €1
            expected_1000 = 3.5  # 0.35% of 1000 = 3.5
            expected_10000 = 35.0  # 0.35% of 10000 = 35

            if ing_row.get("250") == expected_250:
                print(f"   ✅ {table_name}: €250 = €{ing_row['250']:.2f} (correct)")
            else:
                print(f"   ⚠️  {table_name}: €250 = €{ing_row.get('250', 'null')} (expected €{expected_250})")

            if abs(ing_row.get("1000", 0) - expected_1000) < 0.1:
                print(f"   ✅ {table_name}: €1000 = €{ing_row['1000']:.2f} (correct)")
            else:
                print(f"   ⚠️  {table_name}: €1000 = €{ing_row.get('1000', 'null')} (expected ~€{expected_1000})")

            if abs(ing_row.get("10000", 0) - expected_10000) < 0.5:
                print(f"   ✅ {table_name}: €10000 = €{ing_row['10000']:.2f} (correct)")
            else:
                print(f"   ⚠️  {table_name}: €10000 = €{ing_row.get('10000', 'null')} (expected ~€{expected_10000})")

    # Test 3: Check Keytrade Bank uses tiered pricing
    print("\n3. Checking Keytrade Bank tiered pricing...")
    for table_name in ["stocks"]:
        keytrade_rows = [row for row in result[table_name] if "Keytrade" in row["broker"]]
        if not keytrade_rows:
            print(f"   ❌ {table_name}: Keytrade Bank not found")
            all_passed = False
            continue

        kt_row = keytrade_rows[0]

        # Expected tiered values
        expected = {
            "250": 2.45,
            "500": 5.95,
            "1000": 5.95,
            "2500": 5.95,
            "5000": 14.95,
            "10000": 14.95,
            "50000": 44.95  # 14.95 + 4*7.50
        }

        all_match = True
        for size, expected_val in expected.items():
            actual_val = kt_row.get(size)
            if actual_val is None:
                print(f"   ❌ €{size}: null (expected €{expected_val})")
                all_match = False
                all_passed = False
            elif abs(actual_val - expected_val) > 0.1:
                print(f"   ❌ €{size}: €{actual_val:.2f} (expected €{expected_val})")
                all_match = False
                all_passed = False

        if all_match:
            print(f"   ✅ All values match tiered pricing structure")
            print(f"      €250: €{kt_row['250']:.2f}, €500: €{kt_row['500']:.2f}, €5000: €{kt_row['5000']:.2f}, €50000: €{kt_row['50000']:.2f}")

    # Test 4: Check ING Self Invest is first
    print("\n4. Checking broker order...")
    for table_name in ["etfs", "stocks", "bonds"]:
        first_broker = result[table_name][0]["broker"]
        if "ING" in first_broker:
            print(f"   ✅ {table_name}: ING Self Invest is first")
        else:
            print(f"   ⚠️  {table_name}: First broker is {first_broker} (ING should be first)")

    # Summary
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED - Bugs are fixed!")
    else:
        print("❌ SOME TESTS FAILED - Review the output above")
    print("=" * 80)

    return all_passed


def show_comparison_table():
    """Show a comparison table of key values."""
    output_file = Path("data/output/cost_comparison_tables.json")

    if not output_file.exists():
        return

    with open(output_file, "r", encoding="utf-8") as f:
        result = json.load(f)

    print("\n" + "=" * 80)
    print("STOCKS TRANSACTION COSTS COMPARISON")
    print("=" * 80)
    print(f"{'Broker':<20} {'€250':>8} {'€1000':>8} {'€2500':>8} {'€10000':>8} {'€50000':>8}")
    print("-" * 80)

    for row in result.get("stocks", [])[:5]:
        broker = row["broker"][:19]
        v250 = f"€{row.get('250', 0):.2f}" if row.get('250') is not None else "null"
        v1000 = f"€{row.get('1000', 0):.2f}" if row.get('1000') is not None else "null"
        v2500 = f"€{row.get('2500', 0):.2f}" if row.get('2500') is not None else "null"
        v10000 = f"€{row.get('10000', 0):.2f}" if row.get('10000') is not None else "null"
        v50000 = f"€{row.get('50000', 0):.2f}" if row.get('50000') is not None else "null"

        print(f"{broker:<20} {v250:>8} {v1000:>8} {v2500:>8} {v10000:>8} {v50000:>8}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    success = verify_fixes()
    show_comparison_table()
    exit(0 if success else 1)

